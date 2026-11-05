import logging
from pathlib import Path
from typing import List, Optional
import openpyxl

from core.config import settings
from schemas.colaborador import Colaborador

logger = logging.getLogger(__name__)


class ColaboradoresService:
    @staticmethod
    def carregar_colaboradores(caminho_arquivo: Optional[str] = None) -> List[Colaborador]:
        """
        Lê a planilha de colaboradores fornecida pela Unimed contendo:
        Nome, Matrícula, Setor, Email.
        """
        caminho = Path(caminho_arquivo or settings.PLANILHA_COLABORADORES_PATH)
        if not caminho.exists():
            logger.warning(f"Planilha de colaboradores não encontrada em: {caminho}. Criando modelo de exemplo.")
            ColaboradoresService.criar_planilha_modelo(caminho)

        wb = openpyxl.load_workbook(caminho, data_only=True)
        sheet = wb.active

        colaboradores: List[Colaborador] = []
        headers = {}

        # Mapeia cabeçalhos da primeira linha
        for col_idx, cell in enumerate(sheet[1], start=1):
            if cell.value:
                val = str(cell.value).strip().lower()
                if "matricula" in val or "matrícula" in val or "crachá" in val:
                    headers["matricula"] = col_idx
                elif "nome" in val or "colaborador" in val or "empregado" in val:
                    headers["nome"] = col_idx
                elif "setor" in val or "departamento" in val:
                    headers["setor"] = col_idx
                elif "email" in val or "e-mail" in val:
                    headers["email"] = col_idx

        if "matricula" not in headers or "email" not in headers:
            raise ValueError(
                f"A planilha precisa conter pelo menos as colunas 'Matrícula' e 'Email'. Cabeçalhos encontrados: {headers}"
            )

        # Itera sobre as linhas de dados
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row:
                continue

            matricula_raw = row[headers["matricula"] - 1] if headers.get("matricula") else None
            nome_raw = row[headers["nome"] - 1] if headers.get("nome") else None
            setor_raw = row[headers["setor"] - 1] if headers.get("setor") else ""
            email_raw = row[headers["email"] - 1] if headers.get("email") else None

            if not matricula_raw or not email_raw:
                continue

            # Sanitização de matrícula (caso venha 12345.0 do Excel)
            if isinstance(matricula_raw, float):
                matricula = str(int(matricula_raw)).strip()
            else:
                matricula = str(matricula_raw).strip()

            nome = str(nome_raw).strip() if nome_raw else f"Colaborador {matricula}"
            setor = str(setor_raw).strip() if setor_raw else ""
            email = str(email_raw).strip()

            colaboradores.append(
                Colaborador(
                    matricula=matricula,
                    nome=nome,
                    setor=setor,
                    email=email,
                )
            )

        logger.info(f"Total de {len(colaboradores)} colaboradores carregados com sucesso da planilha.")
        return colaboradores

    @staticmethod
    def criar_planilha_modelo(caminho: Path) -> None:
        """Cria uma planilha modelo com dados de exemplo se o arquivo não existir."""
        caminho.parent.mkdir(parents=True, exist_ok=True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Colaboradores"
        ws.append(["Nome", "Matrícula", "Setor", "Email"])
        ws.append(["Exemplo Colaborador 1", "1001", "Recursos Humanos", "colaborador1@unimedvaledoaco.coop.br"])
        ws.append(["Exemplo Colaborador 2", "1002", "Pronto Atendimento", "colaborador2@unimedvaledoaco.coop.br"])
        wb.save(caminho)
        logger.info(f"Planilha de exemplo gerada em: {caminho}")

