from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import ExtractedRecordRow, RecordBatch, UploadedRecordImage
from app.schemas.record_schema import (
    ExtractedRecordRowRead,
    ExtractedRecordRowsUpdate,
    RecordBatchAnalyzeResponse,
    RecordBatchDetail,
    RecordBatchFinalizeResponse,
    RecordBatchListResponse,
    RecordBatchUploadResponse,
)
from app.services.excel_export_service import generate_records_excel
from app.services.record_ocr_service import analyze_record_image
from app.services.record_upload_service import create_record_batch_from_uploads

router = APIRouter(prefix="/api/record-batches", tags=["record-batches"])


@router.post("/upload", response_model=RecordBatchUploadResponse)
async def upload_record_batch(db: Annotated[Session, Depends(get_db)], files: list[UploadFile] = File(...)):
    try:
        batch = await create_record_batch_from_uploads(db, files)
        db.commit()
        db.refresh(batch)
        return RecordBatchUploadResponse(batch_id=batch.id, batch_code=batch.batch_code, total_images=batch.total_images, status=batch.status)
    except Exception:
        db.rollback()
        raise


@router.post("/{batch_id}/analyze", response_model=RecordBatchAnalyzeResponse)
def analyze_record_batch(batch_id: int, db: Annotated[Session, Depends(get_db)]):
    batch = _get_batch(db, batch_id)
    if batch.status == "completed":
        raise HTTPException(status_code=400, detail="Batch already finalized. Upload a new batch to analyze again.")

    images = list(db.scalars(select(UploadedRecordImage).where(UploadedRecordImage.batch_id == batch.id).order_by(UploadedRecordImage.id)))
    if not images:
        raise HTTPException(status_code=400, detail="No images found for this batch")

    try:
        batch.status = "processing"
        db.execute(delete(ExtractedRecordRow).where(ExtractedRecordRow.batch_id == batch.id, ExtractedRecordRow.is_final.is_(False)))
        db.flush()
        created_rows: list[ExtractedRecordRow] = []
        row_number = 1

        for image in images:
            image.status = "processing"
            extracted_rows = analyze_record_image(image.file_path)
            for extracted in extracted_rows:
                row = ExtractedRecordRow(batch_id=batch.id, image_id=image.id, row_number=row_number, **extracted)
                db.add(row)
                created_rows.append(row)
                row_number += 1
            image.status = "review_pending"

        batch.total_rows = len(created_rows)
        batch.status = "review_pending"
        db.commit()
        db.refresh(batch)
        rows = list(db.scalars(select(ExtractedRecordRow).where(ExtractedRecordRow.batch_id == batch.id).order_by(ExtractedRecordRow.row_number, ExtractedRecordRow.id)))
        return RecordBatchAnalyzeResponse(batch=batch, rows=rows)
    except Exception:
        db.rollback()
        failed_batch = db.get(RecordBatch, batch_id)
        if failed_batch:
            failed_batch.status = "failed"
            db.commit()
        raise


@router.get("/images/{image_id}/file")
def download_record_image(image_id: int, db: Annotated[Session, Depends(get_db)]):
    image = db.get(UploadedRecordImage, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Uploaded image not found")
    return FileResponse(image.file_path, media_type=image.mime_type, filename=image.original_name)


@router.get("/{batch_id}", response_model=RecordBatchDetail)
def get_record_batch(batch_id: int, db: Annotated[Session, Depends(get_db)]):
    statement = select(RecordBatch).where(RecordBatch.id == batch_id).options(selectinload(RecordBatch.images), selectinload(RecordBatch.rows))
    batch = db.scalars(statement).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Record batch not found")
    batch.images.sort(key=lambda image: image.id)
    batch.rows.sort(key=lambda row: (row.row_number, row.id))
    return batch


@router.put("/{batch_id}/rows", response_model=list[ExtractedRecordRowRead])
def update_record_batch_rows(batch_id: int, payload: ExtractedRecordRowsUpdate, db: Annotated[Session, Depends(get_db)]):
    batch = _get_batch(db, batch_id)
    existing_rows = {row.id: row for row in db.scalars(select(ExtractedRecordRow).where(ExtractedRecordRow.batch_id == batch.id))}
    incoming_ids = {row.id for row in payload.rows if row.id}

    try:
        for row_id, row in existing_rows.items():
            if row_id not in incoming_ids:
                db.delete(row)
        for index, item in enumerate(payload.rows, start=1):
            values = item.model_dump()
            row_id = values.pop("id", None)
            values["row_number"] = index
            values["is_reviewed"] = True
            if row_id and row_id in existing_rows:
                for field_name, value in values.items():
                    setattr(existing_rows[row_id], field_name, value)
            else:
                db.add(ExtractedRecordRow(batch_id=batch.id, **values))

        batch.total_rows = len(payload.rows)
        batch.status = "review_pending"
        db.commit()
        return list(db.scalars(select(ExtractedRecordRow).where(ExtractedRecordRow.batch_id == batch.id).order_by(ExtractedRecordRow.row_number, ExtractedRecordRow.id)))
    except Exception:
        db.rollback()
        raise


@router.post("/{batch_id}/finalize", response_model=RecordBatchFinalizeResponse)
def finalize_record_batch(batch_id: int, db: Annotated[Session, Depends(get_db)]):
    batch = _get_batch(db, batch_id)
    rows = list(db.scalars(select(ExtractedRecordRow).where(ExtractedRecordRow.batch_id == batch.id).order_by(ExtractedRecordRow.row_number, ExtractedRecordRow.id)))
    if not rows:
        raise HTTPException(status_code=400, detail="Add at least one reviewed row before finalizing")

    for index, row in enumerate(rows, start=1):
        row.row_number = index
        row.is_reviewed = True
        row.is_final = True
        row.extraction_confidence = 1.0
    batch.total_rows = len(rows)
    batch.excel_file_path = generate_records_excel(batch.id, rows)
    batch.status = "completed"
    db.commit()
    db.refresh(batch)
    return RecordBatchFinalizeResponse(batch=batch, excel_url=f"/api/record-batches/{batch.id}/excel")


@router.get("/{batch_id}/excel")
def download_record_batch_excel(batch_id: int, db: Annotated[Session, Depends(get_db)]):
    batch = _get_batch(db, batch_id)
    if not batch.excel_file_path:
        raise HTTPException(status_code=404, detail="Excel file has not been generated yet")
    return FileResponse(batch.excel_file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"record_batch_{batch.id}.xlsx")


@router.get("", response_model=RecordBatchListResponse)
def list_record_batches(db: Annotated[Session, Depends(get_db)], page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    total = db.scalar(select(func.count()).select_from(RecordBatch)) or 0
    statement = select(RecordBatch).order_by(RecordBatch.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return RecordBatchListResponse(items=list(db.scalars(statement)), total=total, page=page, page_size=page_size)


def _get_batch(db: Session, batch_id: int) -> RecordBatch:
    batch = db.get(RecordBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Record batch not found")
    return batch
