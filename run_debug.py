"""Script de execução direta para depuração (F5) no IDE."""

import sys
from pathlib import Path

DIRETORIO_RAIZ = Path(__file__).resolve().parent
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

from manage import senior_fluxo

if __name__ == "__main__":
    senior_fluxo(
        usuario="",
        senha="",
        abrir=True,
        ambiente="producao",
        timeout=60,
        confidence=0.70,
        selecionar_702=True,
    )
