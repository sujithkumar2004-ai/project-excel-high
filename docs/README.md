# Hospital Records Upload and Extraction Module

This module is implemented as a standalone FastAPI backend and Next.js App Router frontend inside `project-excel`.

## Backend Files

1. Database models
   - `backend/app/models/record_batch.py`
   - `backend/app/models/uploaded_record_image.py`
   - `backend/app/models/extracted_record_row.py`

2. Pydantic schemas
   - `backend/app/schemas/record_schema.py`

3. Services
   - `backend/app/services/record_upload_service.py`
   - `backend/app/services/record_ocr_service.py`
   - `backend/app/services/excel_export_service.py`

4. Router APIs
   - `backend/app/routers/record_router.py`

5. App registration
   - `backend/app/main.py`

## Frontend Files

1. Pages
   - `frontend/src/app/(dashboard)/records/upload/page.tsx`
   - `frontend/src/app/(dashboard)/records/review/[batchId]/page.tsx`
   - `frontend/src/app/(dashboard)/records/batches/page.tsx`
   - `frontend/src/app/(dashboard)/records/export/[batchId]/page.tsx`

2. Reusable components
   - `frontend/src/components/records/ImageUploader.tsx`
   - `frontend/src/components/records/BatchStatusCard.tsx`
   - `frontend/src/components/records/ExtractedRowsTable.tsx`
   - `frontend/src/components/records/ImagePreviewPanel.tsx`

3. API client
   - `frontend/src/lib/records-api.ts`

## API Endpoints

The backend router is available at `/api/record-batches/...`.

## Example Postman Requests

### Upload images

`POST http://127.0.0.1:8000/api/record-batches/upload`

Body: `form-data`

- Key: `files`, Type: File, select one or more `jpg`, `jpeg`, `png`, or `webp` images.

### Analyze batch

`POST http://127.0.0.1:8000/api/record-batches/{batch_id}/analyze`

### Get batch detail

`GET http://127.0.0.1:8000/api/record-batches/{batch_id}`

### Update reviewed rows

`PUT http://127.0.0.1:8000/api/record-batches/{batch_id}/rows`

```json
{
  "rows": [
    {
      "id": 1,
      "image_id": 1,
      "row_number": 1,
      "hospital_registration_no": "UHID-1001",
      "patient_name": "Patient Name",
      "age": "42",
      "sex": "F",
      "provisional_diagnosis": "Appendicitis",
      "procedure_name": "Appendectomy",
      "final_diagnosis": "Acute appendicitis",
      "surgeon_name": "Dr Surgeon",
      "anesthetist_name": "Dr Anesthesia",
      "staff_name": "OT Staff",
      "ot_number": "OT-2",
      "procedure_date": "2026-04-30",
      "start_time": "10:00",
      "end_time": "11:15",
      "anesthesia_type": "General",
      "extraction_confidence": 0.76,
      "is_reviewed": true
    }
  ]
}
```

### Finalize batch

`POST http://127.0.0.1:8000/api/record-batches/{batch_id}/finalize`

### Download Excel

`GET http://127.0.0.1:8000/api/record-batches/{batch_id}/excel`

### List batches

`GET http://127.0.0.1:8000/api/record-batches?page=1&page_size=20`

## Example MySQL Table Creation

```sql
CREATE TABLE record_batches (
  id INT AUTO_INCREMENT PRIMARY KEY,
  batch_code VARCHAR(80) NOT NULL UNIQUE,
  total_images INT NOT NULL DEFAULT 0,
  total_rows INT NOT NULL DEFAULT 0,
  status VARCHAR(40) NOT NULL DEFAULT 'uploaded',
  excel_file_path VARCHAR(500) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_record_batches_batch_code (batch_code),
  INDEX ix_record_batches_status (status)
);

CREATE TABLE uploaded_record_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  batch_id INT NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  mime_type VARCHAR(120) NOT NULL,
  file_size INT NOT NULL DEFAULT 0,
  status VARCHAR(40) NOT NULL DEFAULT 'uploaded',
  created_at DATETIME NOT NULL,
  INDEX ix_uploaded_record_images_batch_id (batch_id),
  INDEX ix_uploaded_record_images_status (status),
  CONSTRAINT fk_uploaded_record_images_batch_id FOREIGN KEY (batch_id) REFERENCES record_batches(id)
);

CREATE TABLE extracted_record_rows (
  id INT AUTO_INCREMENT PRIMARY KEY,
  batch_id INT NOT NULL,
  image_id INT NULL,
  row_number INT NOT NULL DEFAULT 1,
  hospital_registration_no VARCHAR(120) NULL,
  patient_name VARCHAR(200) NULL,
  age VARCHAR(40) NULL,
  sex VARCHAR(40) NULL,
  provisional_diagnosis TEXT NULL,
  procedure_name TEXT NULL,
  final_diagnosis TEXT NULL,
  surgeon_name VARCHAR(200) NULL,
  anesthetist_name VARCHAR(200) NULL,
  staff_name VARCHAR(200) NULL,
  ot_number VARCHAR(80) NULL,
  procedure_date VARCHAR(80) NULL,
  start_time VARCHAR(80) NULL,
  end_time VARCHAR(80) NULL,
  anesthesia_type VARCHAR(160) NULL,
  extraction_confidence FLOAT NOT NULL DEFAULT 0,
  is_reviewed BOOL NOT NULL DEFAULT 0,
  is_final BOOL NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX ix_extracted_record_rows_batch_id (batch_id),
  INDEX ix_extracted_record_rows_image_id (image_id),
  CONSTRAINT fk_extracted_record_rows_batch_id FOREIGN KEY (batch_id) REFERENCES record_batches(id),
  CONSTRAINT fk_extracted_record_rows_image_id FOREIGN KEY (image_id) REFERENCES uploaded_record_images(id)
);
```

## Testing Steps

1. Install backend dependencies.
   - `pip install -r backend/requirements.txt`

2. Set MySQL in `.env`.
   - `DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/hospital_clinical_ai`

3. Start backend.
   - `cd backend`
   - `uvicorn app.main:app --reload`

4. Start frontend.
   - `cd frontend`
   - `npm install`
   - `npm run dev`

5. Open `/records/upload`.

6. Upload 2 or more register images and click `Analyze Records`.

7. On `/records/review/{batchId}`, edit extracted draft rows, add or remove rows, then click `Save Final Records`.

8. Download the Excel file and verify it contains all final rows from all uploaded images.

9. Check MySQL:
   - `record_batches.total_images` equals the number of uploaded images.
   - `uploaded_record_images` has one row per original image.
   - `extracted_record_rows` contains reviewed rows with `is_final = 1`.
