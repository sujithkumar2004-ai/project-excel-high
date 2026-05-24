from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import HTTPException

from app.core.config import settings


@dataclass(frozen=True)
class PreprocessResult:
    original_path: str
    processed_path: str
    threshold_path: str
    table_path: str
    debug_paths: dict[str, str] = field(default_factory=dict)
    skew_angle: float = 0.0


def preprocess_image(original_path: str, output_dir: str | Path | None = None) -> PreprocessResult:
    image = cv2.imread(original_path)
    if image is None:
        raise HTTPException(status_code=400, detail="Unable to read uploaded image")

    target_dir = Path(output_dir) if output_dir else Path(settings.upload_dir) / "processed"
    target_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = target_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    oriented = _auto_orient(image)
    deskewed, angle = _deskew(oriented)
    table = _perspective_correct_table(deskewed)
    enhanced = _enhance_for_ocr(table)
    thresholded = _threshold_for_lines(enhanced)

    stem = Path(original_path).stem
    suffix = uuid4().hex[:8]
    processed_path = target_dir / f"{stem}_{suffix}_processed.png"
    threshold_path = target_dir / f"{stem}_{suffix}_threshold.png"
    table_path = target_dir / f"{stem}_{suffix}_table.png"

    _write_image(processed_path, enhanced)
    _write_image(threshold_path, thresholded)
    _write_image(table_path, table)
    _write_image(debug_dir / "oriented.png", oriented)
    _write_image(debug_dir / "deskewed.png", deskewed)

    return PreprocessResult(
        original_path=original_path,
        processed_path=str(processed_path),
        threshold_path=str(threshold_path),
        table_path=str(table_path),
        debug_paths={
            "oriented": str(debug_dir / "oriented.png"),
            "deskewed": str(debug_dir / "deskewed.png"),
        },
        skew_angle=round(angle, 2),
    )


def prepare_cell_for_ocr(crop: np.ndarray) -> np.ndarray:
    if crop.size == 0:
        return crop

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 12)

    height, width = binary.shape[:2]
    ink = cv2.bitwise_not(binary)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 2, 18), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 2, 12)))
    horizontal = cv2.dilate(cv2.erode(ink, horizontal_kernel, iterations=1), horizontal_kernel, iterations=1)
    vertical = cv2.dilate(cv2.erode(ink, vertical_kernel, iterations=1), vertical_kernel, iterations=1)
    lines = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((2, 2), np.uint8), iterations=1)
    binary[lines > 0] = 255

    binary = cv2.copyMakeBorder(binary, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    scale = 4 if max(binary.shape[:2]) < 900 else 2
    binary = cv2.resize(binary, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _auto_orient(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if height > width * 1.15:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return image


def _deskew(image: np.ndarray) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coordinates = np.column_stack(np.where(binary > 0))
    if coordinates.size == 0:
        return image, 0.0

    angle = cv2.minAreaRect(coordinates)[-1]
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90
    if abs(angle) < 0.35:
        return image, 0.0

    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width // 2, height // 2), angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, float(angle)


def _perspective_correct_table(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image

    image_area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        area = cv2.contourArea(contour)
        if area < image_area * 0.20:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4:
            return _four_point_transform(image, approx.reshape(4, 2).astype("float32"))
    return image


def _four_point_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    rect = _order_points(points)
    top_left, top_right, bottom_right, bottom_left = rect
    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    max_width = max(int(width_a), int(width_b), 1)
    max_height = max(int(height_a), int(height_b), 1)
    destination = np.array([[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image, matrix, (max_width, max_height), borderMode=cv2.BORDER_REPLICATE)


def _order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def _enhance_for_ocr(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    enhanced_l = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(l_channel)
    enhanced = cv2.cvtColor(cv2.merge((enhanced_l, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
    return cv2.fastNlMeansDenoisingColored(enhanced, None, 5, 5, 7, 21)


def _threshold_for_lines(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 10)


def _write_image(path: Path, image: np.ndarray) -> None:
    if not cv2.imwrite(str(path), image):
        raise HTTPException(status_code=500, detail=f"Failed to save image: {path.name}")
