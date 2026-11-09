"""
Script de execução direta para Depuração (F5) no VS Code / PyCharm.
Executa o fluxo completo do RPA Senior de ponta a ponta:
Passos 1 a 10 (Login -> Navegação -> Modelo 702 -> Datas/Ok -> Salvar PDF -> Separar PDFs -> E-mails).
"""
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path de importação
raiz = Path(__file__).resolve().parent
if str(raiz) not in sys.path:
    sys.path.insert(0, str(raiz))

from manage import senior_fluxo

if __name__ == "__main__":
    print("=================================================================")
    print("  Iniciando RPA Senior - Fluxo Completo Ponta a Ponta (DEBUG F5) ")
    print("=================================================================")
    senior_fluxo(
        usuario="",
        senha="",
        abrir=True,
        ambiente="homologacao",
        timeout=60,
        confidence=0.70,
        selecionar_702=True,
    )
