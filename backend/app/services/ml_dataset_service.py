from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.config import settings

LABEL_COLUMNS = ["image_path", "column_name", "ocr_text", "corrected_text", "confidence", "record_id"]


def save_training_samples(record_id: str, rows: list[dict]) -> int:
    samples_path = _samples_path()
    samples_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0

    with samples_path.open("a", encoding="utf-8") as output:
        for row_index, row in enumerate(rows, start=1):
            for column_name, cell in row.items():
                corrected_text = str(cell.get("value") or "").strip()
                crop_path = str(cell.get("cell_crop_path") or "").strip()
                if not corrected_text or not crop_path:
                    continue
                sample = {
                    "record_id": record_id,
                    "row_index": row_index,
                    "column_name": column_name,
                    "image_crop_path": crop_path,
                    "ocr_text": str(cell.get("ocr_text") or cell.get("original_value") or ""),
                    "corrected_text": corrected_text,
                    "confidence": float(cell.get("confidence") or 0.0),
                    "created_at": datetime.utcnow().isoformat(),
                }
                output.write(json.dumps(sample, ensure_ascii=False) + "\n")
                count += 1
    return count


def export_dataset() -> dict:
    dataset_dir = Path(settings.upload_dir) / "datasets" / "ot_register"
    images_dir = dataset_dir / "images"
    labels_path = dataset_dir / "labels.csv"
    images_dir.mkdir(parents=True, exist_ok=True)

    samples = _deduplicated_samples()
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=dataset_dir) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        total = 0
        for index, sample in enumerate(samples, start=1):
            source = Path(str(sample.get("image_crop_path") or ""))
            if not source.exists():
                continue
            image_name = f"cell_{index:06d}{source.suffix.lower() or '.png'}"
            target = images_dir / image_name
            shutil.copy2(source, target)
            writer.writerow(
                {
                    "image_path": f"images/{image_name}",
                    "column_name": sample.get("column_name", ""),
                    "ocr_text": sample.get("ocr_text", ""),
                    "corrected_text": sample.get("corrected_text", ""),
                    "confidence": sample.get("confidence", 0.0),
                    "record_id": sample.get("record_id", ""),
                }
            )
            total += 1
        temp_path = Path(temp_file.name)

    temp_path.replace(labels_path)
    return {
        "dataset_dir": str(dataset_dir),
        "images_dir": str(images_dir),
        "labels_csv": str(labels_path),
        "total_cells": total,
    }


def dataset_stats() -> dict:
    samples = _deduplicated_samples()
    by_column: dict[str, int] = {}
    records = set()
    corrected = 0
    for sample in samples:
        column_name = str(sample.get("column_name") or "")
        by_column[column_name] = by_column.get(column_name, 0) + 1
        records.add(str(sample.get("record_id") or ""))
        if str(sample.get("corrected_text") or "").strip():
            corrected += 1
    return {
        "total_samples": len(samples),
        "corrected_samples": corrected,
        "record_count": len([record for record in records if record]),
        "by_column": by_column,
        "samples_path": str(_samples_path()),
    }


def _deduplicated_samples() -> list[dict]:
    path = _samples_path()
    if not path.exists():
        return []
    latest: dict[tuple[str, str, str], dict] = {}
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (str(sample.get("record_id") or ""), str(sample.get("row_index") or ""), str(sample.get("column_name") or ""))
            latest[key] = sample
    return list(latest.values())


def _samples_path() -> Path:
    return Path(settings.upload_dir) / "ml" / "corrections.jsonl"
