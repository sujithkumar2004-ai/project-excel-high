from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtractedRecordRow(Base):
    __tablename__ = "extracted_record_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("record_batches.id"), index=True)
    image_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_record_images.id"), index=True)
    row_number: Mapped[int] = mapped_column(default=1)
    hospital_registration_no: Mapped[str | None] = mapped_column(String(120))
    patient_name: Mapped[str | None] = mapped_column(String(200))
    age: Mapped[str | None] = mapped_column(String(40))
    sex: Mapped[str | None] = mapped_column(String(40))
    provisional_diagnosis: Mapped[str | None] = mapped_column(Text)
    procedure_name: Mapped[str | None] = mapped_column(Text)
    final_diagnosis: Mapped[str | None] = mapped_column(Text)
    surgeon_name: Mapped[str | None] = mapped_column(String(200))
    anesthetist_name: Mapped[str | None] = mapped_column(String(200))
    staff_name: Mapped[str | None] = mapped_column(String(200))
    ot_number: Mapped[str | None] = mapped_column(String(80))
    procedure_date: Mapped[str | None] = mapped_column(String(80))
    start_time: Mapped[str | None] = mapped_column(String(80))
    end_time: Mapped[str | None] = mapped_column(String(80))
    anesthesia_type: Mapped[str | None] = mapped_column(String(160))
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    batch: Mapped["RecordBatch"] = relationship(back_populates="rows")
    image: Mapped["UploadedRecordImage | None"] = relationship(back_populates="rows")
