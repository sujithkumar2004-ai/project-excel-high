from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.fixed_ot_register_service import (
    COLUMN_KEYS,
    create_fixed_ot_record,
    export_fixed_ot_excel,
    get_fixed_ot_record,
    save_fixed_ot_data,
)

router = APIRouter(tags=["fixed-ot-register"])


class OTRegisterRow(BaseModel):
    s_no: str | None = None
    ipd_hospital_registration_no: str | None = None
    patient_name: str | None = None
    age_sex: str | None = None
    provisional_diagnosis: str | None = None
    procedure_name: str | None = None
    final_diagnosis: str | None = None
    surgeon_anaesthetist_staff: str | None = None
    ot: str | None = None
    date_of_procedure: str | None = None
    surgery_time: str | None = None
    end_time: str | None = None
    type_of_anaesthesia: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertain_fields: list[str] = Field(default_factory=list)


class OTRegisterData(BaseModel):
    document_type: str = "hospital_ot_register"
    columns: list[str] = Field(default_factory=lambda: list(COLUMN_KEYS))
    rows: list[OTRegisterRow] = Field(default_factory=list)


class OTRegisterRecordResponse(BaseModel):
    id: str
    imagePath: str
    processedImagePath: str
    data: OTRegisterData


@router.post("/upload-image", response_model=OTRegisterRecordResponse)
async def upload_image(image: UploadFile = File(...)):
    return await create_fixed_ot_record(image)


@router.get("/record/{record_id}", response_model=OTRegisterRecordResponse)
def get_record(record_id: str):
    return get_fixed_ot_record(record_id)


@router.post("/save-data/{record_id}", response_model=OTRegisterRecordResponse)
def save_data(record_id: str, payload: OTRegisterData):
    return save_fixed_ot_data(record_id, payload.model_dump())


@router.get("/export-excel/{record_id}")
def export_excel(record_id: str):
    excel_path = export_fixed_ot_excel(record_id)
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="OT_Register.xlsx",
    )
