from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import alerting
from config import settings
from fx.forms import router as fx_forms
from fx.routes import router as fx_router
from views.routes import router as views_router

WEEK_S = 7 * 24 * 60 * 60
Path("tmp").mkdir(exist_ok=True)
log = structlog.get_logger()
templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY.get_secret_value(),
    max_age=WEEK_S,
)
app.include_router(views_router, tags=["views"])
app.include_router(fx_router, prefix="/fx", tags=["fx"])
app.include_router(fx_forms, prefix="/fx", tags=["forms"])


@app.exception_handler(Exception)
async def any_exception(request: Request, exc: Exception):
    """
    If app crashes for realz, not by manually raising HTTPException.

    So, let admins know someone is not using it properly by loggin it in:
    1. stdout via structlog
    2. telegram message
    """
    detail = repr(exc)
    url = request.url.path

    # easy to find log message
    log.error("app error", errors=detail, url=url)

    # send telegram message
    msg = f"<b>Bea FX app exception</b>\n\n{detail}\n<i>url: </i>{url}"
    await alerting.telegram(text=msg)

    raise exc
