import os
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import NoReturn


def bye(retcode: int = 0) -> NoReturn:
    print(":: Bye")
    raise SystemExit(retcode)


def run(cmd: str) -> None:
    print(f" :: running :: {cmd}")
    if subprocess.run(cmd, shell=True).returncode != 0:
        bye()


def main():

    print("")
    print(":: Bea FX deployment")
    print("::")

    uri = os.getenv("FX_URI", None)
    if not uri:
        uri = input(":: No deployment uri in FX_URI found, type in: ")

    traefik = os.getenv("TRAEFIK_CONF", "traefik.prod.toml")

    print(":: Selected settings:\n")
    print(
        f"   Traefik conf: '{traefik}' (must be in ./traefik/) + deployment URI: '{uri}'"
    )
    try:
        yn = input("\n:: Is this correct? (Y/n) ") or "y"
    except KeyboardInterrupt:
        print(" KeyboardInterrupt")
        bye()

    if yn.lower() not in ("y", "yes"):
        bye()

    compose = f"""\
    version: '3.8'

    services:
      web:
        build:
          context: .
        command: gunicorn main:app --bind 0.0.0.0:5000 -k uvicorn.workers.UvicornWorker
        restart: always
        ports:
          - "500:5000"
        labels:
          - traefik.enable=true
          - traefik.http.routers.fastapi.rule=Host(`{uri}`)
          - traefik.http.services.app.loadbalancer.server.port=500
          - traefik.http.routers.app-http.entrypoints=http
        volumes:
          - fx_temp:/web/tmp

      traefik:
        image: traefik:2.9.1
        ports:
          - "8080:500"
        restart: always
        volumes:
          - "/var/run/docker.sock:/var/run/docker.sock:ro"
          - "$PWD/traefik/{traefik}:/etc/traefik/traefik.toml"
          - traefik-public-certificates:/certificates

    volumes:
      traefik-public-certificates:
      fx_temp:
        driver: local
    """

    p = Path(".") / "docker-compose.prod.yml"
    p.write_text(dedent(compose))

    run("git pull")
    run("docker compose stop")
    run("docker compose build")
    run("docker compose -f docker-compose.prod.yml up -d")


if __name__ == "__main__":
    main()
