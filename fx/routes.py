from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

log = structlog.get_logger()
templates = Jinja2Templates(directory="templates")
router = APIRouter()


@router.get("/dl/{fname}/", response_class=FileResponse)
async def download_result(fname: str):

    p = Path("tmp") / fname
    if not p.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    return FileResponse(path=str(p), filename=fname)
