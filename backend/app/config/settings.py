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
    # 8000 is permanently reserved by an unrelated app (NEXORA) on this
    # machine -- QVault always runs on 8004 (see CLAUDE.md).
    api_port: int = 8004

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

    # --- Video generation ---
    assets_dir: Path = ROOT / "assets"
    output_dir: Path = ROOT / "output"
    video_fps: int = 30
    video_concurrent_renders: int = 1
    video_template: str = "glass_dark"

    # --- TTS (provider-abstracted; see integrations/tts) ---
    tts_provider: str = "edge"
    # Pallavi speaking the English script gives Tamil Nadu accented English;
    # the edge provider adds a base pitch lift for a younger (early-20s) tone.
    tts_voice: str = "ta-IN-PallaviNeural"
    tts_rate: str = "-4%"  # slightly slower than default for natural pacing
    tts_pitch: str = "+0Hz"
    tts_openai_api_key: str | None = None
    tts_openai_model: str = "gpt-4o-mini-tts"
    tts_elevenlabs_api_key: str | None = None
    tts_elevenlabs_model: str = "eleven_multilingual_v2"
    tts_azure_key: str | None = None
    tts_azure_region: str | None = None
    tts_google_api_key: str | None = None
    tts_piper_exe: str | None = None
    tts_piper_model: str | None = None

    ncert_page_url: str = "https://ncert.nic.in/textbook.php"
    ncert_files_base: str = "https://ncert.nic.in/textbook/pdf"
    ncert_retry_count: int = 3
    ncert_concurrent_downloads: int = 2
    ncert_timeout: int = 60

    # --- GK Scraper (generic site analyzer) ---
    # A site's real inventory (up to gk_scraper_pool_size pages) is discovered
    # and enqueued, and a single Start Scan run fetches/parses every one of
    # them (AcquisitionItem's idempotent (provider, source_id) state still
    # means a second run only re-touches new/failed pages, never redoing
    # completed ones).
    # 5000 was a placeholder guess; cross-checked against the legacy TNPSC
    # scraper's own lifetime visited-URL log (45,358 unique pages over ~2
    # years) and a direct sitemap probe of gktoday.in (59,836 URLs total) --
    # raised to cover the real site, not an arbitrary fraction of it.
    gk_scraper_pool_size: int = 65000
    gk_scraper_timeout: int = 20
    # Matches the proven concurrency level from the user's own prior scrapers
    # (examveda_fast_scraper.py / gktoday_scraper_parallel.py: Pool(8), no delay).
    gk_scraper_concurrency: int = 8
    gk_scraper_request_delay: float = 0.0

    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_email: str = "admin@qvault.local"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_dir / "jobs"

    @property
    def instagram_dir(self) -> Path:
        return self.storage_dir / "instagram"

    @property
    def instagram_cookies_path(self) -> Path:
        """Cookie jar managed by the in-app Instagram login (Instagram
        Acquisition page) -- separate from `ytdlp_cookies_file` so logging in
        for Instagram never touches YouTube's cookie configuration."""
        return self.instagram_dir / "cookies.txt"

    @property
    def instagram_session_path(self) -> Path:
        return self.instagram_dir / "session.json"

    @property
    def ncert_dir(self) -> Path:
        return self.storage_dir / "ncert"

    @property
    def documents_dir(self) -> Path:
        return self.storage_dir / "documents"

    @property
    def catalog_dir(self) -> Path:
        return self.storage_dir / "catalog"

    @property
    def gk_scraper_dir(self) -> Path:
        return self.storage_dir / "gk_scraper"

    @property
    def education_dir(self) -> Path:
        return self.storage_dir / "education"

    @property
    def acquisition_dir(self) -> Path:
        """Deterministic download layout for the Question Acquisition &
        Extraction Engine's provider framework: <provider>/<exam>/<year>/<source_id>/."""
        return self.storage_dir / "acquisition"

    @property
    def templates_dir(self) -> Path:
        return self.assets_dir / "templates"

    @property
    def fonts_dir(self) -> Path:
        return self.assets_dir / "fonts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mssql_server_address(self) -> str:
        """SERVER= value: named instances (e.g. HOST\\SQLEXPRESS) resolve their own
        dynamic port and must not have ,port appended; plain hosts do."""
        if "\\" in self.mssql_server:
            return self.mssql_server
        return f"{self.mssql_server},{self.mssql_port}"

    def _mssql_connect(self, database: str) -> str:
        parts = [
            f"DRIVER={{{self.mssql_driver}}}",
            f"SERVER={self.mssql_server_address}",
            f"DATABASE={database}",
            f"UID={self.mssql_user}",
            f"PWD={self.mssql_password}",
        ]
        if self.mssql_trust_cert:
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts) + ";"

    @property
    def mssql_odbc_connect(self) -> str:
        """Raw ODBC connection string for pyodbc / SQLAlchemy odbc_connect."""
        return self._mssql_connect(self.mssql_database)

    @property
    def mssql_master_odbc_connect(self) -> str:
        """Same server, connected to `master` — used to create/check the target
        database itself before it exists."""
        return self._mssql_connect("master")

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
# QVAULT_STORAGE_DIR (and any other Path-typed env override) may arrive as a
# bare relative value (e.g. "storage") — pydantic-settings casts it to Path
# as-is, so it silently resolved against the process's cwd rather than the
# repo root. Every documented run command `cd backend && uvicorn ...` has a
# cwd of `backend/`, so this was quietly writing/reading a second, wrong
# `backend/storage/` tree instead of the top-level `storage/` the rest of the
# codebase assumes. Anchor it to ROOT once, here, regardless of cwd.
if not settings.storage_dir.is_absolute():
    settings.storage_dir = (ROOT / settings.storage_dir).resolve()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.instagram_dir.mkdir(parents=True, exist_ok=True)
settings.ncert_dir.mkdir(parents=True, exist_ok=True)
settings.documents_dir.mkdir(parents=True, exist_ok=True)
settings.catalog_dir.mkdir(parents=True, exist_ok=True)
settings.gk_scraper_dir.mkdir(parents=True, exist_ok=True)
settings.education_dir.mkdir(parents=True, exist_ok=True)
settings.acquisition_dir.mkdir(parents=True, exist_ok=True)
(ROOT / "database").mkdir(parents=True, exist_ok=True)
for _sub in ("videos", "shorts", "reels", ".work"):
    (settings.output_dir / _sub).mkdir(parents=True, exist_ok=True)
