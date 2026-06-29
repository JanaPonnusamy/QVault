from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / "config" / ".env"),
        env_prefix="QVAULT_",
        extra="ignore",
    )

    app_name: str = "QVault"
    env: str = "development"
    log_level: str = "INFO"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = f"sqlite:///{(ROOT / 'database' / 'qvault.db').as_posix()}"
    storage_dir: Path = ROOT / "storage"

    jwt_secret: str = "change-me-in-production-qvault-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    frame_max_count: int = 200
    frame_min_interval: float = 2.0

    question_threshold: float = 0.55
    dedup_mad: float = 0.012
    merge_threshold: float = 0.35

    ncert_page_url: str = "https://ncert.nic.in/textbook.php"
    ncert_files_base: str = "https://ncert.nic.in/textbook/pdf"
    ncert_retry_count: int = 3
    ncert_concurrent_downloads: int = 2
    ncert_timeout: int = 60

    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_email: str = "admin@qvault.local"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_dir / "jobs"

    @property
    def ncert_dir(self) -> Path:
        return self.storage_dir / "ncert"

    @property
    def documents_dir(self) -> Path:
        return self.storage_dir / "documents"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.ncert_dir.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
(ROOT / "database").mkdir(parents=True, exist_ok=True)
