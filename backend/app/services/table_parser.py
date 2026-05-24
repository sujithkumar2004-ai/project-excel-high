from __future__ import annotations

import re

DEFAULT_REGISTER_COLUMNS = [
    "S.No",
    "Hospital Registration No",
    "Name of Patient",
    "Age/Sex",
    "Provisional Diagnosis",
    "Name of Procedure",
    "Final Diagnosis",
    "Name of Surgeon / Anesthetist / Staff",
    "OT No",
    "Date",
    "Start Time",
    "End Time",
    "Type of Anesthesia",
]

HEADER_HINTS = {
    "s.no",
    "sno",
    "no",
    "name",
    "patient",
    "age",
    "sex",
    "diagnosis",
    "procedure",
    "surgeon",
    "anesthesia",
    "anaesthesia",
    "date",
    "time",
    "registration",
    "reg",
}


def parse_ocr_table(ocr_result: dict) -> dict:
    lines = _ocr_lines(ocr_result)
    table_lines = [_split_cells(line) for line in lines if line.strip()]
    table_lines = [cells for cells in table_lines if cells]

    if not table_lines:
        return {"columns": DEFAULT_REGISTER_COLUMNS, "rows": [], "rawText": ocr_result.get("text", "")}

    header_index = _find_header_index(table_lines)
    if header_index is not None and len(table_lines[header_index]) >= 2:
        columns = _clean_columns(table_lines[header_index])
        row_lines = table_lines[header_index + 1 :]
    else:
        widest = max(len(cells) for cells in table_lines)
        columns = DEFAULT_REGISTER_COLUMNS[: max(widest, 1)]
        row_lines = table_lines

    rows = [_normalize_row(columns, cells) for cells in row_lines]
    rows = [row for row in rows if any(value.strip() for value in row.values())]

    return {
        "columns": columns,
        "rows": rows,
        "rawText": ocr_result.get("text", ""),
    }


def _ocr_lines(ocr_result: dict) -> list[str]:
    lines = [str(item.get("text", "")).strip() for item in ocr_result.get("lines", []) if str(item.get("text", "")).strip()]
    if lines:
        return lines
    return [line.strip() for line in str(ocr_result.get("text", "")).splitlines() if line.strip()]


def _split_cells(line: str) -> list[str]:
    normalized = re.sub(r"\s{2,}", " | ", line.strip())
    cells = [cell.strip(" |:-") for cell in re.split(r"\s*\|\s*|\t+|,{2,}", normalized) if cell.strip(" |:-")]

    if len(cells) <= 1:
        cells = [cell.strip(" |:-") for cell in re.split(r"\s{2,}", line.strip()) if cell.strip(" |:-")]

    if len(cells) <= 1 and re.match(r"^\d+[\).]?\s+", line):
        pieces = re.split(r"\s+", line, maxsplit=8)
        cells = [piece.strip(" |:-") for piece in pieces if piece.strip(" |:-")]

    return cells


def _find_header_index(lines: list[list[str]]) -> int | None:
    best_index: int | None = None
    best_score = 0
    for index, cells in enumerate(lines[:5]):
        lowered = " ".join(cells).lower()
        score = sum(1 for hint in HEADER_HINTS if hint in lowered)
        if score > best_score:
            best_score = score
            best_index = index
    return best_index if best_score >= 2 else None


def _clean_columns(cells: list[str]) -> list[str]:
    columns: list[str] = []
    seen: dict[str, int] = {}
    for index, cell in enumerate(cells, start=1):
        value = re.sub(r"\s+", " ", cell).strip() or f"Column {index}"
        count = seen.get(value, 0)
        seen[value] = count + 1
        columns.append(value if count == 0 else f"{value} {count + 1}")
    return columns


def _normalize_row(columns: list[str], cells: list[str]) -> dict[str, str]:
    cleaned = [re.sub(r"\s+", " ", cell).strip() for cell in cells]
    if cleaned and re.fullmatch(r"\d+[\).]?", cleaned[0]) and columns and columns[0].lower() not in {"s.no", "sno", "no"}:
        cleaned = cleaned[1:]
    cleaned = cleaned[: len(columns)]
    cleaned.extend([""] * (len(columns) - len(cleaned)))
    return dict(zip(columns, cleaned, strict=False))
