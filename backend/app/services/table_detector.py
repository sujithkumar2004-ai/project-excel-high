from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

import cv2
import numpy as np
from fastapi import HTTPException


@dataclass(frozen=True)
class TableCell:
    row_index: int
    column_index: int
    column_name: str
    bbox: tuple[int, int, int, int]
    image: np.ndarray


@dataclass(frozen=True)
class TableDetectionResult:
    columns: list[str]
    rows: list[list[TableCell]]
    debug_image_path: str | None = None
    debug_lines_path: str | None = None
    table_detected: bool = False
    partial_table_detected: bool = False
    horizontal_line_count: int = 0
    vertical_line_count: int = 0


REGISTER_COLUMNS = [
    "S.No",
    "UHID",
    "Patient Name",
    "Age/Sex",
    "Provisional Diagnosis",
    "Procedure",
    "Final Diagnosis",
    "Anaesthetist",
    "OT No",
    "Date",
    "Start Time",
    "End Time",
]


def detect_table_cells(image_path: str, output_dir: str | Path | None = None, columns: list[str] | None = None) -> TableDetectionResult:
    image = cv2.imread(image_path)
    if image is None:
        raise HTTPException(status_code=400, detail="Unable to read preprocessed table image")

    target_columns = columns or REGISTER_COLUMNS
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 35, -8)

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 30, 35), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 18, 24)))
    horizontal = cv2.dilate(cv2.erode(binary, horizontal_kernel, iterations=1), horizontal_kernel, iterations=2)
    vertical = cv2.dilate(cv2.erode(binary, vertical_kernel, iterations=1), vertical_kernel, iterations=2)

    hough_horizontal, hough_vertical = _hough_line_positions(binary, width, height)
    horizontal_lines = _merge_positions(
        sorted(horizontal_lines := _line_positions(horizontal, axis="horizontal", min_length=max(width * 0.25, 90), tolerance=10) + hough_horizontal),
        tolerance=12,
    )
    vertical_lines = _merge_positions(
        sorted(vertical_lines := _line_positions(vertical, axis="vertical", min_length=max(height * 0.15, 70), tolerance=10) + hough_vertical),
        tolerance=12,
    )
    horizontal_count = len(horizontal_lines)
    vertical_count = len(vertical_lines)
    full_grid = horizontal_count >= 6 and vertical_count >= min(len(target_columns), 8)
    partial_grid = horizontal_count >= 6 and vertical_count >= 5
    detected_horizontal_lines = list(horizontal_lines)
    detected_vertical_lines = list(vertical_lines)

    if len(vertical_lines) < len(target_columns) + 1:
        vertical_lines = _fallback_column_lines(width, len(target_columns))
    else:
        vertical_lines = _normalize_vertical_lines(vertical_lines, width, len(target_columns))

    if len(horizontal_lines) < 3:
        horizontal_lines = _fallback_row_lines(height)
    else:
        horizontal_lines = _normalize_horizontal_lines(horizontal_lines, height)

    row_bands = _data_row_bands(horizontal_lines, height)
    rows: list[list[TableCell]] = []
    for row_index, (top, bottom) in enumerate(row_bands, start=1):
        row_cells: list[TableCell] = []
        for column_index, column_name in enumerate(target_columns):
            left, right = vertical_lines[column_index], vertical_lines[column_index + 1]
            crop = _crop_cell(image, left, top, right, bottom)
            row_cells.append(TableCell(row_index=row_index, column_index=column_index, column_name=column_name, bbox=(left, top, right, bottom), image=crop))
        rows.append(row_cells)

    debug_lines_path = _save_line_debug(image, detected_horizontal_lines, detected_vertical_lines, output_dir)
    debug_image_path = _save_debug_image(image, rows, output_dir)
    return TableDetectionResult(
        columns=target_columns,
        rows=rows,
        debug_image_path=debug_image_path,
        debug_lines_path=debug_lines_path,
        table_detected=full_grid,
        partial_table_detected=partial_grid,
        horizontal_line_count=horizontal_count,
        vertical_line_count=vertical_count,
    )


