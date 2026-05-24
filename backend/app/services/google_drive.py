from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.core.config import settings

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload_excel_to_drive(file_path: str) -> dict[str, str]:
    credentials = _credentials()
    service = build("drive", "v3", credentials=credentials)

    path = Path(file_path)
    metadata: dict[str, object] = {"name": path.name}
    if settings.google_drive_folder_id:
        metadata["parents"] = [settings.google_drive_folder_id]

    media = MediaFileUpload(str(path), mimetype=EXCEL_MIME_TYPE, resumable=False)
    uploaded = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    file_id = uploaded.get("id")
    if not file_id:
        raise HTTPException(status_code=502, detail="Google Drive upload did not return a file id")

    if settings.google_drive_share_with_link:
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute()
        uploaded = service.files().get(fileId=file_id, fields="id, webViewLink").execute()

    return {"driveFileId": file_id, "driveLink": uploaded.get("webViewLink", "")}


def _credentials() -> service_account.Credentials:
    if settings.google_drive_service_account_json:
        try:
            info = json.loads(settings.google_drive_service_account_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Invalid GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON") from exc
        return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

    credential_path = Path(settings.google_service_account_file)
    if credential_path.exists():
        return service_account.Credentials.from_service_account_file(str(credential_path), scopes=DRIVE_SCOPES)

    raise HTTPException(
        status_code=500,
        detail="Google Drive service account credentials are missing",
    )
