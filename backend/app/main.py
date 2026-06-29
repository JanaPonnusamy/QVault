import uvicorn

from app.config.settings import settings
from app.core.app import app

__all__ = ["app"]


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