def detect_table_grid(image_path: str) -> tuple[bool, int, int]:
    image = cv2.imread(image_path)
    if image is None:
        return False, 0, 0
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 35, -8)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(width // 30, 35), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(height // 18, 24)))
    horizontal = cv2.dilate(cv2.erode(binary, horizontal_kernel, iterations=1), horizontal_kernel, iterations=2)
    vertical = cv2.dilate(cv2.erode(binary, vertical_kernel, iterations=1), vertical_kernel, iterations=2)
    hough_horizontal, hough_vertical = _hough_line_positions(binary, width, height)
    horizontal_count = len(_merge_positions(_line_positions(horizontal, "horizontal", max(width * 0.25, 90), 10) + hough_horizontal, 12))
    vertical_count = len(_merge_positions(_line_positions(vertical, "vertical", max(height * 0.15, 70), 10) + hough_vertical, 12))
    return horizontal_count >= 6 and vertical_count >= 5, horizontal_count, vertical_count


def _line_positions(mask: np.ndarray, axis: str, min_length: float, tolerance: int) -> list[int]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    positions: list[int] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if axis == "horizontal" and width >= min_length and height <= 24:
            positions.append(y + height // 2)
        if axis == "vertical" and height >= min_length and width <= 24:
            positions.append(x + width // 2)
    return _merge_positions(sorted(positions), tolerance=tolerance)


def _merge_positions(values: list[int], tolerance: int) -> list[int]:
    if not values:
        return []
    groups: list[list[int]] = [[values[0]]]
    for value in values[1:]:
        if value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [round(sum(group) / len(group)) for group in groups]


def _hough_line_positions(binary: np.ndarray, width: int, height: int) -> tuple[list[int], list[int]]:
    edges = cv2.Canny(binary, 50, 150, apertureSize=3)
    min_line = max(50, min(width, height) // 5)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=70, minLineLength=min_line, maxLineGap=18)
    horizontal: list[int] = []
    vertical: list[int] = []
    if lines is None:
        return horizontal, vertical
    for line in lines[:, 0]:
        x1, y1, x2, y2 = [int(value) for value in line]
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx > width * 0.2 and dy <= max(10, dx * 0.08):
            horizontal.append(round((y1 + y2) / 2))
        elif dy > height * 0.15 and dx <= max(10, dy * 0.08):
            vertical.append(round((x1 + x2) / 2))
    return horizontal, vertical


def _normalize_vertical_lines(lines: list[int], width: int, column_count: int) -> list[int]:
    lines = sorted({max(0, min(width, line)) for line in lines})
    if not lines or lines[0] > width * 0.03:
        lines.insert(0, 0)
    if width - lines[-1] > width * 0.03:
        lines.append(width)
    if len(lines) == column_count + 1:
        return lines

    expected = _fallback_column_lines(width, column_count)
    selected = []
    tolerance = max(width * 0.035, 16)
    for index, expected_line in enumerate(expected):
        if index in {0, len(expected) - 1}:
            selected.append(expected_line)
            continue
        nearby = [line for line in lines if abs(line - expected_line) <= tolerance]
        selected.append(min(nearby, key=lambda line: abs(line - expected_line)) if nearby else expected_line)
    return sorted(selected)


def _normalize_horizontal_lines(lines: list[int], height: int) -> list[int]:
    normalized = sorted({max(0, min(height, line)) for line in lines})
    if not normalized or normalized[0] > 10:
        normalized.insert(0, 0)
    if height - normalized[-1] > 10:
        normalized.append(height)
    return normalized


def _fallback_column_lines(width: int, column_count: int) -> list[int]:
    return [round(width * index / column_count) for index in range(column_count + 1)]


def _fallback_row_lines(height: int) -> list[int]:
    estimated_total_rows = 13
    return [round(height * index / estimated_total_rows) for index in range(estimated_total_rows + 1)]


def _data_row_bands(lines: list[int], height: int) -> list[tuple[int, int]]:
    bands = [(top, bottom) for top, bottom in zip(lines, lines[1:], strict=False) if bottom - top >= 18]
    if not bands:
        return []

    heights = [bottom - top for top, bottom in bands]
    typical_height = median(heights)
    data_bands = []
    for index, (top, bottom) in enumerate(bands):
        band_height = bottom - top
        if index == 0 and (band_height > typical_height * 1.2 or top < height * 0.18):
            continue
        if band_height < max(18, typical_height * 0.35):
            continue
        data_bands.append((top, bottom))

    if data_bands:
        return data_bands
    return bands[1:] if len(bands) > 1 else bands


def _crop_cell(image: np.ndarray, left: int, top: int, right: int, bottom: int) -> np.ndarray:
    height, width = image.shape[:2]
    cell_width = max(1, right - left)
    cell_height = max(1, bottom - top)
    pad_x = max(3, round(cell_width * 0.04))
    pad_y = max(3, round(cell_height * 0.08))
    crop = image[max(0, top + pad_y) : min(height, bottom - pad_y), max(0, left + pad_x) : min(width, right - pad_x)]
    if crop.size == 0:
        return image[max(0, top) : min(height, bottom), max(0, left) : min(width, right)]
    return crop


def _save_debug_image(image: np.ndarray, rows: list[list[TableCell]], output_dir: str | Path | None) -> str | None:
    if output_dir is None:
        return None
    debug_dir = _debug_dir(output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    overlay = image.copy()
    for row in rows:
        for cell in row:
            left, top, right, bottom = cell.bbox
            cv2.rectangle(overlay, (left, top), (right, bottom), (0, 180, 255), 1)
            if cell.column_index == 0:
                cv2.putText(overlay, str(cell.row_index), (left + 4, max(top + 16, 16)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 180), 1)
    path = debug_dir / "detected_cells.jpg"
    cv2.imwrite(str(path), overlay)
    return str(path)


def _save_line_debug(image: np.ndarray, horizontal_lines: list[int], vertical_lines: list[int], output_dir: str | Path | None) -> str | None:
    if output_dir is None:
        return None
    debug_dir = _debug_dir(output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    overlay = image.copy()
    height, width = image.shape[:2]
    for y in horizontal_lines:
        cv2.line(overlay, (0, y), (width, y), (0, 180, 0), 2)
    for x in vertical_lines:
        cv2.line(overlay, (x, 0), (x, height), (0, 80, 255), 2)
    path = debug_dir / "detected_lines.jpg"
    cv2.imwrite(str(path), overlay)
    return str(path)


def _debug_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir)
    if path.name and path.parent.name == "records_v2":
        return path.parent.parent / "debug" / path.name
    return path / "debug"
