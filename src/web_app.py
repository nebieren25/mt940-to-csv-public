"""
FastAPI application factory. Mounts web adapter routes and web-ui static files.
M5: Logging config, consistent error handling.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.adapters.web.logging_config import configure_logging, get_logger
from src.adapters.web.routes import router as api_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="MT940 → CSV",
        description="Upload MT940 bank statement, convert to CSV.",
        version="0.5.0",
    )
    app.include_router(api_router)

    async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
        """Return consistent 500 with detail; log full exception."""
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Serve web-ui folder at /ui (web-ui-1.html, web-ui-2.html, mt940-api.js)
    web_ui_dir = Path(__file__).resolve().parent.parent / "web-ui"
    if web_ui_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=str(web_ui_dir), html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def root():
        """Redirect to the main UI (web-ui-1)."""
        return RedirectResponse(url="/ui/web-ui-1-v3.html", status_code=302)

    @app.get("/insights", include_in_schema=False)
    def insights_redirect():
        """Redirect to Insights dashboard."""
        return RedirectResponse(url="/ui/insights.html", status_code=302)

    return app


app = create_app()
