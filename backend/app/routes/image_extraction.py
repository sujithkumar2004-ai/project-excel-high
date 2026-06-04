from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.routes.auth import require_auth
from app.services.extracted_excel import create_extraction_workbook
from app.services.llm_image_extraction import ExtractionError, extract_visible_data

router = APIRouter(prefix="/api", tags=["image-extraction"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class ExtractionData(BaseModel):
    extracted_text: str = ""
    rows: list[dict[str, str]] = Field(default_factory=list)
    fields: dict[str, str] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    success: bool = True
    data: ExtractionData
    excel_filename: str
    excel_download_url: str


@router.post("/extract-image", response_model=ExtractionResponse)
async def extract_image(image: UploadFile | None = File(default=None), _username: str = Depends(require_auth)):
    if image is None:
        raise HTTPException(status_code=400, detail="Image is required")

    content_type = image.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use JPG, PNG, WebP, or GIF.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(image_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Image exceeds the {settings.max_upload_mb} MB upload limit")

    try:
        data: dict[str, Any] = await extract_visible_data(image_bytes, content_type)
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    excel_filename, _ = create_extraction_workbook(data)
    return ExtractionResponse(
        data=ExtractionData(**data),
        excel_filename=excel_filename,
        excel_download_url=f"/api/excel/{excel_filename}",
    )


@router.get("/excel/{filename}")
def download_excel(filename: str, _username: str = Depends(require_auth)):
    if not filename.endswith(".xlsx") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid Excel file name")

    file_path = Path(settings.export_dir) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")

    return FileResponse(
        str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Project_Excel_Extraction.xlsx",
    )
