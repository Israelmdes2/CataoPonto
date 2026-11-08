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
    poll_interval: float = 0.5,
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
    Força a janela com 'titulo_parcial' a ir para o primeiro plano (Foreground) absoluto,
    mesmo que o terminal/PowerShell esteja focado e bloqueando foco no Windows.
    """
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    target_hwnds = []

    def callback(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                t = buff.value.lower()
                if titulo_parcial.lower() in t:
                    target_hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(callback), 0)

    if not target_hwnds:
        return False

    hwnd = target_hwnds[0]
    try:
        # SW_RESTORE = 9, SW_MAXIMIZE = 3, SW_SHOW = 5
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.1)

        fore_hwnd = user32.GetForegroundWindow()
        cur_thread = kernel32.GetCurrentThreadId()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)

        if fore_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fore_thread, True)
        if target_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, target_thread, True)

        # Truque do teclado Alt (VK_MENU = 0x12) para quebrar o bloqueio de LockSetForegroundWindow
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)

        # Eleva para HWND_TOPMOST (-1) e depois volta para HWND_NOTOPMOST (-2)
        # SWP_NOSIZE | SWP_NOMOVE = 0x0001 | 0x0002 = 0x0003
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0003)

        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)

        if fore_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fore_thread, False)
        if target_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, target_thread, False)

        time.sleep(0.4)
        return True
    except Exception as e:
        logger.debug(f"Erro ao forçar foco na janela '{titulo_parcial}': {e}")
        return False


def focar_senior_geral() -> bool:
    """Busca e coloca em primeiro plano qualquer janela aberta pertencente ao Senior."""
    termos = [
        "autorização",
        "gestão de pessoas",
        "controle de ponto",
        "seleção de modelos",
        "senior",
        "vetorh",
        "ronda",
    ]
    for termo in termos:
        if focar_janela(termo):
            return True
    return False
