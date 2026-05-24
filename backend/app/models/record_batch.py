from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecordBatch(Base):
    __tablename__ = "record_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    total_images: Mapped[int] = mapped_column(default=0)
    total_rows: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(40), default="uploaded", index=True)
    excel_file_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[list["UploadedRecordImage"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    rows: Mapped[list["ExtractedRecordRow"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
