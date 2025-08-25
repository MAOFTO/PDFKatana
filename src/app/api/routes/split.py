import json
import os
import tempfile
import time
import zipfile
from io import BytesIO
from typing import Tuple

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.core.splitter import split_pdf
from app.core.sweeper import cleanup_temp_files
from app.core.validator import PDFValidator
from app.schemas.split import SplitRequest
from app.utils.logger import logger

router = APIRouter()


def validate_and_repair_input_pdf(contents: bytes, filename: str) -> Tuple[bytes, dict]:
    """
    Validate and repair input PDF before processing.
    Returns (repaired_contents, validation_info).
    """
    try:
        # Create BytesIO buffer for validation
        pdf_buffer = BytesIO(contents)

        # Perform comprehensive validation
        validator = PDFValidator()
        validation_result = validator.comprehensive_validation(pdf_buffer)

        # Add file info
        validation_result["filename"] = filename
        validation_result["original_size_mb"] = len(contents) / (1024 * 1024)

        # If PDF is valid, return as-is
        if validation_result["is_valid"]:
            logger.info(f"Input PDF '{filename}' is valid and ready for processing")
            return contents, validation_result

        # If PDF needs repair, attempt it
        if validation_result["needs_repair"]:
            logger.info(f"Input PDF '{filename}' needs repair, attempting...")

            # Try to repair the PDF
            if validation_result["repair_successful"]:
                # Get the repaired content
                pdf_buffer.seek(0)
                repaired_contents = pdf_buffer.read()
                logger.info(f"Input PDF '{filename}' successfully repaired")
                return repaired_contents, validation_result
            else:
                # Repair failed
                logger.warning(f"Input PDF '{filename}' could not be repaired")
                return contents, validation_result

        # If PDF is invalid and not repairable, return original with validation info
        logger.warning(f"Input PDF '{filename}' is invalid and not repairable")
        return contents, validation_result

    except Exception as e:
        logger.error(f"PDF validation failed for '{filename}': {e}")
        # Return original content with error info
        return contents, {
            "filename": filename,
            "original_size_mb": len(contents) / (1024 * 1024),
            "is_valid": False,
            "validation_error": str(e),
        }


