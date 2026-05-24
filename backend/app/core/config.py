from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Hospital Records Upload and Extraction"
    database_url: str = "mysql+pymysql://root:password@127.0.0.1:3306/project_excel"
    auto_create_tables: bool = False
    backend_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3010,http://127.0.0.1:3010"
    upload_dir: str = "uploads"
    export_dir: str = "exports"
    max_upload_mb: int = Field(default=25, ge=1, le=200)
    ocr_engine: str = "paddleocr"
    trocr_model_name: str = "microsoft/trocr-base-handwritten"
    trocr_local_files_only: bool = True
    google_sheet_id: str = ""
    google_sheet_worksheet: str = "Sheet1"
    google_service_account_file: str = "./service-account.json"
    google_drive_folder_id: str = ""
    google_drive_service_account_json: str = ""
    google_drive_share_with_link: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
