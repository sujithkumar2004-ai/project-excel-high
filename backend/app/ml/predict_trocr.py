from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import settings


@dataclass(frozen=True)
class TrOCRPrediction:
    text: str
    confidence: float
    model_path: str


def predict_cell(image: np.ndarray | str | Path) -> TrOCRPrediction | None:
    model = _load_local_model()
    if model is None:
        return None

    processor, vision_model, torch = model
    try:
        pil_image = _to_pil(image)
        pixel_values = processor(images=pil_image, return_tensors="pt").pixel_values
        with torch.no_grad():
            generated_ids = vision_model.generate(pixel_values, max_new_tokens=64)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    except Exception:
        return None

    if not text:
        return None
    return TrOCRPrediction(text=text, confidence=0.80, model_path=_model_dir_setting())


@lru_cache(maxsize=1)
def _load_local_model():
    model_dir = Path(_model_dir_setting())
    if not model_dir.exists():
        return None
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except Exception:
        return None
    try:
        processor = TrOCRProcessor.from_pretrained(model_dir, local_files_only=True)
        model = VisionEncoderDecoderModel.from_pretrained(model_dir, local_files_only=True)
        model.eval()
    except Exception:
        return None
    return processor, model, torch


def _model_dir_setting() -> str:
    return str(getattr(settings, "trocr_finetuned_model_dir", "models/trocr-ot-register"))


def _to_pil(image: np.ndarray | str | Path) -> Image.Image:
    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image).convert("RGB")
        return Image.fromarray(image[:, :, ::-1]).convert("RGB")
    return Image.open(image).convert("RGB")
