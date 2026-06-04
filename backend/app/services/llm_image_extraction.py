from __future__ import annotations

import base64
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field

from app.core.config import settings


class ExtractionError(Exception):
    pass


class ExtractedField(BaseModel):
    name: str
    value: str


class ExtractedRow(BaseModel):
    values: list[ExtractedField] = Field(default_factory=list)


class ModelExtraction(BaseModel):
    extracted_text: str
    rows: list[ExtractedRow] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)


async def extract_visible_data(image_bytes: bytes, content_type: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ExtractionError("OPENAI_API_KEY is missing. Add it to backend/.env and restart the backend.")

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:{content_type};base64,{encoded_image}"
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.responses.parse(
            model=settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Extract visible data from the provided image accurately. "
                        "Preserve the original reading order in extracted_text. "
                        "For tabular content, return each visible row and use the visible column names "
                        "as field names. For standalone labels or values, return them in fields. "
                        "Do not invent missing or unreadable values; use an empty string instead."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Extract the visible content from this image."},
                        {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                    ],
                },
            ],
            text_format=ModelExtraction,
        )
    except OpenAIError as exc:
        raise ExtractionError(f"OpenAI extraction failed: {exc}") from exc
    except Exception as exc:
        raise ExtractionError(f"OpenAI extraction failed: {exc}") from exc

    parsed = response.output_parsed
    if parsed is None:
        raise ExtractionError("OpenAI extraction failed: the model returned no structured data.")

    return {
        "extracted_text": parsed.extracted_text,
        "rows": [_fields_to_dict(row.values) for row in parsed.rows],
        "fields": _fields_to_dict(parsed.fields),
    }


def _fields_to_dict(fields: list[ExtractedField]) -> dict[str, str]:
    return {field.name: field.value for field in fields if field.name.strip()}
