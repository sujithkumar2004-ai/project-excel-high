from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.excel_export import generate_excel
from app.services.google_drive import upload_excel_to_drive
from app.services.image_preprocess import preprocess_image
from app.services.ocr_trocr import run_ocr
from app.services.table_parser import parse_ocr_table

router = APIRouter(prefix="/api/local-register", tags=["local-register"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class DraftResponse(BaseModel):
    success: bool = True
    imagePath: str
    processedImagePath: str
    imageUrl: str
    processedImageUrl: str
    ocrEngine: str
    skewAngle: float
    columns: list[str]
    rows: list[dict[str, str]]
    rawText: str


class ExportRequest(BaseModel):
    columns: list[str] = Field(min_length=1)
    rows: list[dict[str, str]] = Field(default_factory=list)


class ExportResponse(BaseModel):
    success: bool = True
    excelPath: str
    downloadUrl: str
    driveFileId: str
    driveLink: str


@router.post("/draft", response_model=DraftResponse)
async def create_ocr_draft(image: UploadFile = File(...)):
    original_path = await _save_original_image(image)
    processed = preprocess_image(original_path)
    ocr_result = run_ocr(processed.processed_path)
    parsed = parse_ocr_table(ocr_result)

    return DraftResponse(
        imagePath=original_path,
        processedImagePath=processed.processed_path,
        imageUrl=f"/api/local-register/files/{Path(original_path).name}",
        processedImageUrl=f"/api/local-register/files/{Path(processed.processed_path).name}",
        ocrEngine=ocr_result.get("engine", settings.ocr_engine),
        skewAngle=processed.skew_angle,
        columns=parsed["columns"],
        rows=parsed["rows"],
        rawText=parsed["rawText"],
    )


@router.post("/export", response_model=ExportResponse)
def export_reviewed_register(payload: ExportRequest):
    columns = [column.strip() for column in payload.columns if column.strip()]
    if not columns:
        raise HTTPException(status_code=400, detail="At least one reviewed column is required")

    normalized_rows = [_normalize_row(columns, row) for row in payload.rows]
    excel_path = generate_excel(columns, normalized_rows)
    drive = upload_excel_to_drive(excel_path)

    return ExportResponse(
        excelPath=excel_path,
        downloadUrl=f"/api/local-register/excel/{Path(excel_path).name}",
        driveFileId=drive["driveFileId"],
        driveLink=drive["driveLink"],
    )


@router.get("/excel/{file_name}")
def download_excel(file_name: str):
    if Path(file_name).name != file_name or not file_name.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid Excel file name")

    excel_path = Path(settings.export_dir) / file_name
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")

    return FileResponse(
        str(excel_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name,
    )


@router.get("/files/{file_name}")
def get_uploaded_file(file_name: str):
    if Path(file_name).name != file_name:
        raise HTTPException(status_code=400, detail="Invalid file name")

    for directory in (Path(settings.upload_dir) / "images", Path(settings.upload_dir) / "processed"):
        file_path = directory / file_name
        if file_path.exists():
            return FileResponse(str(file_path))

    raise HTTPException(status_code=404, detail="File not found")


async def _save_original_image(file: UploadFile) -> str:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")

    suffix = Path(file.filename or "").suffix.lower() or ALLOWED_IMAGE_TYPES[content_type]
    if suffix == ".jpeg":
        suffix = ".jpg"
    if suffix not in {".jpg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {file.filename}")

    output_dir = Path(settings.upload_dir) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{uuid4().hex}{suffix}"
    output_path.write_bytes(content)
    return str(output_path)


def _normalize_row(columns: list[str], row: dict[str, str]) -> dict[str, str]:
    return {column: str(row.get(column, "") or "") for column in columns}
