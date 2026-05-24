# Project Excel

Local hospital OT register image-to-Excel pipeline.

## Stack

- Backend: FastAPI
- Frontend: Next.js / React
- OCR: PaddleOCR / PaddlePaddle
- Table detection: OpenCV
- Excel export: openpyxl

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

PaddlePaddle must be available for your Python version. If installation fails, use a PaddlePaddle-supported Python runtime such as Python 3.10, 3.11, or 3.12.

## Frontend Setup

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api npm run dev
```

Open `http://localhost:3010/records/upload`.

## Flow

1. Upload a hospital OT register image.
2. Backend saves the original image under `backend/uploads/ot_register/{id}`.
3. OpenCV auto-rotates, deskews, enhances contrast, detects the printed grid, and splits rows/cells.
4. PaddleOCR reads each cell.
5. The fixed OT register columns are mapped to JSON.
6. Frontend shows an editable review table and highlights uncertain cells.
7. Corrected JSON is saved with `POST /save-data/{id}`.
8. Excel is exported with `GET /export-excel/{id}`.

## API

`POST /upload-image`

Multipart field: `image`

`GET /record/{id}`

Returns stored extracted or reviewed JSON.

`POST /save-data/{id}`

Saves corrected JSON.

`GET /export-excel/{id}`

Exports one sheet named `OT_Register`, freezes the header row, autosizes columns, and includes `confidence` and `uncertain_fields` at the end.
