import subprocess
import time
from pathlib import Path
import pyautogui

def capturar_tela_login():
    print("Iniciando Senior Controle de Ponto (Homologação)...")
    
    # Caminho do executável e argumentos
    exe_path = r"\\SRVVETORH-HML\Senior_HML\Iniciar.exe"
    args = [exe_path, "-SystemModule:VETORH.RONDA", '-seniordir:C:\\Senior-hml\\']
    
    try:
        proc = subprocess.Popen(args)
        print(f"Processo disparado. PID: {proc.pid}. Aguardando janela carregar (15 segundos)...")
        time.sleep(15)
    except Exception as e:
        print(f"Erro ao disparar processo: {e}")
        return False
        
    out_dir = Path(r"C:\Digitaly\EnvioCartaoPonto\assets\prints")
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / "tela_login_senior.png"
    
    img = pyautogui.screenshot()
    img.save(str(screenshot_path))
    print(f"Screenshot salvo com sucesso em: {screenshot_path}")
    print(f"Dimensões da imagem: {img.size}")
    return screenshot_path

if __name__ == "__main__":
    capturar_tela_login()
