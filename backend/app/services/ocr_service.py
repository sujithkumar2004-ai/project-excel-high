from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from statistics import mean
from typing import Callable

import cv2
import numpy as np

from app.core.config import settings
from app.ml.predict_trocr import predict_cell
from app.services.image_preprocess import prepare_cell_for_ocr


@dataclass(frozen=True)
class OCRCellResult:
    value: str
    confidence: float
    uncertain: bool
    engine: str


LOW_CONFIDENCE_THRESHOLD = 0.72
OCRReader = Callable[[np.ndarray], tuple[str, float, str] | None]


def ocr_cell(cell_image: np.ndarray) -> OCRCellResult:
    if _looks_blank(cell_image):
        return OCRCellResult(value="", confidence=0.0, uncertain=True, engine=_primary_engine_name())

    trocr_prediction = predict_cell(cell_image)
    if trocr_prediction is not None:
        cleaned = _clean_text(trocr_prediction.text)
        confidence = max(0.0, min(1.0, trocr_prediction.confidence))
        return OCRCellResult(value=cleaned, confidence=round(confidence, 3), uncertain=_is_uncertain(cleaned, confidence), engine="trocr")

    prepared = prepare_cell_for_ocr(cell_image)
    for reader in _available_readers():
        result = reader(prepared)
        if result is not None:
            value, confidence, engine = result
            cleaned = _clean_text(value)
            confidence = max(0.0, min(1.0, confidence))
            if confidence <= 0.01 and cleaned.lower() in {"o", "oo", "0", "00"}:
                cleaned = ""
            return OCRCellResult(value=cleaned, confidence=round(confidence, 3), uncertain=_is_uncertain(cleaned, confidence), engine=engine)
    return OCRCellResult(value="", confidence=0.0, uncertain=True, engine="none")


def _looks_blank(image: np.ndarray) -> bool:
    if image.size == 0:
        return True
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    height, width = threshold.shape[:2]
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 2, 16), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 2, 12)))
    horizontal = cv2.dilate(cv2.erode(threshold, horizontal_kernel, iterations=1), horizontal_kernel, iterations=1)
    vertical = cv2.dilate(cv2.erode(threshold, vertical_kernel, iterations=1), vertical_kernel, iterations=1)
    content = cv2.bitwise_and(threshold, cv2.bitwise_not(cv2.bitwise_or(horizontal, vertical)))
    ink_ratio = cv2.countNonZero(content) / float(height * width)
    return ink_ratio < 0.004


@lru_cache(maxsize=1)
def _available_readers() -> tuple[OCRReader, ...]:
    readers: list[OCRReader] = []
    preferred_engine = settings.ocr_engine.strip().lower()
    if preferred_engine == "paddleocr" and _paddle_ocr() is not None:
        readers.append(_ocr_with_paddle)
    if _tesseract_available():
        readers.append(_ocr_with_tesseract)
    if preferred_engine == "easyocr" and _easyocr_reader() is not None:
        readers.append(_ocr_with_easyocr)
    return tuple(readers)


def _ocr_with_paddle(image: np.ndarray) -> tuple[str, float, str] | None:
    reader = _paddle_ocr()
    if reader is None:
        return None
    try:
        result = reader.ocr(image)
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
    pytesseract = _pytesseract()
    if pytesseract is None:
        return None

    best_text = ""
    best_confidence = 0.0
    for psm in (7, 6):
        config = f"--psm {psm}"
        try:
            text = pytesseract.image_to_string(image, config=config, timeout=4)
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT, timeout=4)
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
    reader = _easyocr_reader()
    if reader is None:
        return None

    try:
        result = reader.readtext(image, detail=1, paragraph=False)
    except Exception:
        return None
    texts = [str(item[1]).strip() for item in result if len(item) >= 3 and str(item[1]).strip()]
    confidences = [float(item[2]) for item in result if len(item) >= 3]
    return " ".join(texts), mean(confidences) if confidences else 0.0, "easyocr"


@lru_cache(maxsize=1)
def _paddle_ocr():
    try:
        from paddleocr import PaddleOCR
    except Exception:
        return None

    try:
        return PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except Exception:
        try:
            return PaddleOCR(lang="en", use_angle_cls=True, show_log=False)
        except Exception:
            return None


@lru_cache(maxsize=1)
def _easyocr_reader():
    try:
        import easyocr
    except Exception:
        return None

    try:
        return easyocr.Reader(["en"], gpu=False, verbose=False)
    except Exception:
        return None


@lru_cache(maxsize=1)
def _pytesseract():
    try:
        import pytesseract
    except Exception:
        return None
    return pytesseract


@lru_cache(maxsize=1)
def _tesseract_available() -> bool:
    pytesseract = _pytesseract()
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def _primary_engine_name() -> str:
    engine = settings.ocr_engine.strip().lower()
    if engine in {"paddleocr", "easyocr", "tesseract"}:
        return engine
    return "none"


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
