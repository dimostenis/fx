from __future__ import annotations

from pathlib import Path

import pandas as pd
import pendulum
import structlog
from fastapi import APIRouter
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

import alerting
import crud.cache
import crud.fx

log = structlog.get_logger()
router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/", response_class=HTMLResponse)
async def fetch_data_form(
    request: Request,
    date_from: str = Form(...),
    date_to: str = Form(...),
    ecb: bool = Form(False),  # checkbox
    apilayer: bool = Form(False),  # checkbox
    investiny: bool = Form(False),  # checkbox
):

    # send telegram message
    msg = (
        "<b>Bea FX app run</b>\n\n"
        f"{date_from}-{date_to}\n"
        f"<i>ecb: </i>{ecb}\n"
        f"<i>apilayer: </i>{apilayer}\n"
        f"<i>investiny: </i>{investiny}"
    )
    await alerting.telegram(text=msg)

    # date_to cant be in future –> set it to today
    now = pendulum.now(tz="UTC")
    date_to_ = pendulum.from_format(date_to, "YYYY-MM").end_of("month")
    if date_to_ > now:
        date_to_ = now

    dic = {
        "date_from": pendulum.from_format(date_from, "YYYY-MM")
        .start_of("month")
        .format("YYYY-MM-DD"),
        "date_to": date_to_.format("YYYY-MM-DD"),
    }

    if not date_from < date_to:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="date_from must be before date_to",
        )

    dfe = pd.DataFrame()
    dfa = pd.DataFrame()
    dfi = pd.DataFrame()
    if ecb:
        dfe = crud.fx.get_ecb(date_from=dic["date_from"], date_to=dic["date_to"])
    if apilayer:
        dfa = crud.fx.get_apilayer(date_from=dic["date_from"], date_to=dic["date_to"])
    if investiny:
        dfi = crud.fx.get_investiny(date_from=dic["date_from"], date_to=dic["date_to"])

    df = pd.concat([dfe, dfa, dfi])
    if df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data.")

    df_daily, df_spot, df_monthly = transform(df=df)

    ending = ""
    if ecb and apilayer:
        ...  # thats OK, we use all
    else:
        if ecb:
            ending += "-ecb"
        if apilayer:
            ending += "-apilayer"
        if investiny:
            ending += "-investiny"
    fname = Path("tmp") / f'{dic["date_from"]}_{dic["date_to"]}{ending}.xlsx'
    with pd.ExcelWriter(str(fname)) as writer:
        df_daily.to_excel(writer, sheet_name="daily", index=False)
        df_spot.to_excel(writer, sheet_name="spot", index=False)
        df_monthly.to_excel(writer, sheet_name="monthly", index=False)

    context = {"request": request, "filename": fname.name}
    return templates.TemplateResponse(name="index/result.jinja", context=context)


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns dataframes (daily, spot, monthly)"""

    COLS = ["currency", "ts", "value", "source"]
    emtpy_df = pd.DataFrame(columns=COLS)

    df_daily = df.copy().query("freq == 'D'")
    if not df_daily.empty:
        df_daily = df_daily.sort_values(["currency", "ts"]).loc[:, COLS]
    else:
        df_daily = emtpy_df.copy()

    df_monthly = df.copy().query("freq == 'M'")
    if not df_monthly.empty:
        df_monthly = df_monthly.sort_values(["currency", "ts"]).loc[:, COLS]
    else:
        df_monthly = emtpy_df.copy()

    df_spot = df.copy().query("freq == 'D'")
    if not df_spot.empty:
        df_spot.loc[:, "_dt"] = pd.to_datetime(df_spot.loc[:, "ts"]).values
        df_spot.loc[:, "_ym"] = df_spot.apply(
            lambda row: f'{row["currency"]}-{row["_dt"].year}-{row["_dt"].month}',
            axis=1,
        )
        df_spot = (
            df_spot.sort_values("ts", ascending=False)
            .drop_duplicates(keep="first", subset="_ym")
            .sort_values(["currency", "ts"])
            .loc[:, COLS]
        )
        for col in df_spot.columns:
            if col.startswith("_"):
                del df_spot[col]
    else:
        # return empty DF in correct shape
        df_spot = emtpy_df.copy()

    return df_daily, df_spot, df_monthly
