import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pymupdf

from core.config import settings

logger = logging.getLogger(__name__)


class PdfSplitterService:
    """Serviço responsável por dividir o PDF consolidado em cartões individuais."""

    @staticmethod
    def extrair_matricula_da_pagina(texto_pagina: str) -> Optional[str]:
        """Extrai o código de matrícula do colaborador a partir do texto extraído da página."""
        if not texto_pagina:
            return None

        # No PDF exportado pelo Senior, os rótulos vêm agrupados antes dos valores em linhas separadas
        correspondencia = re.search(r"Empregado:.*?\n\s*(\d{3,6})\s*\n", texto_pagina, re.DOTALL)
        if correspondencia:
            return correspondencia.group(1).strip()

        correspondencia_linha = re.search(
            r"(?:Empregado|Cadastro|Matr[íi]cula)\s*:\s*(\d+)",
            texto_pagina,
            re.IGNORECASE,
        )
        if correspondencia_linha:
            return str(int(correspondencia_linha.group(1)))

        correspondencia_isolada = re.search(r"\n\s*(\d{3,6})\s*\n[A-Z\s]{4,}", texto_pagina)
        if correspondencia_isolada:
            return correspondencia_isolada.group(1).strip()

        return None

    @classmethod
    def dividir_cartoes_ponto(
        cls,
        caminho_consolidado: str | Path,
        pasta_destino: Optional[str | Path] = None,
    ) -> Dict[str, Path]:
        """Separa o PDF consolidado em arquivos individuais nomeados com a matrícula."""
        caminho_pdf = Path(caminho_consolidado)
        if not caminho_pdf.exists():
            raise FileNotFoundError(f"Arquivo consolidado não encontrado: {caminho_pdf}")

        destino = Path(pasta_destino or settings.REDE_PASTA_INDIVIDUAIS)
        destino.mkdir(parents=True, exist_ok=True)

        arquivos_gerados: Dict[str, Path] = {}
        documento = pymupdf.open(str(caminho_pdf))
        try:
            total_paginas = len(documento)
            logger.info(f"PDF consolidado '{caminho_pdf.name}' carregado com {total_paginas} páginas.")

            paginas_por_matricula: Dict[str, List[int]] = {}
            matricula_atual: Optional[str] = None
            paginas_sem_matricula = 0

            for indice_pagina, pagina in enumerate(documento):
                matricula = cls.extrair_matricula_da_pagina(pagina.get_text())
                if matricula:
                    matricula_atual = matricula
                elif not matricula_atual:
                    paginas_sem_matricula += 1
                    continue

                if matricula_atual not in paginas_por_matricula:
                    paginas_por_matricula[matricula_atual] = []
                paginas_por_matricula[matricula_atual].append(indice_pagina)

            logger.info(
                f"Mapeamento concluído: {len(paginas_por_matricula)} colaboradores em {total_paginas} páginas "
                f"({paginas_sem_matricula} páginas ignoradas)."
            )

            total_colaboradores = len(paginas_por_matricula)
            for indice, (matricula, indices_paginas) in enumerate(paginas_por_matricula.items(), start=1):
                caminho_saida = destino / f"{matricula}.pdf"
                subdocumento = pymupdf.open()
                try:
                    for pagina_idx in indices_paginas:
                        subdocumento.insert_pdf(documento, from_page=pagina_idx, to_page=pagina_idx)
                    subdocumento.save(str(caminho_saida), garbage=4, deflate=True)
                finally:
                    subdocumento.close()

                arquivos_gerados[matricula] = caminho_saida
                if indice % 100 == 0 or indice == total_colaboradores:
                    logger.info(f"Progresso da separação: {indice}/{total_colaboradores} cartões salvos.")
        finally:
            documento.close()

        return arquivos_gerados
