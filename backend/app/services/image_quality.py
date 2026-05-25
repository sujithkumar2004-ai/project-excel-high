from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from fastapi import HTTPException


@dataclass
class ImageQualityResult:
    valid: bool
    score: int
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float | bool | int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "score": self.score,
            "issues": self.issues,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }


def assess_image_quality(image_path: str) -> ImageQualityResult:
    image = cv2.imread(image_path)
    if image is None:
        raise HTTPException(status_code=400, detail="Unable to read uploaded image")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))

    issues: list[str] = []
    warnings: list[str] = []
    score = 100

    if blur_score < 20:
        issues.append("Image is too blurry for reliable table extraction")
        score -= 45
    elif blur_score < 75:
        warnings.append("Image is slightly blurry")
        score -= 18

    if brightness < 55:
        warnings.append("Image is dark")
        score -= 25
    elif brightness > 225:
        warnings.append("Image is overexposed")
        score -= 25

    if contrast < 22:
        warnings.append("Image contrast is too low")
        score -= 30
    elif contrast < 42:
        warnings.append("Low contrast")
        score -= 12

    metrics = {
        "blur_score": round(blur_score, 2),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "rotation_angle": 0.0,
        "table_detected": False,
        "table_detected_raw": False,
        "table_detected_processed": False,
        "low_quality": False,
        "horizontal_line_count": 0,
        "vertical_line_count": 0,
        "row_count": 0,
        "column_count": 0,
        "cell_count": 0,
    }
    return ImageQualityResult(valid=not issues and score >= 20, score=max(0, min(100, score)), issues=issues, warnings=warnings, metrics=metrics)


def finalize_quality(
    quality: ImageQualityResult,
    *,
    rotation_angle: float,
    table_detected_raw: bool,
    table_detected_processed: bool,
    partial_table_detected: bool,
    horizontal_line_count: int,
    vertical_line_count: int,
    row_count: int,
    column_count: int,
    cell_count: int,
) -> ImageQualityResult:
    metrics = dict(quality.metrics)
    metrics.update(
        {
            "rotation_angle": round(rotation_angle, 2),
            "table_detected": table_detected_processed or partial_table_detected or (horizontal_line_count >= 3 and vertical_line_count >= 3),
            "table_detected_raw": table_detected_raw,
            "table_detected_processed": table_detected_processed,
            "low_quality": horizontal_line_count >= 3 and vertical_line_count >= 3 and not table_detected_processed,
            "horizontal_line_count": horizontal_line_count,
            "vertical_line_count": vertical_line_count,
            "row_count": row_count,
            "column_count": column_count,
            "cell_count": cell_count,
        }
    )
    issues = list(quality.issues)
    warnings = list(quality.warnings)
    score = quality.score

    if not table_detected_raw:
        warnings.append("Raw table grid not detected, trying preprocessing")
        score -= 5

    if horizontal_line_count < 3 or vertical_line_count < 3:
        issues.append("Too few table lines were detected after preprocessing")
        score -= 45
    elif not table_detected_processed:
        warnings.append("Partial table grid detected. Please review carefully.")
        score -= 18

    if row_count < 1:
        issues.append("No table rows were detected")
        score -= 25
    if cell_count < 8:
        issues.append("Not enough table cells were detected")
        score -= 20

    deduped_issues = list(dict.fromkeys(issues))
    return ImageQualityResult(
        valid=not deduped_issues and score >= 45,
        score=max(0, min(100, score)),
        issues=deduped_issues,
        warnings=list(dict.fromkeys(warnings)),
        metrics=metrics,
    )
