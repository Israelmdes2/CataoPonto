import logging
from pathlib import Path
from typing import List, Optional, Dict
import openpyxl

from core.config import settings
from schemas.colaborador import Colaborador

logger = logging.getLogger(__name__)


class ColaboradoresService:
    @staticmethod
    def carregar_colaboradores(caminho_arquivo: Optional[str] = None) -> List[Colaborador]:
        """
        Lê a planilha de colaboradores fornecida pela Unimed:
        'RELAÇÃO E-MAIL COLABORADORES- ATUALIZADO.xlsx'
        - Linha de cabeçalho:
          - Coluna A: Cadastro (código do empregado)
          - Coluna C: Nome do empregado
          - Coluna G: E-mail do empregado
        """
        caminho = Path(caminho_arquivo or settings.PLANILHA_COLABORADORES_PATH)
        if not caminho.exists():
            raise FileNotFoundError(f"Planilha de colaboradores não encontrada em: {caminho}")

        logger.info(f"Lendo colaboradores da planilha: {caminho}...")
        wb = openpyxl.load_workbook(caminho, data_only=True)
        sheet = wb.active

        colaboradores: List[Colaborador] = []
        linha_cabecalho = None
        col_cadastro = None
        col_nome = None
        col_email = None

        # 1. Procura dinamicamente a linha que contém os cabeçalhos nas primeiras 10 linhas
        for r in range(1, min(12, sheet.max_row + 1)):
            for c in range(1, min(15, sheet.max_column + 1)):
                val = str(sheet.cell(r, c).value or "").strip().lower()
                if "cadastro" in val or "matrícula" in val or "matricula" in val:
                    col_cadastro = c
                    linha_cabecalho = r
                elif "nome" in val or "empregado" in val or "colaborador" in val:
                    col_nome = c
                elif "e-mail" in val or "email" in val:
                    col_email = c

            if col_cadastro and col_email:
                linha_cabecalho = r
                break

        # Fallback fixo para a planilha da Unimed: Coluna A (1), C (3), G (7)
        if not col_cadastro:
            col_cadastro = 1
        if not col_nome:
            col_nome = 3
        if not col_email:
            col_email = 7
        if not linha_cabecalho:
            linha_cabecalho = 3

        logger.info(
            f"Mapeamento de colunas da planilha (cabeçalho na linha {linha_cabecalho}): "
            f"Cadastro=Coluna {col_cadastro}, Nome=Coluna {col_nome}, Email=Coluna {col_email}"
        )

        # 2. Itera a partir da linha seguinte ao cabeçalho
        for r in range(linha_cabecalho + 1, sheet.max_row + 1):
            val_cad = sheet.cell(r, col_cadastro).value
            val_nome = sheet.cell(r, col_nome).value
            val_email = sheet.cell(r, col_email).value

            if val_cad is None or val_email is None:
                continue

            # Sanitização do código de cadastro (ex: 4821 ou 4821.0 -> '4821')
            if isinstance(val_cad, (int, float)):
                matricula = str(int(val_cad)).strip()
            else:
                matricula = str(val_cad).strip()

            nome = str(val_nome).strip() if val_nome else f"Colaborador {matricula}"
            email = str(val_email).strip()

            if matricula and email:
                colaboradores.append(
                    Colaborador(
                        matricula=matricula,
                        nome=nome,
                        setor="",
                        email=email,
                    )
                )

        logger.info(f"Total de {len(colaboradores)} colaboradores carregados com sucesso da planilha.")
        return colaboradores

    @classmethod
    def carregar_mapa_colaboradores(cls, caminho_arquivo: Optional[str] = None) -> Dict[str, Colaborador]:
        """Retorna os colaboradores em um dicionário mapeado por matrícula: {matricula: Colaborador}."""
        lista = cls.carregar_colaboradores(caminho_arquivo)
        return {c.matricula: c for c in lista}
