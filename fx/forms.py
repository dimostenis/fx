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
from config import settings

Path("tmp").mkdir(exist_ok=True)
router = APIRouter()

log = structlog.get_logger()
templates = Jinja2Templates(directory="templates")


@router.post("/", response_class=HTMLResponse)
async def fetch_data_form(
    request: Request,
    date_from: str = Form(...),
    date_to: str = Form(...),
    ecb: bool = Form(False),
    apilayer: bool = Form(False),
    investing: bool = Form(False),
):

    # send telegram message
    msg = (
        "<b>Bea FX app run</b>\n\n"
        f"{date_from}-{date_to}\n"
        f"<i>ecb: </i>{ecb}\n"
        f"<i>apilayer: </i>{apilayer}"
    )
    await alerting.telegram(text=msg)

    # save for next time
    request.session.update(
        {
            "checkboxes": {
                "ecb": ecb,
                "apilayer": apilayer,
                "investing": investing,
            }
        }
    )

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

    ecb_df = pd.DataFrame()
    al_df = pd.DataFrame()
    inv_df = pd.DataFrame()

    if ecb:
        ecb_df = crud.fx.get_ecb(date_from=dic["date_from"], date_to=dic["date_to"])
    if apilayer:
        al_df = crud.fx.get_apilayer(date_from=dic["date_from"], date_to=dic["date_to"])
    if investing:
        inv_df = crud.fx.get_investing(
            date_from=dic["date_from"], date_to=dic["date_to"]
        )

    df = pd.concat([ecb_df, al_df, inv_df])
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
        if investing:
            ending += "-investing"
    fname = Path("tmp") / f'{dic["date_from"]}_{dic["date_to"]}{ending}.xlsx'
    with pd.ExcelWriter(str(fname)) as writer:
        df_daily.to_excel(writer, sheet_name="daily", index=False)
        df_spot.to_excel(writer, sheet_name="spot", index=False)
        df_monthly.to_excel(writer, sheet_name="monthly", index=False)

    context = {"request": request, "filename": fname.name}
    return templates.TemplateResponse(name="index/result.jinja", context=context)


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    df_daily = (
        df.copy()
        .query("freq == 'D'")
        .sort_values(["currency", "ts"], ascending=[True, True])
        .loc[:, ["currency", "ts", "value", "source"]]
    )

    df_monthly_existing = df.copy().query("freq == 'M'")
    df_monthly_missing = (
        pd.DataFrame(
            columns=list(df_monthly_existing["ts"].unique()),
            index=settings.APILAYER_SYMBOLS.split(","),
        )
        .reset_index()
        .melt(id_vars="index")
        .rename(columns={"index": "currency", "variable": "ts"})
        .assign(freq="M")  # for cleaner concat
        .assign(value=-1)
        .assign(source="apilayer")
    )
    df_monthly = (
        pd.concat([df_monthly_existing, df_monthly_missing])
        .sort_values(["value", "currency", "ts"], ascending=[False, True, True])
        .loc[:, ["currency", "ts", "value", "source"]]
    )

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
            .sort_values(["currency", "ts"], ascending=[True, True])
            .loc[:, ["currency", "ts", "value", "source"]]
        )
        for col in df_spot.columns:
            if col.startswith("_"):
                del df_spot[col]
    else:
        # return empty DF in correct shape
        df_spot = df_spot.loc[:, ["currency", "ts", "value", "source"]]

    return df_daily, df_spot, df_monthly
