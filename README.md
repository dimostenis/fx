# FX for Bea

*Microapp for a friend accountant.*

Requirements were to find **daily**, **monthly** and **spot** (last day of month) FX rates.

Some currencies are to be found on [ECB](ecbapi), but rest must come from elsewhere, because they not listed on ECB unfortunatelly. Those I found on [Apilayer exchange rates API](apilayerapi).

To access Apilayer API, one must register to obtain API key.

## Cookies

App uses 1 first party cookie to save last form checkboxes.

## Auth

There is no auth impemented, as we dont really need it.

## Alerting

*Sentry-like* Telegram notifications has been used.

## Run

Set env variables (`.env` can be used):

```bash
SECRET_KEY=...  # to secure cookie - 16len str is generated if not set

APILAYER_API_KEY=...  # get your own:)
```

Variables below have default values (as Bea requests), but can be overriden:

```bash
BASE="EUR"  # base currency

ECB_ENDPOINT="https://sdw-wsrest.ecb.europa.eu/service/data/EXR/"
ECB_SYMBOLS="USD+CZK+HUF+RON+TRY+BGN"

APILAYER_ENDPOINT="https://api.apilayer.com/exchangerates_data/"
APILAYER_SYMBOLS="RSD,KZT,UAH,UZS"
```

Alerting via Telegram can be used, if enabled by:

```bash
TELEGRAM_ENABLED=  # bool, by default 0/false/False
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Deployment

There are several options presented:

**1. Run app locally with:**

```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload --workers 1
```

**2. Run locally in Docker via [Traefik](traefik)**

```bash
docker-compose up
```

Find running app at `localhost:500`

**3. Deploy on server**

There is no CI, all manually:

1. push to repo
1. ssh to machine/repo
1. `python deploy.py`

## Contribution

Im not sure I wanna accept PR, as its a quick side project.

However, if you really wanna, dont forget to use `pre-commit`!

```bash
pre-commit install
pre-commit
```

If you use Visual Studio Code, use this launch.json settings:

```json
        {
            "name": "Python: FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "main:app"
            ],
            "jinja": true,
            "justMyCode": true
        }
```

## Plans

Use certificate ...

[ecbapi]: https://sdw-wsrest.ecb.europa.eu/help/
[apilayerapi]: https://apilayer.com/marketplace/exchangerates_data-api
[Traefik]: https://traefik.io
