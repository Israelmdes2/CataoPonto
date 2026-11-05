"""
Helpers de visão computacional com OpenCV.
Computer vision helpers with OpenCV.

Todas as funções aceitam caminhos ou ndarrays e retornam ndarrays
para fácil composição em pipelines.

All functions accept paths or ndarrays and return ndarrays for
easy pipeline composition.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)

ImageLike = Union[str, Path, np.ndarray]


def _ensure_array(img: ImageLike) -> np.ndarray:
    if isinstance(img, np.ndarray):
        return img
    arr = cv2.imread(str(img), cv2.IMREAD_UNCHANGED)
    if arr is None:
        raise FileNotFoundError(f"Imagem não encontrada / image not found: {img}")
    return arr


# ── IO ─────────────────────────────────────────────────────────

def load_image(path: Union[str, Path]) -> np.ndarray:
    """Carrega imagem em BGR / Load image in BGR."""
    return _ensure_array(path)


def save_image(img: np.ndarray, path: Union[str, Path]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), img)


# ── Conversões / Conversions ──────────────────────────────────

def to_grayscale(img: ImageLike) -> np.ndarray:
    return cv2.cvtColor(_ensure_array(img), cv2.COLOR_BGR2GRAY)


def to_rgb(img: ImageLike) -> np.ndarray:
    return cv2.cvtColor(_ensure_array(img), cv2.COLOR_BGR2RGB)


# ── Transformações / Transforms ───────────────────────────────

def resize(img: ImageLike, width: int, height: int) -> np.ndarray:
    return cv2.resize(_ensure_array(img), (width, height), interpolation=cv2.INTER_AREA)


def crop(img: ImageLike, box: tuple[int, int, int, int]) -> np.ndarray:
    """box = (x, y, w, h)"""
    a = _ensure_array(img)
    x, y, w, h = box
    return a[y:y + h, x:x + w]


# ── Template matching / Busca por template ─────────────────────

def find_template(
    img: ImageLike,
    template: ImageLike,
    threshold: float = 0.8,
) -> list[tuple[int, int, float]]:
    """
    Localiza ocorrências de `template` em `img`.
    Returns: lista de (x, y, score), do mais provável ao menos.
    """
    src = _ensure_array(img)
    tpl = _ensure_array(template)
    src_gray = src if len(src.shape) == 2 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    tpl_gray = tpl if len(tpl.shape) == 2 else cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)

    result = cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
    locs   = np.where(result >= threshold)
    out    = []
    for y, x in zip(*locs):
        out.append((int(x), int(y), float(result[y, x])))
    # ordena por score desc / sort by score desc
    out.sort(key=lambda t: t[2], reverse=True)
    logger.debug("[vision] %d matches (threshold=%.2f)", len(out), threshold)
    return out


# ── Diff / Comparação ─────────────────────────────────────────

def diff(a: ImageLike, b: ImageLike, threshold: float = 0.95) -> tuple[bool, float]:
    """
    Retorna (similares, score). Score = correlação normalizada.
    Returns (similar, score). Score = normalized correlation.
    """
    ia = to_grayscale(a)
    ib = to_grayscale(b)
    if ia.shape != ib.shape:
        ib = cv2.resize(ib, (ia.shape[1], ia.shape[0]))
    score = float(cv2.matchTemplate(ia, ib, cv2.TM_CCOEFF_NORMED).max())
    return (score >= threshold), score


# ── Desenho / Drawing ─────────────────────────────────────────

def draw_boxes(
    img: ImageLike,
    boxes: list[tuple[int, int, int, int]],
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """boxes = [(x, y, w, h), ...]"""
    out = _ensure_array(img).copy()
    for (x, y, w, h) in boxes:
        cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
    return out


def draw_points(
    img: ImageLike,
    points: list[tuple[int, int]],
    color: tuple[int, int, int] = (0, 0, 255),
    radius: int = 5,
) -> np.ndarray:
    out = _ensure_array(img).copy()
    for (x, y) in points:
        cv2.circle(out, (x, y), radius, color, -1)
    return out


# ── OCR (opcional) / OCR (optional) ───────────────────────────────

def read_text_from_region(x: int, y: int, width: int, height: int,
                          lang: str = "por+eng") -> str:
    """Le texto de uma regiao da tela usando OCR (Tesseract).
    Reads text from a screen region using OCR (Tesseract).

    Requer / Requires:
        pip install pytesseract pillow
        + binario do Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
    """
    try:
        import pytesseract
        import pyautogui
    except ImportError as e:
        raise RuntimeError(
            "OCR indisponivel. Instale: pip install pytesseract pillow"
        ) from e
    img = pyautogui.screenshot(region=(x, y, width, height))
    return pytesseract.image_to_string(img, lang=lang).strip()


def read_text_from_image(image_path: str, lang: str = "por+eng") -> str:
    """Le texto de uma imagem em disco."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "OCR indisponivel. Instale: pip install pytesseract pillow"
        ) from e
    return pytesseract.image_to_string(Image.open(image_path), lang=lang).strip()
