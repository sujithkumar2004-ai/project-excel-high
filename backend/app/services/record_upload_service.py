from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import RecordBatch, UploadedRecordImage

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def create_record_batch_from_uploads(db: Session, files: list[UploadFile]) -> RecordBatch:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one image")

    batch = RecordBatch(batch_code=f"RB-{uuid4().hex[:12].upper()}", total_images=len(files), status="uploaded")
    db.add(batch)
    db.flush()

    upload_dir = Path(settings.upload_dir) / "records" / str(batch.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        content_type = file.content_type or ""
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

        content = await file.read()
        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")

        suffix = Path(file.filename or "").suffix.lower() or ALLOWED_IMAGE_TYPES[content_type]
        if suffix == ".jpeg":
            suffix = ".jpg"
        if suffix not in {".jpg", ".png", ".webp"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {file.filename}")

        stored_name = f"{uuid4().hex}{suffix}"
        stored_path = upload_dir / stored_name
        stored_path.write_bytes(content)
        db.add(
            UploadedRecordImage(
                batch_id=batch.id,
                file_name=stored_name,
                file_path=str(stored_path),
                original_name=file.filename or stored_name,
                mime_type=content_type,
                file_size=len(content),
                status="uploaded",
            )
        )

    return batch
