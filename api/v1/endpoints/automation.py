"""
Endpoint /automation — expõe operações de automação via HTTP.
Endpoint /automation — exposes automation operations over HTTP.

⚠️  Cuidado / Caution: ações de GUI executam NO SERVIDOR.
Use somente em ambientes controlados / Use only in controlled environments.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from pathlib import Path
import tempfile

router = APIRouter()


@router.get("/screen-size", summary="Screen size of host")
async def screen_size():
    try:
        from infrastructure.automation import gui
        w, h = gui.screen_size()
        return {"width": w, "height": h}
    except Exception as e:
        raise HTTPException(503, f"GUI unavailable: {e}")


@router.post("/screenshot", summary="Take screenshot on host")
async def screenshot(
    x: Optional[int] = None, y: Optional[int] = None,
    w: Optional[int] = None, h: Optional[int] = None,
):
    from infrastructure.automation import gui
    region = (x, y, w, h) if all(v is not None for v in (x, y, w, h)) else None
    tmp = Path(tempfile.gettempdir()) / "automation_shot.png"
    gui.screenshot(region=region, save_to=tmp)
    return {"path": str(tmp)}


@router.post("/find-template", summary="OpenCV template match")
async def find_template(
    image: UploadFile = File(...),
    template: UploadFile = File(...),
    threshold: float = Form(0.85),
):
    from infrastructure.automation import vision
    img_path = Path(tempfile.gettempdir()) / image.filename
    tpl_path = Path(tempfile.gettempdir()) / template.filename
    img_path.write_bytes(await image.read())
    tpl_path.write_bytes(await template.read())
    matches = vision.find_template(
        vision.load_image(str(img_path)),
        vision.load_image(str(tpl_path)),
        threshold=threshold,
    )
    return {"matches": [{"x": x, "y": y, "score": s} for x, y, s in matches]}
