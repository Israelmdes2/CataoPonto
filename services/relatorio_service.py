import logging
from datetime import datetime
from pathlib import Path
from typing import List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.config import settings
from schemas.execucao import RegistroExecucaoColaborador

logger = logging.getLogger(__name__)

CABECALHOS_RELATORIO = [
    "Data Execução",
    "Matrícula",
    "Colaborador",
    "Email",
    "Status",
    "MotivoErro",
]


class RelatorioService:
    """Serviço responsável pela geração da planilha de controle de execução."""

    @staticmethod
    def gerar_nome_arquivo(momento_execucao: datetime | None = None) -> str:
        """Retorna o nome padronizado da planilha de controle conforme PDD."""
        data_hora = momento_execucao or datetime.now()
        marca_tempo = data_hora.strftime("%d%m%Y-%H%M")
        return f"{marca_tempo}– Envio de Cartão Ponto.xlsx"

    @classmethod
    def gerar_relatorio_execucao(
        cls,
        registros: List[RegistroExecucaoColaborador],
        pasta_destino: str | Path | None = None,
        momento_execucao: datetime | None = None,
    ) -> Path:
        """Gera a planilha Excel formatada com o resultado dos envios."""
        data_hora = momento_execucao or datetime.now()
        destino = Path(pasta_destino or settings.REDE_PASTA_RELATORIOS)
        destino.mkdir(parents=True, exist_ok=True)
        caminho_final = destino / cls.gerar_nome_arquivo(data_hora)

        planilha = openpyxl.Workbook()
        aba = planilha.active
        aba.title = "Relatório de Execução"

        preenchimento_cabecalho = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
        fonte_cabecalho = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        borda_fina = Border(
            left=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin", color="CCCCCC"),
            top=Side(style="thin", color="CCCCCC"),
            bottom=Side(style="thin", color="CCCCCC"),
        )
        alinhamento_centro = Alignment(horizontal="center", vertical="center")
        alinhamento_esquerda = Alignment(horizontal="left", vertical="center")

        aba.append(CABECALHOS_RELATORIO)
        for indice_coluna in range(1, len(CABECALHOS_RELATORIO) + 1):
            celula = aba.cell(row=1, column=indice_coluna)
            celula.fill = preenchimento_cabecalho
            celula.font = fonte_cabecalho
            celula.alignment = alinhamento_centro

        for registro in registros:
            status_texto = registro.status.value if hasattr(registro.status, "value") else str(registro.status)
            aba.append([
                registro.data_execucao,
                registro.matricula,
                registro.colaborador,
                registro.email,
                status_texto,
                registro.motivo_erro or "",
            ])
            linha_atual = aba.max_row
            for indice_coluna in range(1, len(CABECALHOS_RELATORIO) + 1):
                celula = aba.cell(row=linha_atual, column=indice_coluna)
                celula.border = borda_fina
                celula.alignment = alinhamento_centro if indice_coluna in (1, 2, 5) else alinhamento_esquerda

        for coluna in aba.columns:
            largura_maxima = max(len(str(celula.value or "")) for celula in coluna)
            letra_coluna = coluna[0].column_letter
            aba.column_dimensions[letra_coluna].width = max(largura_maxima + 4, 14)

        planilha.save(caminho_final)
        logger.info(f"Relatório de execução salvo em: {caminho_final}")
        return caminho_final
