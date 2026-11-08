"""
Helpers de automação de GUI com PyAutoGUI.
GUI automation helpers with PyAutoGUI.

Atenção: PyAutoGUI requer display gráfico (X11/Wayland/Windows/macOS).
Em servidores headless use --headless ao gerar este módulo.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


def _ensure_display():
    """No-op; PyAutoGUI assume display disponível."""
    pass


# Import lazy para falhar com mensagem clara se PyAutoGUI não estiver disponível
def _pg():
    _ensure_display()
    try:
        import pyautogui
        pyautogui.FAILSAFE = True  # mouse no canto superior esquerdo aborta
        try:
            pyautogui.useImageNotFoundException(False)
        except Exception:
            pass
        return pyautogui
    except Exception as e:
        raise RuntimeError(
            f"PyAutoGUI indisponível: {e}. "
            "Instale com / Install with: pip install pyautogui"
        ) from e


# ── Screenshot ─────────────────────────────────────────────────

def screenshot(
    region: Optional[tuple[int, int, int, int]] = None,
    save_to: Optional[Union[str, Path]] = None,
):
    """
    Captura tela inteira ou região (x, y, w, h).
    Capture full screen or region.
    """
    img = _pg().screenshot(region=region)
    if save_to:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(save_to))
    return img


# ── Mouse ──────────────────────────────────────────────────────

def move_to(x: int, y: int, duration: float = 0.2) -> None:
    _pg().moveTo(x, y, duration=duration)


def click(x: Optional[int] = None, y: Optional[int] = None,
          button: str = "left", clicks: int = 1, interval: float = 0.0) -> None:
    _pg().click(x=x, y=y, button=button, clicks=clicks, interval=interval)


def double_click(x: Optional[int] = None, y: Optional[int] = None) -> None:
    _pg().doubleClick(x=x, y=y)


def right_click(x: Optional[int] = None, y: Optional[int] = None) -> None:
    _pg().rightClick(x=x, y=y)


def drag_to(x: int, y: int, duration: float = 0.5, button: str = "left") -> None:
    _pg().dragTo(x, y, duration=duration, button=button)


def scroll(amount: int) -> None:
    """amount > 0 = up; < 0 = down"""
    _pg().scroll(amount)


# ── Teclado / Keyboard ─────────────────────────────────────────

def type_text(text: str, interval: float = 0.05) -> None:
    _pg().typewrite(text, interval=interval)


def press(key: str) -> None:
    _pg().press(key)


def hotkey(*keys: str) -> None:
    """hotkey('ctrl', 'c')"""
    _pg().hotkey(*keys)


# ── Localização por imagem / Image-based location ─────────────

def locate_on_screen(
    template_path: Union[str, Path],
    confidence: float = 0.9,
) -> Optional[tuple[int, int, int, int]]:
    """
    Localiza imagem na tela. Retorna (x, y, w, h) ou None.
    Locate image on screen. Returns (x, y, w, h) or None.

    Requer opencv-python para confidence < 1.0
    """
    try:
        box = _pg().locateOnScreen(str(template_path), confidence=confidence)
        if box is None:
            return None
        return (int(box.left), int(box.top), int(box.width), int(box.height))
    except Exception as e:
        logger.debug(f"locate_on_screen não encontrou {template_path}: {e}")
        return None


def locate_center_on_screen(
    template_path: Union[str, Path],
    confidence: float = 0.9,
) -> Optional[tuple[int, int]]:
    """Mesmo que locate_on_screen mas retorna centro / Same but returns center."""
    try:
        box = locate_on_screen(template_path, confidence=confidence)
        if box is None:
            return None
        x, y, w, h = box
        return (x + w // 2, y + h // 2)
    except Exception:
        return None


def wait_for(
    template_path: Union[str, Path],
    timeout: float = 10.0,
    poll_interval: float = 0.12,
    confidence: float = 0.9,
) -> Optional[tuple[int, int]]:
    """Aguarda imagem aparecer; retorna centro ou None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            pt = locate_center_on_screen(template_path, confidence=confidence)
            if pt is not None:
                return pt
        except Exception:
            pass
        time.sleep(poll_interval)
    return None


def click_image(
    template_path: Union[str, Path],
    confidence: float = 0.9,
    timeout: float = 5.0,
) -> bool:
    """Espera imagem aparecer e clica no centro / Wait then click center."""
    pt = wait_for(template_path, timeout=timeout, confidence=confidence)
    if pt is None:
        return False
    click(*pt)
    return True


# ── Info ───────────────────────────────────────────────────────

def screen_size() -> tuple[int, int]:
    s = _pg().size()
    return (s.width, s.height)


def mouse_position() -> tuple[int, int]:
    p = _pg().position()
    return (int(p.x), int(p.y))


# ── Gerenciamento de Janelas e Resiliência / Window & Resilience Helpers ─

def is_visible(template_path: Union[str, Path], confidence: float = 0.70) -> bool:
    """Verifica de imediato se o template está visível na tela sem aguardar."""
    return locate_center_on_screen(template_path, confidence=confidence) is not None


def focar_janela(titulo_parcial: str) -> bool:
    """
    Ativa e traz a janela para o foco sem redimensionar, minimizar ou alterar seu estado.
    """
    try:
        import pygetwindow as gw
        for win in gw.getAllWindows():
            if titulo_parcial.lower() in (win.title or '').lower():
                if win.isMinimized:
                    win.restore()
                win.activate()
                return True
    except Exception:
        pass

    try:
        import ctypes
        user32 = ctypes.windll.user32
        target_hwnd = None

        def callback(hwnd, extra):
            nonlocal target_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    if titulo_parcial.lower() in buff.value.lower():
                        target_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(callback), 0)

        if target_hwnd:
            user32.SetForegroundWindow(target_hwnd)
            return True
    except Exception:
        pass

    return False


def focar_senior_geral() -> bool:
    """Busca e coloca em primeiro plano qualquer janela aberta pertencente ao Senior priorizando janelas modais."""
    termos = [
        "seleção de modelos",
        "modelos para execução",
        "autorização",
        "controle de ponto e refeitório",
        "gestão de pessoas",
        "vetorh",
        "ronda",
        "senior",
    ]
    for termo in termos:
        if focar_janela(termo):
            return True
    return False
