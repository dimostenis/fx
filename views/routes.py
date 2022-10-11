from __future__ import annotations

import random
from typing import Literal
from typing import TypedDict

import pendulum
import structlog
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import config
import crud.cache
from config import settings

log = structlog.get_logger()
templates = Jinja2Templates(directory="templates")
router = APIRouter()


class Checkboxes(TypedDict):
    ecb: bool
    apilayer: bool
    investiny: bool


@router.get("/", response_class=HTMLResponse)
async def index_view(request: Request):

    now = pendulum.now().end_of("month")
    start = now.subtract(years=3)
    options = []

    cur = start
    while cur <= now:
        options.append(cur.format("YYYY-MM"))
        cur = cur.add(months=1)

    # if no cookie, enable all
    session: Checkboxes
    default = {k: True for k in Checkboxes.__annotations__.keys()}
    if session := request.session.get("checkboxes", default):
        if default.items() <= session.items():  # session has all keys needed
            ...  # OK, however session cookie CAN has extra keys, but who cares...
        else:
            session = default | session  # use what we have, if usable
    request.session.update({"checkboxes": session})

    context = {
        "request": request,
        "fx_ecb": config.list_rates(settings.ECB_SYMBOLS, sep="+"),
        "fx_apilayer": config.list_rates(settings.APILAYER_SYMBOLS, sep=","),
        "fx_investiny": ", ".join(tuple(settings.INVESTINY_SYMBOLS.keys())),
        "options": list(reversed(options)),
        "checkboxes": session,  # settings from last time
    }

    return templates.TemplateResponse("index/index.jinja", context=context)


@router.get("/quota_progressbar/", response_class=HTMLResponse)
async def hx_quota_progressbar(request: Request):

    APILAYER_DEFAULT_MAX = 250

    dic = crud.cache.get("apilayer_quota")
    if dic:
        ...
    else:
        # just first run, before cache is populated
        dic = {
            "remaining": random.randint(0, APILAYER_DEFAULT_MAX),
            "limit": APILAYER_DEFAULT_MAX,
        }

    valuenow = dic["remaining"]
    valuemax = dic["limit"]

    width = int(valuenow / valuemax * 100)
    label = f"{valuenow} / {valuemax}"

    context = {
        "request": request,
        "valuemax": valuemax,
        "valuenow": valuenow,
        "width": width,
        "label": label,
    }
    return templates.TemplateResponse(name="index/quota.jinja", context=context)


@router.get("/toggle_checkbox/{key}")
async def toggle_checkbox_in_session(
    request: Request,
    key: Literal["ecb", "apilayer", "investiny"],  # keys of typed dict Checkboxes
) -> None:
    """Toggle checkbox position to session"""
    if dic := request.session.get("checkboxes"):
        dic[key] = not dic[key]  # toggle current value
        log.info("checkbox toggle", key=key, now=dic[key])
