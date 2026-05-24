from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from PIL import Image

from app.core.config import settings


def run_ocr(image_path: str) -> dict:
    engine = settings.ocr_engine.strip().lower()
    if engine == "paddle":
        return _run_paddleocr(image_path)
    if engine != "trocr":
        raise HTTPException(status_code=500, detail=f"Unsupported OCR_ENGINE: {settings.ocr_engine}")

    try:
        return _run_trocr(image_path)
    except HTTPException as trocr_error:
        try:
            fallback = _run_paddleocr(image_path)
            fallback["fallbackReason"] = trocr_error.detail
            return fallback
        except HTTPException as paddle_error:
            raise HTTPException(
                status_code=503,
                detail=f"TrOCR failed ({trocr_error.detail}); PaddleOCR fallback failed ({paddle_error.detail})",
            ) from paddle_error


def _run_trocr(image_path: str) -> dict:
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except Exception as exc:
        raise HTTPException(status_code=503, detail="TrOCR dependencies are not installed") from exc

    try:
        processor, model = _load_trocr_model()
        image = Image.open(image_path).convert("RGB")
        pixel_values = processor(images=image, return_tensors="pt").pixel_values
        with torch.no_grad():
            generated_ids = model.generate(pixel_values, max_new_tokens=512)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"TrOCR inference failed: {exc}") from exc

    return {
        "engine": "trocr",
        "text": text,
        "lines": [{"text": line.strip(), "confidence": None} for line in text.splitlines() if line.strip()],
    }


@lru_cache(maxsize=1)
def _load_trocr_model():
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    model_name = settings.trocr_model_name
    kwargs = {"local_files_only": settings.trocr_local_files_only}
    processor = TrOCRProcessor.from_pretrained(model_name, **kwargs)
    model = VisionEncoderDecoderModel.from_pretrained(model_name, **kwargs)
    model.eval()
    return processor, model


def _run_paddleocr(image_path: str) -> dict:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise HTTPException(status_code=503, detail="PaddleOCR dependencies are not installed") from exc

    try:
        ocr = _load_paddleocr()
        result = ocr.ocr(str(Path(image_path)), cls=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PaddleOCR inference failed: {exc}") from exc

    lines: list[dict] = []
    for page in result or []:
        for item in page or []:
            if len(item) < 2:
                continue
            text, confidence = item[1][0], float(item[1][1])
            lines.append({"text": text.strip() if confidence >= 0.55 else "unclear", "confidence": confidence})

    return {
        "engine": "paddleocr",
        "text": "\n".join(line["text"] for line in lines if line["text"]),
        "lines": lines,
    }


@lru_cache(maxsize=1)
def _load_paddleocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
