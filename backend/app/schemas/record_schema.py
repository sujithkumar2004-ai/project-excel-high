from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ExtractedRecordRowBase(BaseModel):
    hospital_registration_no: str | None = ""
    patient_name: str | None = ""
    age: str | None = ""
    sex: str | None = ""
    provisional_diagnosis: str | None = ""
    procedure_name: str | None = ""
    final_diagnosis: str | None = ""
    surgeon_name: str | None = ""
    anesthetist_name: str | None = ""
    staff_name: str | None = ""
    ot_number: str | None = ""
    procedure_date: str | None = ""
    start_time: str | None = ""
    end_time: str | None = ""
    anesthesia_type: str | None = ""
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractedRecordRowUpsert(ExtractedRecordRowBase):
    id: int | None = None
    image_id: int | None = None
    row_number: int = 1
    is_reviewed: bool = True


class ExtractedRecordRowsUpdate(BaseModel):
    rows: list[ExtractedRecordRowUpsert]


class UploadedRecordImageRead(ORMModel):
    id: int
    batch_id: int
    file_name: str
    file_path: str
    original_name: str
    mime_type: str
    file_size: int
    status: str
    created_at: datetime


class ExtractedRecordRowRead(ORMModel, ExtractedRecordRowBase):
    id: int
    batch_id: int
    image_id: int | None
    row_number: int
    is_reviewed: bool
    is_final: bool
    created_at: datetime
    updated_at: datetime


class RecordBatchRead(ORMModel):
    id: int
    batch_code: str
    total_images: int
    total_rows: int
    status: str
    excel_file_path: str | None
    created_at: datetime
    updated_at: datetime


class RecordBatchDetail(RecordBatchRead):
    images: list[UploadedRecordImageRead] = Field(default_factory=list)
    rows: list[ExtractedRecordRowRead] = Field(default_factory=list)


class RecordBatchUploadResponse(BaseModel):
    batch_id: int
    batch_code: str
    total_images: int
    status: str


class RecordBatchAnalyzeResponse(BaseModel):
    batch: RecordBatchRead
    rows: list[ExtractedRecordRowRead]


class RecordBatchFinalizeResponse(BaseModel):
    batch: RecordBatchRead
    excel_url: str


class RecordBatchListResponse(BaseModel):
    items: list[RecordBatchRead]
    total: int
    page: int
    page_size: int
