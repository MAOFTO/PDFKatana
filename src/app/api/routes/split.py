import json
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.splitter import split_pdf
from app.utils.logger import logger

router = APIRouter()


@router.post("/v1/split")
async def split_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    separators: str = Form(...),
):
    # Validate file size
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large.")
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, dir="tmp", suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    # Parse separators
    try:
        try:
            sep_obj = json.loads(separators)
        except Exception:
            sep_obj = separators  # fallback to raw string if not JSON
        if isinstance(sep_obj, dict) and "separators" in sep_obj:
            sep_list = sep_obj["separators"]
        elif isinstance(sep_obj, list):
            sep_list = sep_obj
        elif isinstance(sep_obj, str):
            # Try to parse a comma-separated string or a quoted array
            sep_str = sep_obj.strip()
            if sep_str.startswith("[") and sep_str.endswith("]"):
                # Try to parse as JSON array string
                sep_list = json.loads(sep_str)
            else:
                sep_list = [int(x.strip()) for x in sep_str.split(",") if x.strip()]
        else:
            raise ValueError
        sep_list = [int(x) for x in sep_list]
    except Exception:
        os.remove(tmp_path)
        raise HTTPException(status_code=422, detail="Invalid separators JSON.")
    # Split PDF
    try:
        parts = split_pdf(tmp_path, sep_list)
    except Exception as e:
        os.remove(tmp_path)
        logger.error(f"Split error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
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
    return StreamingResponse(
        iter_parts(),
        media_type=f"multipart/mixed; boundary={boundary}",
        headers={"Content-Disposition": "inline"},
    )