@router.post("/v1/validate-pdf")
async def validate_pdf_endpoint(
    request: Request,
    file: UploadFile = File(...),
):
    """Validate a PDF file for compatibility with paperless-ngx and other systems"""
    start_time = time.time()
    request_id = str(time.time())

    logger.info(f"Request {request_id}: Starting PDF validation for file {file.filename}")

    # Validate file size
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    logger.info(f"Request {request_id}: File size {file_size_mb:.2f} MB")

    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        logger.warning(f"Request {request_id}: File too large ({file_size_mb:.2f} MB)")
        raise HTTPException(status_code=413, detail="File too large.")

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    logger.info(f"Request {request_id}: Saved to temp file {tmp_path}")

    try:
        # Create BytesIO buffer for validation
        pdf_buffer = BytesIO(contents)

        # Perform comprehensive validation
        validator = PDFValidator()
        validation_result = validator.comprehensive_validation(pdf_buffer)

        # Add file info
        validation_result["filename"] = file.filename
        validation_result["original_size_mb"] = file_size_mb

        # Clean up temp file
        os.remove(tmp_path)

        # Record metrics
        duration = time.time() - start_time
        logger.info(f"Request {request_id}: Validation completed in {duration:.2f} seconds")

        # Clean up old temp files
        cleanup_temp_files()

        return validation_result

    except Exception as e:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        logger.error(f"Request {request_id}: Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"PDF validation failed: {str(e)}")


@router.post("/v1/split")
async def split_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    start_time = time.time()
    request_id = str(time.time())  # Simple request ID for logging

    logger.info(f"Request {request_id}: Starting PDF split for file {file.filename}")

    # Validate file size
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    logger.info(f"Request {request_id}: File size {file_size_mb:.2f} MB")

    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        logger.warning(f"Request {request_id}: File too large ({file_size_mb:.2f} MB)")
        raise HTTPException(status_code=413, detail="File too large.")

    # Validate and repair input PDF upfront
    logger.info(f"Request {request_id}: Validating and repairing input PDF")
    repaired_contents, validation_info = validate_and_repair_input_pdf(contents, file.filename)

    # Check if PDF is valid enough to proceed
    if not validation_info.get("is_valid", False) and not validation_info.get(
        "repair_successful", False
    ):
        # PDF is invalid and couldn't be repaired
        issues_summary = "; ".join(validation_info.get("issues", []))
        error_detail = f"PDF validation failed and could not be repaired. Issues: {issues_summary}"

        logger.error(f"Request {request_id}: {error_detail}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "PDF validation failed and could not be repaired",
                "validation_info": validation_info,
                "message": "The uploaded PDF has structural issues that prevent safe splitting. Please use a different PDF file.",
            },
        )

    # Log validation results
    if validation_info.get("repair_successful"):
        logger.info(f"Request {request_id}: Input PDF repaired successfully")
    elif validation_info.get("is_valid"):
        logger.info(f"Request {request_id}: Input PDF is already valid")
    else:
        logger.warning(f"Request {request_id}: Input PDF has issues but proceeding with caution")

    # Save repaired/validated PDF to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(repaired_contents)
        tmp_path = tmp.name

    logger.info(f"Request {request_id}: Saved validated/repaired PDF to temp file {tmp_path}")

    # Parse pages JSON and determine if we should split
    should_split = True
    split_pages = []
    parts = None

    try:
        pages_data = json.loads(pages)

        # Check if pages field exists and is not empty
        if "pages" not in pages_data or not pages_data["pages"]:
            should_split = False
            logger.info(
                f"Request {request_id}: Empty or missing pages array, returning original PDF"
            )
        else:
            # Try to parse the pages
            try:
                split_request = SplitRequest(**pages_data)
                split_pages = [page_obj.page for page_obj in split_request.pages]

                # Validate page numbers are in range
                import pikepdf

                with pikepdf.open(tmp_path) as pdf:
                    num_pages = len(pdf.pages)

                    for page_num in split_pages:
                        if page_num < 1 or page_num > num_pages:
                            should_split = False
                            logger.info(
                                f"Request {request_id}: Page {page_num} out of range (1-{num_pages}), returning original PDF"
                            )
                            break

                if should_split:
                    logger.info(f"Request {request_id}: Split pages: {split_pages}")

            except ValueError as ve:
                # Validation error from SplitRequest (e.g., negative page numbers)
                should_split = False
                logger.info(
                    f"Request {request_id}: Invalid page values: {ve}, returning original PDF"
                )
            except Exception as parse_e:
                # Other parsing errors
                should_split = False
                logger.info(
                    f"Request {request_id}: Failed to parse pages: {parse_e}, returning original PDF"
                )

    except json.JSONDecodeError as je:
        should_split = False
        logger.info(f"Request {request_id}: Invalid JSON format: {je}, returning original PDF")
    except Exception as e:
        should_split = False
        logger.info(
            f"Request {request_id}: Unexpected error parsing pages: {e}, returning original PDF"
        )

    # Either split the PDF or return the original
    if should_split:
        # Split PDF (now with validated/repaired input)
        try:
            logger.info(f"Request {request_id}: Starting PDF split operation")
            parts = split_pdf(tmp_path, split_pages)
            logger.info(f"Request {request_id}: Split completed, generated {len(parts)} parts")
        except Exception as e:
            # If split fails, return original PDF
            should_split = False
            logger.warning(
                f"Request {request_id}: Split operation failed: {e}, returning original PDF"
            )

    # If we're not splitting, return the original PDF
    if not should_split:
        logger.info(f"Request {request_id}: Returning original PDF without splitting")

        # Schedule temp file cleanup
        if background_tasks:
            background_tasks.add_task(os.remove, tmp_path)
            logger.info(f"Request {request_id}: Scheduled temp file cleanup")

        # Record metrics
        duration = time.time() - start_time
        from app.api.routes.metrics import split_duration_seconds, split_pages_total

        split_duration_seconds.observe(duration)
        split_pages_total.inc(1)  # Count as 1 part (the original)

        logger.info(f"Request {request_id}: Operation completed in {duration:.2f} seconds")

        # Clean up old temp files
        cleanup_temp_files()

        # Return the original PDF as a streaming response
        return StreamingResponse(
            BytesIO(repaired_contents),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
        )

    # Record metrics
    duration = time.time() - start_time
    from app.api.routes.metrics import split_duration_seconds, split_pages_total

    split_duration_seconds.observe(duration)
    split_pages_total.inc(len(parts))

    logger.info(f"Request {request_id}: Operation completed in {duration:.2f} seconds")

    # Clean up old temp files
    cleanup_temp_files()

    # Prepare multipart/mixed response
    import uuid

    boundary = f"pdfkatana-{uuid.uuid4().hex}"

    def iter_parts():
        for idx, part in enumerate(parts):
            filename = f"{os.path.splitext(file.filename)[0]}_part{idx + 1}.pdf"
            yield (
                f"--{boundary}\r\n"
                f"Content-Type: application/pdf\r\n"
                f'Content-Disposition: attachment; filename="{filename}"\r\n\r\n'
            ).encode()
            yield part.read()
            yield b"\r\n"
        yield f"--{boundary}--\r\n".encode()

    # Schedule temp file cleanup
    if background_tasks:
        background_tasks.add_task(os.remove, tmp_path)
        logger.info(f"Request {request_id}: Scheduled temp file cleanup")

    return StreamingResponse(
        iter_parts(),
        media_type=f"multipart/mixed; boundary={boundary}",
        headers={"Content-Disposition": "inline"},
    )


