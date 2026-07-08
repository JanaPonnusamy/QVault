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

    # --- Database ---
    # db_backend selects the target; an explicit database_url overrides everything.
    db_backend: str = "sqlite"  # "sqlite" | "sqlserver"
    database_url: str | None = None  # explicit SQLAlchemy URL override (QVAULT_DATABASE_URL)

    mssql_server: str = "192.168.10.73"
    mssql_port: int = 1433
    mssql_database: str = "QVault"
    mssql_user: str = "sa"
    mssql_password: str = "Admin123"
    mssql_driver: str = "ODBC Driver 17 for SQL Server"
    mssql_trust_cert: bool = True

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

    # yt-dlp cookie auth (Instagram/YouTube increasingly require a logged-in
    # session for some content). Both optional; cookies_file takes precedence.
    ytdlp_cookies_file: str | None = None  # path to a Netscape-format cookies.txt
    ytdlp_cookies_from_browser: str | None = None  # e.g. "chrome", "firefox:Default"

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

    @property
    def mssql_odbc_connect(self) -> str:
        """Raw ODBC connection string for pyodbc / SQLAlchemy odbc_connect."""
        parts = [
            f"DRIVER={{{self.mssql_driver}}}",
            f"SERVER={self.mssql_server},{self.mssql_port}",
            f"DATABASE={self.mssql_database}",
            f"UID={self.mssql_user}",
            f"PWD={self.mssql_password}",
        ]
        if self.mssql_trust_cert:
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts) + ";"

    @property
    def sqlalchemy_url(self) -> str:
        """Resolved SQLAlchemy URL: explicit override > backend selection > sqlite default."""
        if self.database_url:
            return self.database_url
        if self.db_backend.lower() in ("sqlserver", "mssql"):
            from urllib.parse import quote_plus

            return f"mssql+pyodbc:///?odbc_connect={quote_plus(self.mssql_odbc_connect)}"
        return f"sqlite:///{(ROOT / 'database' / 'qvault.db').as_posix()}"

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.ncert_dir.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
(ROOT / "database").mkdir(parents=True, exist_ok=True)
