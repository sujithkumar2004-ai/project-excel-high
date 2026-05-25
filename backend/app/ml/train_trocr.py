from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.services.ml_dataset_service import export_dataset


def train_trocr_model(output_dir: str | None = None) -> dict:
    """Skeleton entry point for future TrOCR fine-tuning on reviewed cell crops."""
    dataset = export_dataset()
    if dataset["total_cells"] == 0:
        raise HTTPException(status_code=400, detail="No corrected cell samples available for TrOCR training")

    target_dir = Path(output_dir or settings.trocr_finetuned_model_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    readme = target_dir / "README.md"
    readme.write_text(
        "This directory is reserved for a fine-tuned TrOCR model.\n"
        "Use datasets/ot_register/labels.csv and images/ as the supervised dataset.\n",
        encoding="utf-8",
    )
    return {
        "status": "not_trained",
        "message": "Training skeleton prepared. Add a GPU/CPU training job here when enough corrected samples exist.",
        "dataset": dataset,
        "model_dir": str(target_dir),
    }


if __name__ == "__main__":
    print(train_trocr_model())
