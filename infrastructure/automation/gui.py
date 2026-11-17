from __future__ import annotations

import ctypes
import logging
import time
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)

TERMOS_JANELAS_SENIOR = (
    "seleção de modelos",
    "modelos para execução",
    "autorização",
    "controle de ponto e refeitório",
    "gestão de pessoas",
    "vetorh",
    "ronda",
    "senior",
)


def _obter_pyautogui():
    """Carrega PyAutoGUI sob demanda para permitir uso do CLI em ambientes sem display."""
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        try:
            pyautogui.useImageNotFoundException(False)
        except Exception:
            pass
        return pyautogui
    except Exception as erro:
        raise RuntimeError(f"PyAutoGUI indisponível: {erro}. Instale com: pip install pyautogui") from erro


def screenshot(
    region: Optional[tuple[int, int, int, int]] = None,
    save_to: Optional[Union[str, Path]] = None,
):
    """Captura a tela inteira ou uma região específica."""
    imagem = _obter_pyautogui().screenshot(region=region)
    if save_to:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        imagem.save(str(save_to))
    return imagem


def move_to(coord_x: int, coord_y: int, duration: float = 0.2) -> None:
    """Move o ponteiro do mouse até a coordenada informada."""
    _obter_pyautogui().moveTo(coord_x, coord_y, duration=duration)


def click(
    coord_x: Optional[int] = None,
    coord_y: Optional[int] = None,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.0,
) -> None:
    """Executa clique do mouse na posição especificada."""
    _obter_pyautogui().click(x=coord_x, y=coord_y, button=button, clicks=clicks, interval=interval)


def double_click(coord_x: Optional[int] = None, coord_y: Optional[int] = None) -> None:
    """Executa duplo clique do mouse."""
    _obter_pyautogui().doubleClick(x=coord_x, y=coord_y)


def right_click(coord_x: Optional[int] = None, coord_y: Optional[int] = None) -> None:
    """Executa clique com o botão direito do mouse."""
    _obter_pyautogui().rightClick(x=coord_x, y=coord_y)


def drag_to(coord_x: int, coord_y: int, duration: float = 0.5, button: str = "left") -> None:
    """Arrasta o mouse até a coordenada destino."""
    _obter_pyautogui().dragTo(coord_x, coord_y, duration=duration, button=button)


def scroll(amount: int) -> None:
    """Rola a roda do mouse (positivo sobe, negativo desce)."""
    _obter_pyautogui().scroll(amount)


def type_text(text: str, interval: float = 0.05) -> None:
    """Digita texto simulando teclado físico."""
    _obter_pyautogui().typewrite(text, interval=interval)


def press(key: str) -> None:
    """Pressiona uma tecla simples."""
    _obter_pyautogui().press(key)


def hotkey(*keys: str) -> None:
    """Aciona combinação de teclas simultâneas."""
    _obter_pyautogui().hotkey(*keys)


def locate_on_screen(
    template_path: Union[str, Path],
    confidence: float = 0.9,
) -> Optional[tuple[int, int, int, int]]:
    """Localiza a imagem na tela e retorna (esquerda, topo, largura, altura)."""
    try:
        caixa = _obter_pyautogui().locateOnScreen(str(template_path), confidence=confidence)
        if caixa is None:
            return None
        return (int(caixa.left), int(caixa.top), int(caixa.width), int(caixa.height))
    except Exception as erro:
        logger.debug(f"locate_on_screen não encontrou {template_path}: {erro}")
        return None


def locate_center_on_screen(
    template_path: Union[str, Path],
    confidence: float = 0.9,
) -> Optional[tuple[int, int]]:
    """Localiza a imagem na tela e retorna o ponto central (x, y)."""
    try:
        caixa = locate_on_screen(template_path, confidence=confidence)
        if caixa is None:
            return None
        esquerda, topo, largura, altura = caixa
        return (esquerda + largura // 2, topo + altura // 2)
    except Exception:
        return None


def wait_for(
    template_path: Union[str, Path],
    timeout: float = 10.0,
    poll_interval: float = 0.12,
    confidence: float = 0.9,
) -> Optional[tuple[int, int]]:
    """Aguarda a imagem aparecer na tela até o tempo limite e retorna seu centro."""
    prazo_limite = time.time() + timeout
    while time.time() < prazo_limite:
        try:
            ponto = locate_center_on_screen(template_path, confidence=confidence)
            if ponto is not None:
                return ponto
        except Exception:
            pass
        time.sleep(poll_interval)
    return None


def click_image(
    template_path: Union[str, Path],
    confidence: float = 0.9,
    timeout: float = 5.0,
) -> bool:
    """Aguarda a imagem aparecer e clica no centro."""
    ponto = wait_for(template_path, timeout=timeout, confidence=confidence)
    if ponto is None:
        return False
    click(*ponto)
    return True


def screen_size() -> tuple[int, int]:
    """Retorna a resolução atual da tela (largura, altura)."""
    tamanho = _obter_pyautogui().size()
    return (tamanho.width, tamanho.height)


def mouse_position() -> tuple[int, int]:
    """Retorna a posição atual do cursor do mouse."""
    posicao = _obter_pyautogui().position()
    return (int(posicao.x), int(posicao.y))


def is_visible(template_path: Union[str, Path], confidence: float = 0.70) -> bool:
    """Verifica imediatamente se o template está visível na tela."""
    return locate_center_on_screen(template_path, confidence=confidence) is not None


def focar_janela(titulo_parcial: str) -> bool:
    """Traz a janela correspondente ao título parcial para o primeiro plano."""
    try:
        import pygetwindow

        for janela in pygetwindow.getAllWindows():
            if titulo_parcial.lower() in (janela.title or "").lower():
                if janela.isMinimized:
                    janela.restore()
                janela.activate()
                return True
    except Exception:
        pass

    try:
        user32 = ctypes.windll.user32
        hwnd_alvo = None

        def _buscar_hwnd(hwnd, _extra):
            nonlocal hwnd_alvo
            if not user32.IsWindowVisible(hwnd):
                return True
            tamanho = user32.GetWindowTextLengthW(hwnd)
            if tamanho <= 0:
                return True
            buffer_titulo = ctypes.create_unicode_buffer(tamanho + 1)
            user32.GetWindowTextW(hwnd, buffer_titulo, tamanho + 1)
            if titulo_parcial.lower() in buffer_titulo.value.lower():
                hwnd_alvo = hwnd
                return False
            return True

        tipo_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(tipo_callback(_buscar_hwnd), 0)

        if hwnd_alvo:
            user32.SetForegroundWindow(hwnd_alvo)
            return True
    except Exception:
        pass

    return False


def focar_senior_geral() -> bool:
    """Coloca em foco a janela ativa do Senior priorizando diálogos modais."""
    for termo in TERMOS_JANELAS_SENIOR:
        if focar_janela(termo):
            return True
    return False