@router.post("/v1/split-into-zip")
async def split_into_zip_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pages: str = Form(...),
):
    start_time = time.time()
    request_id = str(time.time())  # Simple request ID for logging

    logger.info(f"Request {request_id}: Starting PDF split into ZIP for file {file.filename}")

    # Validate file size
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    logger.info(f"Request {request_id}: File size {file_size_mb:.2f} MB")

    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        logger.warning(f"Request {request_id}: File too large ({file_size_mb:.2f} MB)")
        raise HTTPException(status_code=413, detail="File too large.")

    # Validate and repair input PDF upfront
    logger.info(f"Request {request_id}: Validating and repairing input PDF")
    repaired_contents, validation_info = validate_and_repair_input_pdf(contents, file.filename)

    # Check if PDF is valid enough to proceed
    if not validation_info.get("is_valid", False) and not validation_info.get(
        "repair_successful", False
    ):
        # PDF is invalid and couldn't be repaired
        issues_summary = "; ".join(validation_info.get("issues", []))
        error_detail = f"PDF validation failed and could not be repaired. Issues: {issues_summary}"

        logger.error(f"Request {request_id}: {error_detail}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "PDF validation failed and could not be repaired",
                "validation_info": validation_info,
                "message": "The uploaded PDF has structural issues that prevent safe splitting. Please use a different PDF file.",
            },
        )

    # Log validation results
    if validation_info.get("repair_successful"):
        logger.info(f"Request {request_id}: Input PDF repaired successfully")
    elif validation_info.get("is_valid"):
        logger.info(f"Request {request_id}: Input PDF is already valid")
    else:
        logger.warning(f"Request {request_id}: Input PDF has issues but proceeding with caution")

    # Save repaired/validated PDF to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(repaired_contents)
        tmp_path = tmp.name

    logger.info(f"Request {request_id}: Saved validated/repaired PDF to temp file {tmp_path}")

    # Parse pages JSON and determine if we should split
    should_split = True
    split_pages = []
    parts = None

    try:
        pages_data = json.loads(pages)

        # Check if pages field exists and is not empty
        if "pages" not in pages_data or not pages_data["pages"]:
            should_split = False
            logger.info(
                f"Request {request_id}: Empty or missing pages array, returning original PDF"
            )
        else:
            # Try to parse the pages
            try:
                split_request = SplitRequest(**pages_data)
                split_pages = [page_obj.page for page_obj in split_request.pages]

                # Validate page numbers are in range
                import pikepdf

                with pikepdf.open(tmp_path) as pdf:
                    num_pages = len(pdf.pages)

                    for page_num in split_pages:
                        if page_num < 1 or page_num > num_pages:
                            should_split = False
                            logger.info(
                                f"Request {request_id}: Page {page_num} out of range (1-{num_pages}), returning original PDF"
                            )
                            break

                if should_split:
                    logger.info(f"Request {request_id}: Split pages: {split_pages}")

            except ValueError as ve:
                # Validation error from SplitRequest (e.g., negative page numbers)
                should_split = False
                logger.info(
                    f"Request {request_id}: Invalid page values: {ve}, returning original PDF"
                )
            except Exception as parse_e:
                # Other parsing errors
                should_split = False
                logger.info(
                    f"Request {request_id}: Failed to parse pages: {parse_e}, returning original PDF"
                )

    except json.JSONDecodeError as je:
        should_split = False
        logger.info(f"Request {request_id}: Invalid JSON format: {je}, returning original PDF")
    except Exception as e:
        should_split = False
        logger.info(
            f"Request {request_id}: Unexpected error parsing pages: {e}, returning original PDF"
        )

    # Either split the PDF or return the original
    if should_split:
        # Split PDF (now with validated/repaired input)
        try:
            logger.info(f"Request {request_id}: Starting PDF split operation")
            parts = split_pdf(tmp_path, split_pages)
            logger.info(f"Request {request_id}: Split completed, generated {len(parts)} parts")
        except Exception as e:
            # If split fails, return original PDF
            should_split = False
            logger.warning(
                f"Request {request_id}: Split operation failed: {e}, returning original PDF"
            )

    # If we're not splitting, return the original PDF in a ZIP
    if not should_split:
        logger.info(f"Request {request_id}: Returning original PDF in ZIP without splitting")

        # Create ZIP with single file (the original PDF)
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(file.filename, repaired_contents)

        # Reset buffer pointer to beginning
        zip_buffer.seek(0)

        # Schedule temp file cleanup
        if background_tasks:
            background_tasks.add_task(os.remove, tmp_path)
            logger.info(f"Request {request_id}: Scheduled temp file cleanup")

        # Record metrics
        duration = time.time() - start_time
        from app.api.routes.metrics import split_duration_seconds, split_pages_total

        split_duration_seconds.observe(duration)
        split_pages_total.inc(1)  # Count as 1 part (the original)

        logger.info(f"Request {request_id}: Operation completed in {duration:.2f} seconds")

        # Clean up old temp files
        cleanup_temp_files()

        # Return ZIP file
        zip_filename = f"{os.path.splitext(file.filename)[0]}.zip"

        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )

    # Record metrics for split operation
    duration = time.time() - start_time
    from app.api.routes.metrics import split_duration_seconds, split_pages_total

    split_duration_seconds.observe(duration)
    split_pages_total.inc(len(parts))

    logger.info(f"Request {request_id}: Operation completed in {duration:.2f} seconds")

    # Clean up old temp files
    cleanup_temp_files()

    # Create ZIP file in memory with split parts
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, part in enumerate(parts):
            filename = f"{os.path.splitext(file.filename)[0]}_part{idx + 1}.pdf"
            # Create a fresh BytesIO object with the content
            part.seek(0)
            part_content = part.read()
            # Create new BytesIO to avoid any pointer issues
            fresh_part = BytesIO(part_content)
            # Add to ZIP
            zip_file.writestr(filename, fresh_part.getvalue())

    # Reset buffer pointer to beginning
    zip_buffer.seek(0)

    # Schedule temp file cleanup
    if background_tasks:
        background_tasks.add_task(os.remove, tmp_path)
        logger.info(f"Request {request_id}: Scheduled temp file cleanup")

    # Return ZIP file
    zip_filename = f"{os.path.splitext(file.filename)[0]}_split.zip"

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
