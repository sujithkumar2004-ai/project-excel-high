from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from uuid import uuid4

import cv2
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.excel_export import generate_ot_register_excel
from app.services.image_preprocess import preprocess_image
from app.services.ocr_service import ocr_cell
from app.services.table_detector import REGISTER_COLUMNS, detect_table_cells

router = APIRouter(prefix="/records", tags=["records"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class CellPayload(BaseModel):
    value: str | None = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertain: bool = True
    edited: bool = False


class SaveCorrectionsPayload(BaseModel):
    columns: list[str] = Field(default_factory=lambda: list(REGISTER_COLUMNS))
    rows: list[dict[str, CellPayload]] = Field(default_factory=list)


@router.post("/upload")
async def upload_record(image: UploadFile = File(...)):
    record_id = uuid4().hex
    record_dir = _record_dir(record_id)
    record_dir.mkdir(parents=True, exist_ok=True)

    image_path = await _save_upload(image, record_dir)
    preprocess = preprocess_image(image_path, record_dir)
    table = detect_table_cells(preprocess.processed_path, record_dir, REGISTER_COLUMNS)

    rows = []
    engines: list[str] = []
    cells_dir = record_dir / "cells"
    cells_dir.mkdir(exist_ok=True)
    for row in table.rows:
        payload_row: dict[str, dict] = {}
        for cell in row:
            cell_path = cells_dir / f"{cell.row_index:03d}_{cell.column_index + 1:02d}.png"
            cv2.imwrite(str(cell_path), cell.image)
            result = ocr_cell(cell.image)
            engines.append(result.engine)
            payload_row[cell.column_name] = {
                "value": result.value,
                "confidence": result.confidence,
                "uncertain": result.uncertain,
                "edited": False,
            }
        if _row_has_signal(payload_row):
            rows.append(payload_row)

    data = {
        "id": record_id,
        "columns": REGISTER_COLUMNS,
        "rows": rows,
        "summary": _summary(rows, engines),
        "image_url": f"/records/{record_id}/image",
        "processed_image_url": f"/records/{record_id}/processed-image",
        "processed_path": preprocess.processed_path,
        "created_at": datetime.utcnow().isoformat(),
    }
    _write_json(record_dir / "extracted.json", data)
    return data


@router.post("/{record_id}/save-corrections")
def save_corrections(record_id: str, payload: SaveCorrectionsPayload):
    record_dir = _existing_record_dir(record_id)
    extracted = _read_json(record_dir / "extracted.json")
    original_rows = extracted.get("rows") or []
    normalized_rows = []

    for row_index, incoming_row in enumerate(payload.rows):
        normalized_row = {}
        original_row = original_rows[row_index] if row_index < len(original_rows) and isinstance(original_rows[row_index], dict) else {}
        for column in REGISTER_COLUMNS:
            incoming_cell = incoming_row.get(column) or CellPayload()
            original_cell = original_row.get(column) if isinstance(original_row, dict) else {}
            original_value = str((original_cell or {}).get("value") or "").strip()
            value = str(incoming_cell.value or "").strip()
            edited = value != original_value
            normalized_row[column] = {
                "value": value,
                "confidence": incoming_cell.confidence,
                "uncertain": bool(incoming_cell.uncertain),
                "edited": edited or bool(incoming_cell.edited),
            }
        if _row_has_signal(normalized_row):
            normalized_rows.append(normalized_row)

    data = {
        **extracted,
        "columns": REGISTER_COLUMNS,
        "rows": normalized_rows,
        "summary": _summary(normalized_rows, [extracted.get("summary", {}).get("ocr_engine_used", "unknown")]),
        "saved_at": datetime.utcnow().isoformat(),
    }
    _write_json(record_dir / "reviewed.json", data)
    return data


@router.get("/{record_id}/export-excel")
def export_excel(record_id: str):
    record_dir = _existing_record_dir(record_id)
    reviewed_path = record_dir / "reviewed.json"
    if not reviewed_path.exists():
        raise HTTPException(status_code=400, detail="Save corrected data before exporting Excel")
    data = _read_json(reviewed_path)
    rows = data.get("rows") or []
    if not rows:
        raise HTTPException(status_code=400, detail="No corrected rows available for export")

    excel_path = generate_ot_register_excel(REGISTER_COLUMNS, rows, record_dir)
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(excel_path).name,
    )


@router.get("")
def list_records():
    root = _records_root()
    items = []
    for record_dir in sorted(root.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True):
        if not record_dir.is_dir():
            continue
        try:
            data = _read_json(_active_data_path(record_dir))
        except HTTPException:
            continue
        items.append(
            {
                "id": record_dir.name,
                "created_at": data.get("created_at"),
                "saved_at": data.get("saved_at"),
                "total_rows": len(data.get("rows") or []),
                "summary": data.get("summary") or {},
            }
        )
    return {"items": items}


@router.get("/{record_id}")
def get_record(record_id: str):
    record_dir = _existing_record_dir(record_id)
    return _read_json(_active_data_path(record_dir))


@router.get("/{record_id}/image")
def get_record_image(record_id: str):
    record_dir = _existing_record_dir(record_id)
    image_path = next(record_dir.glob("original.*"), None)
    if not image_path:
        raise HTTPException(status_code=404, detail="Original image not found")
    return FileResponse(image_path)


@router.get("/{record_id}/processed-image")
def get_processed_image(record_id: str):
    record_dir = _existing_record_dir(record_id)
    data = _read_json(record_dir / "extracted.json")
    processed_path = data.get("processed_path") or _first_file(record_dir, "*_processed.png")
    if not processed_path:
        raise HTTPException(status_code=404, detail="Processed image not found")
    return FileResponse(processed_path)


async def _save_upload(file: UploadFile, record_dir: Path) -> str:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

    suffix = Path(file.filename or "").suffix.lower() or ALLOWED_IMAGE_TYPES[content_type]
    if suffix == ".jpeg":
        suffix = ".jpg"
    if suffix not in {".jpg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {file.filename}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    image_path = record_dir / f"original{suffix}"
    size = 0
    with image_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                image_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"File too large: {file.filename}")
            output.write(chunk)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    return str(image_path)


def _summary(rows: list[dict], engines: list[str]) -> dict:
    confidences = [float(cell.get("confidence") or 0.0) for row in rows for cell in row.values()]
    uncertain_count = sum(1 for row in rows for cell in row.values() if cell.get("uncertain"))
    edited_count = sum(1 for row in rows for cell in row.values() if cell.get("edited"))
    engine = _most_common([engine for engine in engines if engine]) or "none"
    return {
        "total_rows": len(rows),
        "uncertain_cells_count": uncertain_count,
        "edited_cells_count": edited_count,
        "average_confidence": round(mean(confidences), 3) if confidences else 0.0,
        "ocr_engine_used": engine,
    }


def _row_has_signal(row: dict[str, dict]) -> bool:
    values = [str(cell.get("value") or "").strip() for cell in row.values()]
    meaningful = [value for value in values if value and value.lower() not in {"o", "oo", "0", "00"}]
    return len(meaningful) >= 1


def _most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return max(set(values), key=values.count)


def _records_root() -> Path:
    root = Path(settings.upload_dir) / "records_v2"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _record_dir(record_id: str) -> Path:
    return _records_root() / record_id


def _existing_record_dir(record_id: str) -> Path:
    if not record_id or Path(record_id).name != record_id:
        raise HTTPException(status_code=400, detail="Invalid record id")
    record_dir = _record_dir(record_id)
    if not record_dir.exists():
        raise HTTPException(status_code=404, detail="Record not found")
    return record_dir


def _active_data_path(record_dir: Path) -> Path:
    reviewed = record_dir / "reviewed.json"
    extracted = record_dir / "extracted.json"
    if reviewed.exists():
        return reviewed
    if extracted.exists():
        return extracted
    raise HTTPException(status_code=404, detail="Record data not found")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"{path.name} not found") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Stored record data is invalid: {path.name}") from exc


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _first_file(record_dir: Path, pattern: str) -> str | None:
    match = next(record_dir.glob(pattern), None)
    return str(match) if match else None
