import logging
from datetime import datetime
from pathlib import Path
from typing import List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from core.config import settings
from schemas.execucao import RegistroExecucaoColaborador

logger = logging.getLogger(__name__)


class RelatorioService:
    @staticmethod
    def gerar_nome_arquivo(momento_execucao: datetime | None = None) -> str:
        """
        Formato especificado no PDD:
        DDMMAAAA-HHMM– Envio de Cartão Ponto.xlsx
        """
        dt = momento_execucao or datetime.now()
        timestamp = dt.strftime("%d%m%Y-%H%M")
        return f"{timestamp}– Envio de Cartão Ponto.xlsx"

    @classmethod
    def gerar_relatorio_execucao(
        cls,
        registros: List[RegistroExecucaoColaborador],
        pasta_destino: str | Path | None = None,
        momento_execucao: datetime | None = None,
    ) -> Path:
        """
        Cria a planilha Excel de controle de execução com cabeçalho formatado e registros.
        """
        dt = momento_execucao or datetime.now()
        destino = Path(pasta_destino or settings.REDE_PASTA_RELATORIOS)
        destino.mkdir(parents=True, exist_ok=True)

        nome_arquivo = cls.gerar_nome_arquivo(dt)
        caminho_final = destino / nome_arquivo

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Relatório de Execução"

        # Título / Cabeçalho da tabela
        headers = [
            "Data Execução",
            "Matrícula",
            "Colaborador",
            "Email",
            "Status",
            "MotivoErro",
        ]

        # Estilos
        header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin", color="CCCCCC"),
            top=Side(style="thin", color="CCCCCC"),
            bottom=Side(style="thin", color="CCCCCC"),
        )
        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")

        ws.append(headers)

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = align_center

        # Preenchimento das linhas
        for reg in registros:
            row_data = [
                reg.data_execucao,
                reg.matricula,
                reg.colaborador,
                reg.email,
                reg.status.value if hasattr(reg.status, "value") else str(reg.status),
                reg.motivo_erro or "",
            ]
            ws.append(row_data)
            current_row = ws.max_row
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.border = thin_border
                cell.alignment = align_center if col_idx in [1, 2, 5] else align_left

        # Ajuste de largura automática das colunas
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = col[0].column_letter
            ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        wb.save(caminho_final)
        logger.info(f"Relatório de execução salvo com sucesso em: {caminho_final}")
        return caminho_final

