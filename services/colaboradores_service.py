import logging
from pathlib import Path
from typing import Dict, List, Optional

import openpyxl

from core.config import settings
from schemas.colaborador import Colaborador

logger = logging.getLogger(__name__)

COLUNA_CADASTRO_PADRAO = 1
COLUNA_NOME_PADRAO = 3
COLUNA_EMAIL_PADRAO = 7
LINHA_CABECALHO_PADRAO = 3


class ColaboradoresService:
    """Serviço responsável pela leitura da planilha de colaboradores."""

    @staticmethod
    def _identificar_colunas(aba) -> tuple[int, int, int, int]:
        """Localiza dinamicamente a linha de cabeçalho e as colunas de cadastro, nome e e-mail."""
        col_cadastro = None
        col_nome = None
        col_email = None
        linha_cabecalho = None

        for indice_linha in range(1, min(12, aba.max_row + 1)):
            for indice_coluna in range(1, min(15, aba.max_column + 1)):
                texto_celula = str(aba.cell(indice_linha, indice_coluna).value or "").strip().lower()
                if "cadastro" in texto_celula or "matrícula" in texto_celula or "matricula" in texto_celula:
                    col_cadastro = indice_coluna
                    linha_cabecalho = indice_linha
                elif "nome" in texto_celula or "empregado" in texto_celula or "colaborador" in texto_celula:
                    col_nome = indice_coluna
                elif "e-mail" in texto_celula or "email" in texto_celula:
                    col_email = indice_coluna

            if col_cadastro and col_email:
                linha_cabecalho = indice_linha
                break

        # Fallback para o layout fixo oficial da planilha da Unimed (colunas A, C e G)
        return (
            linha_cabecalho or LINHA_CABECALHO_PADRAO,
            col_cadastro or COLUNA_CADASTRO_PADRAO,
            col_nome or COLUNA_NOME_PADRAO,
            col_email or COLUNA_EMAIL_PADRAO,
        )

    @classmethod
    def carregar_colaboradores(cls, caminho_arquivo: Optional[str] = None) -> List[Colaborador]:
        """Carrega os colaboradores ativos com matrícula e e-mail preenchidos."""
        caminho = Path(caminho_arquivo or settings.PLANILHA_COLABORADORES_PATH)
        if not caminho.exists():
            raise FileNotFoundError(f"Planilha de colaboradores não encontrada em: {caminho}")

        planilha = openpyxl.load_workbook(caminho, data_only=True)
        try:
            aba = planilha.active
            linha_cabecalho, col_cadastro, col_nome, col_email = cls._identificar_colunas(aba)
            logger.info(
                f"Mapeamento da planilha (linha {linha_cabecalho}): "
                f"Cadastro={col_cadastro}, Nome={col_nome}, Email={col_email}"
            )

            colaboradores: List[Colaborador] = []
            for indice_linha in range(linha_cabecalho + 1, aba.max_row + 1):
                valor_cadastro = aba.cell(indice_linha, col_cadastro).value
                valor_nome = aba.cell(indice_linha, col_nome).value
                valor_email = aba.cell(indice_linha, col_email).value

                if valor_cadastro is None or valor_email is None:
                    continue

                if isinstance(valor_cadastro, (int, float)):
                    matricula = str(int(valor_cadastro)).strip()
                else:
                    matricula = str(valor_cadastro).strip()

                nome = str(valor_nome).strip() if valor_nome else f"Colaborador {matricula}"
                email = str(valor_email).strip()

                if matricula and email:
                    colaboradores.append(
                        Colaborador(
                            matricula=matricula,
                            nome=nome,
                            setor="",
                            email=email,
                        )
                    )
        finally:
            planilha.close()

        logger.info(f"Total de {len(colaboradores)} colaboradores carregados com sucesso.")
        return colaboradores

    @classmethod
    def carregar_mapa_colaboradores(cls, caminho_arquivo: Optional[str] = None) -> Dict[str, Colaborador]:
        """Retorna os colaboradores indexados pela matrícula."""
        lista_colaboradores = cls.carregar_colaboradores(caminho_arquivo)
        return {colaborador.matricula: colaborador for colaborador in lista_colaboradores}
