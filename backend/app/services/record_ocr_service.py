from dataclasses import dataclass
from pathlib import Path
import re
from statistics import mean

from PIL import Image, ImageFilter, ImageOps

RECORD_FIELDS = [
    "hospital_registration_no",
    "patient_name",
    "age",
    "provisional_diagnosis",
    "procedure_name",
    "final_diagnosis",
    "surgeon_name",
    "ot_number",
    "procedure_date",
    "start_time",
    "end_time",
    "anesthesia_type",
]

REGISTER_KEYWORDS = {
    "registration",
    "patient",
    "age",
    "sex",
    "procedure",
    "diagnosis",
    "surgeon",
    "anaesthesia",
    "anesthesia",
    "ot",
    "date",
    "time",
}

MIN_USABLE_CONFIDENCE = 0.50
MAX_NOISE_RATIO = 0.35

FIELD_LIMITS = {
    "hospital_registration_no": 120,
    "patient_name": 200,
    "age": 40,
    "surgeon_name": 200,
    "ot_number": 80,
    "procedure_date": 80,
    "start_time": 80,
    "end_time": 80,
    "anesthesia_type": 160,
}


@dataclass
class OCRCandidate:
    text: str
    confidence: float
    score: float


def analyze_record_image(image_path: str) -> list[dict]:
    candidate = extract_text_from_image(image_path)
    if candidate.confidence < MIN_USABLE_CONFIDENCE:
        return []

    rows = parse_table_rows(candidate.text)
    return [normalize_record_row(row, candidate.confidence) for row in rows]


def preprocess_image(image_path: str) -> list[Image.Image]:
    source = Path(image_path)
    variants: list[Image.Image] = []

    with Image.open(source) as image:
        base = ImageOps.exif_transpose(image)
        for angle in (0, 90, 270):
            rotated = base.rotate(angle, expand=True)
            grayscale = ImageOps.grayscale(rotated)
            autocontrast = ImageOps.autocontrast(grayscale)
            enlarged = autocontrast.resize((autocontrast.width * 2, autocontrast.height * 2))
            sharpened = enlarged.filter(ImageFilter.SHARPEN)
            variants.append(sharpened)
    return variants


def extract_text_from_image(image_path: str) -> OCRCandidate:
    try:
        import pytesseract
    except Exception:
        return OCRCandidate(text="", confidence=0.0, score=0.0)

    candidates: list[OCRCandidate] = []
    for image in preprocess_image(image_path):
        for psm in ("6", "11", "4"):
            config = f"--psm {psm}"
            text = pytesseract.image_to_string(image, config=config)
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            candidates.append(_build_candidate(text, data))

    return max(candidates, key=lambda item: item.score, default=OCRCandidate(text="", confidence=0.0, score=0.0))


def parse_table_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    for raw_line in text.splitlines():
        normalized_line = re.sub(r"\s{2,}", " | ", raw_line.strip())
        if not normalized_line or _looks_like_header(normalized_line):
            continue

        cells = [cell.strip(" |") for cell in re.split(r"\s*\|\s*|\t+", normalized_line) if cell.strip(" |")]
        if len(cells) < 3:
            continue
        if cells and re.fullmatch(r"\d+[\).]?", cells[0]):
            cells = cells[1:]

        row = _cells_to_row(cells)
        if _is_usable_row(row):
            rows.append(row)

    if rows:
        return rows

    return [row for row in _parse_loose_rows(text) if _is_usable_row(row)]


def normalize_record_row(row: dict, candidate_confidence: float) -> dict:
    normalized = {field: _truncate(field, _clean_cell(str(row.get(field) or ""))) for field in RECORD_FIELDS}
    populated = sum(1 for field in RECORD_FIELDS if normalized[field])
    completeness = populated / len(RECORD_FIELDS)
    normalized["sex"] = ""
    normalized["anesthetist_name"] = ""
    normalized["staff_name"] = ""
    normalized["extraction_confidence"] = round(
        min(0.95, max(0.0, (candidate_confidence * 0.75) + (completeness * 0.25))),
        2,
    )
    return normalized


def _build_candidate(text: str, data: dict) -> OCRCandidate:
    confidences = []
    for item in data.get("conf", []):
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            confidences.append(value)

    words = [word.strip() for word in text.split() if len(word.strip()) > 1]
    lower_text = text.lower()
    keyword_hits = sum(1 for keyword in REGISTER_KEYWORDS if keyword in lower_text)
    average_confidence = mean(confidences) / 100 if confidences else 0.0
    score = (len(words) * 0.02) + (keyword_hits * 0.25) + average_confidence
    return OCRCandidate(text=text, confidence=round(min(0.95, max(0.25, average_confidence)), 2), score=score)


def _cells_to_row(cells: list[str]) -> dict:
    row = {field: "" for field in RECORD_FIELDS}
    for field, value in zip(RECORD_FIELDS, cells, strict=False):
        row[field] = value
    return row


def _parse_loose_rows(text: str) -> list[dict]:
    rows: list[dict] = []
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or _looks_like_header(line):
            continue
        if re.match(r"^\d+\s*[\)\]]", line):
            if current_lines:
                rows.append(_cells_to_row(_tokenize_row(" ".join(current_lines))))
            current_lines = [re.sub(r"^\d+\s*[\)\]]\s*", "", line)]
            continue
        if current_lines:
            current_lines.append(line)

    if current_lines:
        rows.append(_cells_to_row(_tokenize_row(" ".join(current_lines))))
    return rows


def _tokenize_row(text: str) -> list[str]:
    parts = [part.strip(" |") for part in re.split(r"\s*\|\s*|\s{2,}", text) if part.strip(" |")]
    return parts[: len(RECORD_FIELDS)]


def _looks_like_header(line: str) -> bool:
    lowered = line.lower()
    return "patient" in lowered and ("procedure" in lowered or "diagnosis" in lowered)


def _is_usable_row(row: dict) -> bool:
    cleaned = {field: _clean_cell(str(row.get(field) or "")) for field in RECORD_FIELDS}
    values = [value for value in cleaned.values() if value]
    if len(values) < 3:
        return False

    registration = cleaned["hospital_registration_no"]
    has_registration = bool(re.search(r"\d", registration)) and _noise_ratio(registration) <= MAX_NOISE_RATIO
    has_person = _looks_like_text_value(cleaned["patient_name"])
    has_medical_value = any(
        _looks_like_text_value(cleaned[field])
        for field in ("provisional_diagnosis", "procedure_name", "final_diagnosis", "surgeon_name")
    )

    noisy_values = sum(1 for value in values if _noise_ratio(value) > MAX_NOISE_RATIO)
    if noisy_values > len(values) / 2:
        return False

    return has_registration and (has_person or has_medical_value)


def _looks_like_text_value(value: str) -> bool:
    if len(value) < 2 or _noise_ratio(value) > MAX_NOISE_RATIO:
        return False
    return bool(re.search(r"[A-Za-z]", value))


def _clean_cell(value: str) -> str:
    value = re.sub(r"[_|]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" -—=:;,.[](){}'\"\\/")
    return value.strip()


def _noise_ratio(value: str) -> float:
    compact = re.sub(r"\s+", "", value)
    if not compact:
        return 1.0
    noisy = sum(1 for char in compact if not char.isalnum() and char not in {"/", ".", "-", "&"})
    return noisy / len(compact)


def _truncate(field_name: str, value: str) -> str:
    limit = FIELD_LIMITS.get(field_name)
    if not limit:
        return value
    return value[:limit]
