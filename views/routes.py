from __future__ import annotations

import random
from typing import TypedDict

import pendulum
from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import crud.cache

templates = Jinja2Templates(directory="templates")
router = APIRouter()


class Checkboxes(TypedDict):
    ecb: bool
    apilayer: bool


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
    checkboxes: Checkboxes
    checkboxes = request.session.get("checkboxes", {"ecb": True, "apilayer": True})

    context = {
        "request": request,
        "options": list(reversed(options)),
        "checkboxes": checkboxes,  # settings from last time
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
