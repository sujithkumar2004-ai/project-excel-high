from __future__ import annotations

from fastapi import APIRouter

from app.services.ml_dataset_service import dataset_stats, export_dataset

router = APIRouter(prefix="/ml/dataset", tags=["ml-dataset"])


@router.get("/export")
def export_ml_dataset() -> dict:
    return export_dataset()


@router.get("/stats")
def get_ml_dataset_stats() -> dict:
    return dataset_stats()
