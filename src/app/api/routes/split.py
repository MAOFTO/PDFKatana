import json
import os
import tempfile
import time
import zipfile
from io import BytesIO

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.splitter import split_pdf
from app.core.sweeper import cleanup_temp_files
from app.schemas.split import SplitRequest
from app.utils.logger import logger

router = APIRouter()


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

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    logger.info(f"Request {request_id}: Saved to temp file {tmp_path}")

    # Parse pages JSON
    try:
        pages_data = json.loads(pages)
        split_request = SplitRequest(**pages_data)
        split_pages = [page_obj.page for page_obj in split_request.pages]
        logger.info(f"Request {request_id}: Split pages: {split_pages}")
    except Exception as e:
        os.remove(tmp_path)
        logger.error(f"Request {request_id}: Invalid pages JSON: {e}")
        raise HTTPException(status_code=422, detail="Invalid pages JSON format.")

    # Split PDF
    try:
        logger.info(f"Request {request_id}: Starting PDF split operation")
        parts = split_pdf(tmp_path, split_pages)
        logger.info(f"Request {request_id}: Split completed, generated {len(parts)} parts")
    except Exception as e:
        os.remove(tmp_path)
        logger.error(f"Request {request_id}: Split error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    logger.info(f"Request {request_id}: Saved to temp file {tmp_path}")

    # Parse pages JSON
    try:
        pages_data = json.loads(pages)
        split_request = SplitRequest(**pages_data)
        split_pages = [page_obj.page for page_obj in split_request.pages]
        logger.info(f"Request {request_id}: Split pages: {split_pages}")
    except Exception as e:
        os.remove(tmp_path)
        logger.error(f"Request {request_id}: Invalid pages JSON: {e}")
        raise HTTPException(status_code=422, detail="Invalid pages JSON format.")

    # Split PDF
    try:
        logger.info(f"Request {request_id}: Starting PDF split operation")
        parts = split_pdf(tmp_path, split_pages)
        logger.info(f"Request {request_id}: Split completed, generated {len(parts)} parts")
    except Exception as e:
        os.remove(tmp_path)
        logger.error(f"Request {request_id}: Split error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Record metrics
    duration = time.time() - start_time
    from app.api.routes.metrics import split_duration_seconds, split_pages_total

    split_duration_seconds.observe(duration)
    split_pages_total.inc(len(parts))

    logger.info(f"Request {request_id}: Operation completed in {duration:.2f} seconds")

    # Clean up old temp files
    cleanup_temp_files()

    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, part in enumerate(parts):
            filename = f"{os.path.splitext(file.filename)[0]}_part{idx + 1}.pdf"
            # Reset file pointer to beginning
            part.seek(0)
            zip_file.writestr(filename, part.read())

    # Reset buffer pointer to beginning
    zip_buffer.seek(0)

    # Schedule temp file cleanup
    if background_tasks:
        background_tasks.add_task(os.remove, tmp_path)
        logger.info(f"Request {request_id}: Scheduled temp file cleanup")

    # Return ZIP file
    zip_filename = f"{os.path.splitext(file.filename)[0]}_split.zip"

    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
            "Content-Length": str(zip_buffer.tell()),
        },
    )
