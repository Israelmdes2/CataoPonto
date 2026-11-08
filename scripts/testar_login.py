"""
Script para testar isoladamente o Passo 2 e Passo 3 do PDD:
- Abertura do sistema Senior (Controle de Ponto e Refeitório)
- Localização dos campos por Imagem (OpenCV + PyAutoGUI)
- Preenchimento de Login e Senha
- Clique em 'Autenticar'
- Registro de screenshot para auditoria visual
"""
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pyautogui
from core.config import settings
from core.logger import get_logger
from infrastructure.automation import gui, vision

logger = get_logger("login_test")


def testar_login_senior(usuario: str = None, senha: str = None, tirar_print: bool = True):
    print("=" * 60)
    print("INICIANDO TESTE DO FLUXO DE LOGIN - SENIOR DESKTOP")
    print("=" * 60)

    user = (usuario or settings.SENIOR_LOGIN or "usuario_teste").strip().lower()
    password = senha or settings.SENIOR_PASSWORD or "senha_teste"

    prints_dir = ROOT_DIR / "assets" / "prints"
    templates_dir = ROOT_DIR / "assets" / "templates"
    prints_dir.mkdir(parents=True, exist_ok=True)

    print(f"1. Usuário configurado: {user}")
    print(f"2. Templates carregados de: {templates_dir}")

    # 1. Tira print inicial da tela antes de começar
    if tirar_print:
        print_antes = prints_dir / "01_antes_login.png"
        try:
            img = pyautogui.screenshot()
            img.save(str(print_antes))
            print(f"-> Print inicial salvo: {print_antes.name}")
        except Exception as e:
            print(f"Aviso ao tirar screenshot: {e}")

    # 1.5. Verifica se o ícone do módulo de homologação está na tela
    icone_mod = templates_dir / "homologacao" / "icone_modulo.png"
    if not icone_mod.exists():
        icone_mod = templates_dir / "icone_modulo.png"
    if icone_mod.exists():
        pos_mod = gui.wait_for(str(icone_mod), timeout=3, confidence=0.75)
        if pos_mod:
            print(f"-> Ícone do módulo detectado em {pos_mod}. Clicando...")
            gui.click(pos_mod[0], pos_mod[1])
            time.sleep(2)

    # 2. Procura pelo botão Autenticar ou campo de login
    # Busca em homologacao primeiro, com fallback para raiz
    btn_template = templates_dir / "homologacao" / "botao_autenticar.png"
    if not btn_template.exists():
        btn_template = templates_dir / "botao_autenticar.png"

    login_template = templates_dir / "homologacao" / "campo_login.png"
    if not login_template.exists():
        login_template = templates_dir / "campo_login.png"

    print("Procurando tela de login do Senior por correspondência de imagem...")
    pos_btn = None
    if btn_template.exists():
        pos_btn = gui.locate_center_on_screen(str(btn_template), confidence=0.8)

    if pos_btn:
        print(f"Botão 'Autenticar' localizado nas coordenadas: {pos_btn}")
        # Ancoragem visual: O campo de usuário fica ~55px acima do botão
        x_login = pos_btn[0]
        y_login = pos_btn[1] - 55

        print(f"Clicando no campo de Login em ({x_login}, {y_login})...")
        gui.click(x_login, y_login)
        time.sleep(0.5)

        # Limpa o campo e digita o login
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        gui.type_text(user)
        print("Login digitado.")

        # Pressiona TAB para ir para o campo de senha
        gui.press("tab")
        time.sleep(0.5)
        gui.type_text(password)
        print("Senha digitada.")

        # Clica em Autenticar
        time.sleep(0.5)
        gui.click(pos_btn[0], pos_btn[1])
        print("Clicado no botão 'Autenticar'.")
    else:
        print("Botão 'Autenticar' não detectado diretamente na tela atual.")
        print("Certifique-se de que a janela de Autenticação do Senior está visível na tela.")

    # 3. Tira print após a tentativa de login
    time.sleep(3)
    if tirar_print:
        print_depois = prints_dir / "02_apos_login.png"
        try:
            img = pyautogui.screenshot()
            img.save(str(print_depois))
            print(f"-> Print após tentativa de login salvo: {print_depois.name}")
        except Exception as e:
            print(f"Aviso ao tirar screenshot: {e}")

    print("=" * 60)
    print("TESTE DE LOGIN CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    testar_login_senior()

