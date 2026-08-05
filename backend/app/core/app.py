from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    auth,
    branding,
    catalog,
    content,
    documents,
    education,
    extractor,
    instagram,
    gk_scraper,
    knowledge,
    ncert,
    notifications,
    question_bank,
    research,
    roles,
    users,
    videos,
)
from app.config.settings import settings
from app.core.seed import seed
from app.database.session import init_db
from app.integrations.ytdlp import InstagramSession, log_cookie_source
from app.services.health_service import get_health_status
from app.shared.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    init_db()
    seed()
    log_cookie_source()
    InstagramSession.ensure_seeded()

    app = FastAPI(title="QVault Admin API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(branding.router)
    app.include_router(users.router)
    app.include_router(roles.router)
    app.include_router(extractor.router)
    app.include_router(instagram.router)
    app.include_router(ncert.router)
    app.include_router(notifications.router)
    app.include_router(documents.router)
    app.include_router(knowledge.router)
    app.include_router(content.router)
    app.include_router(research.router)
    app.include_router(videos.router)
    app.include_router(catalog.router)
    app.include_router(question_bank.router)
    app.include_router(gk_scraper.router)
    app.include_router(education.router)

    @app.get("/api/health", tags=["system"])
    def health():
        return {"app": settings.app_name, **get_health_status()}

    return app


app = create_app()
