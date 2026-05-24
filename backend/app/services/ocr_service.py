from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean

import cv2
import numpy as np

from app.services.image_preprocess import prepare_cell_for_ocr


@dataclass(frozen=True)
class OCRCellResult:
    value: str
    confidence: float
    uncertain: bool
    engine: str


LOW_CONFIDENCE_THRESHOLD = 0.72


def ocr_cell(cell_image: np.ndarray) -> OCRCellResult:
    prepared = prepare_cell_for_ocr(cell_image)
    for reader in (_ocr_with_paddle, _ocr_with_tesseract, _ocr_with_easyocr):
        result = reader(prepared)
        if result is not None:
            value, confidence, engine = result
            cleaned = _clean_text(value)
            confidence = max(0.0, min(1.0, confidence))
            if confidence <= 0.01 and cleaned.lower() in {"o", "oo", "0", "00"}:
                cleaned = ""
            return OCRCellResult(value=cleaned, confidence=round(confidence, 3), uncertain=_is_uncertain(cleaned, confidence), engine=engine)
    return OCRCellResult(value="", confidence=0.0, uncertain=True, engine="none")


def _ocr_with_paddle(image: np.ndarray) -> tuple[str, float, str] | None:
    try:
        result = _paddle_ocr().ocr(image)
    except Exception:
        return None

    texts: list[str] = []
    confidences: list[float] = []
    for page in result or []:
        if isinstance(page, dict):
            for text, score in zip(page.get("rec_texts") or [], page.get("rec_scores") or [], strict=False):
                if str(text).strip():
                    texts.append(str(text).strip())
                    confidences.append(float(score))
            continue
        for item in page or []:
            if len(item) < 2:
                continue
            text = str(item[1][0]).strip()
            if text:
                texts.append(text)
                confidences.append(float(item[1][1]))

    if not texts:
        return "", 0.0, "paddleocr"
    return " ".join(texts), mean(confidences) if confidences else 0.0, "paddleocr"


def _ocr_with_tesseract(image: np.ndarray) -> tuple[str, float, str] | None:
    try:
        import pytesseract
    except Exception:
        return None

    best_text = ""
    best_confidence = 0.0
    for psm in (7, 6, 11):
        config = f"--psm {psm}"
        try:
            text = pytesseract.image_to_string(image, config=config)
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        confidences = []
        for raw_confidence in data.get("conf", []):
            try:
                value = float(raw_confidence)
            except (TypeError, ValueError):
                continue
            if value >= 0:
                confidences.append(value / 100)
        confidence = mean(confidences) if confidences else 0.0
        if confidence > best_confidence or (text.strip() and not best_text):
            best_text = text
            best_confidence = confidence
    return best_text, best_confidence, "tesseract"


def _ocr_with_easyocr(image: np.ndarray) -> tuple[str, float, str] | None:
    try:
        import easyocr
    except Exception:
        return None

    try:
        result = _easyocr_reader().readtext(image, detail=1, paragraph=False)
    except Exception:
        return None
    texts = [str(item[1]).strip() for item in result if len(item) >= 3 and str(item[1]).strip()]
    confidences = [float(item[2]) for item in result if len(item) >= 3]
    return " ".join(texts), mean(confidences) if confidences else 0.0, "easyocr"


@lru_cache(maxsize=1)
def _paddle_ocr():
    from paddleocr import PaddleOCR

    try:
        return PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except ValueError:
        return PaddleOCR(lang="en", use_angle_cls=True, show_log=False)


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr

    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _clean_text(value: str) -> str:
    value = re.sub(r"[_|]+", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:=;,.[]{}'\"\\")


def _is_uncertain(value: str, confidence: float) -> bool:
    if not value:
        return True
    compact = re.sub(r"\s+", "", value)
    if compact:
        noisy = sum(1 for char in compact if not char.isalnum() and char not in {"/", ".", "-", "&", ":"})
        if noisy / len(compact) > 0.35:
            return True
    return confidence < LOW_CONFIDENCE_THRESHOLD
