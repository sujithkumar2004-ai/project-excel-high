# Project Excel

Secure image-to-Excel extraction using a Next.js frontend, FastAPI Python backend, and the OpenAI Responses API.

## Workflow

1. Login with the temporary credentials.
2. Select one image in the upload page.
3. Click **Analyze & Create Excel**.
4. The frontend uploads the image to the FastAPI backend.
5. The backend reads `OPENAI_API_KEY` from `backend/.env`, sends the image to OpenAI, extracts structured data, and creates an Excel workbook.
6. The frontend previews the extracted data and downloads the `.xlsx`.

All OpenAI requests happen in the backend. The API key is never sent to the browser.

## Backend Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `backend/.env` and replace the placeholder:

```dotenv
OPENAI_API_KEY=your_key_here
APP_LOGIN_USERNAME=SK001
APP_LOGIN_PASSWORD=SK001@123
```

Start the API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Frontend Setup

In a second terminal:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010/api npm run dev -- --hostname 127.0.0.1 --port 3010
```

Open `http://127.0.0.1:3010`.

## API

Temporary login:

```text
Login ID: SK001
Password: SK001@123
```

`POST /api/auth/login`

Returns a temporary bearer token used by the frontend.

`POST /api/extract-image`

Multipart field: `image`

Example response:

```json
{
  "success": true,
  "data": {
    "extracted_text": "",
    "rows": [],
    "fields": {}
  },
  "excel_filename": "image_extraction_xxx.xlsx",
  "excel_download_url": "/api/excel/image_extraction_xxx.xlsx"
}
```

`GET /api/excel/{filename}`

Downloads the generated workbook. Protected by the same login token.

The backend returns clear errors for missing login, a missing image, unsupported or empty uploads, an absent `OPENAI_API_KEY`, and OpenAI extraction failures.
