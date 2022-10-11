from __future__ import annotations

import io
import json
from typing import Any

import investiny.historical
import investiny.search
import pandas as pd
import pendulum
import requests
import structlog
from fastapi import HTTPException

import crud.cache
import crud.fx
from config import settings

log = structlog.get_logger()


def get_ecb(date_from: str, date_to: str) -> pd.DataFrame:
    """
    Fetch data from ECB and transform it to DF:

        currency freq          ts      value
    0        BGN    D  2022-08-01   1.955800
    1        BGN    D  2022-08-02   1.955800
    2        BGN    D  2022-08-03   1.955800
    3        BGN    D  2022-08-04   1.955800
    4        BGN    D  2022-08-05   1.955800
    ..       ...  ...         ...        ...
    277      RON    M     2022-09   4.909668
    278      TRY    M     2022-08  18.270104
    279      TRY    M     2022-09  18.146536
    280      USD    M     2022-08   1.012843
    281      USD    M     2022-09   0.990377

    Args:
        date_from (str): YYYY-MM-DD
        date_to (str): YYYY-MM-DD

    Raises:
        HTTPException: 500, if ECB API is unvailable

    Returns:
        pd.DataFrame
    """

    logger = log.bind(
        date_from=date_from,
        date_to=date_to,
        source="ECB",
        symbol=settings.ECB_SYMBOLS,
    )

    params = {"format": "csvdata", "startPeriod": date_from, "endPeriod": date_to}
    key = params | {"symbols": settings.ECB_SYMBOLS, "base": settings.BASE}
    if csv := crud.cache.get(key=json.dumps(key)):
        logger.info("getting data from cache")
    else:
        logger.info("getting data via API")
        response = requests.get(
            f"{settings.ECB_ENDPOINT}D+M.{settings.ECB_SYMBOLS}.{settings.BASE}.SP00.A",
            params=params,
        )
        if response.status_code // 100 == 2:
            csv = response.content
            crud.cache.create(key=json.dumps(key), obj=csv)
        else:
            raise HTTPException(status_code=500, detail="failed to fetch data from ECB")

    df = (
        pd.read_csv(io.BytesIO(csv))
        .loc[:, ["CURRENCY", "FREQ", "TIME_PERIOD", "OBS_VALUE"]]
        .rename(
            columns={
                "CURRENCY": "currency",
                "FREQ": "freq",
                "TIME_PERIOD": "ts",
                "OBS_VALUE": "value",
            }
        )
        .assign(source="ecb")
    )

    return df


def get_apilayer(date_from: str, date_to: str) -> pd.DataFrame:
    """
    Fetch FX rates from Apilayer exchange API.
    Currently, there is a limit of 250 calls/month.

    Func returns dataframe:

                 ts currency         value freq
    0    2022-08-01      RSD    117.339545    D
    1    2022-08-02      RSD    117.370164    D
    2    2022-08-03      RSD    117.352196    D
    3    2022-08-04      RSD    117.355885    D
    4    2022-08-05      RSD    117.189486    D
    ..          ...      ...           ...  ...
    239  2022-09-26      UZS  10613.422205    D
    240  2022-09-27      UZS  10591.379323    D
    241  2022-09-28      UZS  10688.334698    D
    242  2022-09-29      UZS  10828.528956    D
    243  2022-09-30      UZS  10799.968445    D

    Args:
        date_from (str): YYYY-MM-DD
        date_to (str): YYYY-MM-DD

    Raises:
        HTTPException: 500, if Apilayer API is unvailable or quota is reached

    Returns:
        pd.DataFrame
    """

    logger = log.bind(
        date_from=date_from,
        date_to=date_to,
        source="apilayer.com",
        symbol=settings.APILAYER_SYMBOLS,
    )

    params = {
        "start_date": date_from,
        "end_date": date_to,
        "base": settings.BASE,
        "symbols": settings.APILAYER_SYMBOLS,
    }
    jsondata: bytes | Any  # shall be bytes if all OK
    if jsondata := crud.cache.get(key=json.dumps(params)):
        logger.info("getting data from cache")
    else:
        logger.info("getting data via API")
        response = requests.get(
            url=f"{settings.APILAYER_ENDPOINT}timeseries",
            headers={"apikey": settings.APILAYER_API_KEY.get_secret_value()},
            params=params,
        )
        if response.status_code // 100 == 2:
            jsondata = response.content
            crud.cache.create(key=json.dumps(params), obj=jsondata)

            # save latest quota values for frontend
            quota = {
                "remaining": int(
                    response.headers.get("X-RateLimit-Remaining-Month", 0)
                ),
                "limit": int(response.headers.get("X-RateLimit-Limit-Month", 0)),
            }
            crud.cache.create(key="apilayer_quota", obj=quota)
        else:
            # just crash .. Bea will call
            raise HTTPException(
                status_code=500,
                detail="failed to fetch data from apilayer.com",
            )

    df = (
        pd.DataFrame.from_dict(
            json.loads(jsondata).get("rates"),
            orient="index",
        )
        .reset_index()
        .melt(id_vars="index")
        .rename(columns={"index": "ts", "variable": "currency"})
        .assign(freq="D")
        .assign(source="apilayer")
    )

    return df


def get_investiny(date_from: str, date_to: str) -> pd.DataFrame:
    logger = log.bind(date_from=date_from, date_to=date_to, source="investiny")

    from_date = pendulum.from_format(date_from, "YYYY-MM-DD")
    to_date = pendulum.from_format(date_to, "YYYY-MM-DD")
    to_date_monthly = to_date
    # dont do monthly if you cant return full month
    if not to_date.day == to_date.end_of("month").day:
        # lets go one month less (to last day of it)
        to_date_monthly = to_date.subtract(months=1).end_of("month")

    # USA date format, lol..
    date_from_usa = from_date.format("MM/DD/YYYY")
    # date_to_usa = to_date.format("MM/DD/YYYY")  # daily not yet done
    date_to_usa_monthly = to_date_monthly.format("MM/DD/YYYY")

    # do monthly
    dates = []
    cursor = from_date
    while cursor < to_date_monthly:
        dates.append(cursor.format("YYYY-MM"))
        cursor = cursor.add(months=1)

    monthly = []
    for symbol, id_ in settings.INVESTINY_SYMBOLS.items():
        key = f"M|{id_}|{symbol}--{date_from_usa}--{date_to_usa_monthly}"

        if dic := crud.cache.get(key=key):
            logger.info("getting data from cache", symbol=symbol)
        else:
            logger.info("getting data via API", symbol=symbol)
            dic = investiny.historical.historical_data(
                investing_id=id_,
                from_date=date_from_usa,
                to_date=date_to_usa_monthly,
                interval="M",
            )
            crud.cache.create(key=key, obj=dic)

        # dic data go from oldes mon to newest
        currency = symbol.split("/")[1]  # EUR/RSD -> RSD
        df = pd.DataFrame.from_dict(dic).assign(currency=currency)
        df.index = dates
        monthly.append(df)

    # do daily
    # NOTE Its a problem now, coz investiny API returns only a list of values,
    # NOTE but I dont know what are the dates? Where were banking holidays? Dunno.

    df = (
        pd.concat(monthly)
        .reset_index()
        .loc[:, ["index", "close", "currency"]]
        .assign(freq="M")
        .rename(columns={"index": "ts", "close": "value"})
        .assign(source="investiny")
    )

    return df


def get_investing_id(symbol: str):
    """
    Dev helper function.

    Ask for a ticker and get internal investing.com ID, so it can be used in investiny.
    """

    res = investiny.search.search_assets(query=symbol, limit=1)
    log.info(res)
    return res
