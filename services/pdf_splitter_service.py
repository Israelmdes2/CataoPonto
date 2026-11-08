import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import pymupdf

from core.config import settings

logger = logging.getLogger(__name__)


class PdfSplitterService:
    @staticmethod
    def extrair_matricula_da_pagina(texto_pagina: str) -> Optional[str]:
        """
        Extrai a matrícula/código do empregado do relatório 702 da Senior.
        No texto extraído do Senior, a estrutura vem com quebras de linha entre as colunas:
        'Empregado:\nCargo:\nLocalização:\n     3898\nCLEMILDA BELIZARIO LOURENCO LIDA'
        """
        if not texto_pagina:
            return None

        # Regex 1 específica para a formatação do relatório 702 do Senior
        m = re.search(r"Empregado:.*?\n\s*(\d{3,6})\s*\n", texto_pagina, re.DOTALL)
        if m:
            return m.group(1).strip()

        # Fallback 1: 'Empregado: 3898' em linha única
        m2 = re.search(r"(?:Empregado|Cadastro|Matr[íi]cula)\s*:\s*(\d+)", texto_pagina, re.IGNORECASE)
        if m2:
            return str(int(m2.group(1)))

        # Fallback 2: código numérico isolado antes de nome em maiúsculas
        m3 = re.search(r"\n\s*(\d{3,6})\s*\n[A-Z\s]{4,}", texto_pagina)
        if m3:
            return m3.group(1).strip()

        return None

    @classmethod
    def dividir_cartoes_ponto(
        cls,
        caminho_consolidado: str | Path,
        pasta_destino: Optional[str | Path] = None,
    ) -> Dict[str, Path]:
        """
        PASSO 8 DO PDD (ULTRA-RÁPIDO COM PyMuPDF):
        Lê o PDF consolidado gerado pelo Senior (todas as centenas de páginas em poucos segundos),
        agrupa as páginas por código de empregado e salva cada cartão individual
        estritamente com o número da matrícula: <codigo>.pdf (ex: 3898.pdf).

        Retorna: Dict {matricula: caminho_pdf_individual}
        """
        caminho_pdf = Path(caminho_consolidado)
        if not caminho_pdf.exists():
            raise FileNotFoundError(f"Arquivo consolidado não encontrado: {caminho_pdf}")

        destino = Path(pasta_destino or settings.REDE_PASTA_INDIVIDUAIS)
        destino.mkdir(parents=True, exist_ok=True)

        logger.info(f"Iniciando leitura de alta performance do PDF '{caminho_pdf.name}' via PyMuPDF...")
        doc = pymupdf.open(str(caminho_pdf))
        total_paginas = len(doc)
        logger.info(f"PDF consolidado carregado com {total_paginas} páginas!")

        # 1. Mapeamento ultra-rápido: matricula -> [indices das páginas]
        paginas_por_matricula: Dict[str, List[int]] = {}
        matricula_atual: Optional[str] = None
        sem_matricula = 0

        for idx, page in enumerate(doc):
            texto = page.get_text()
            matricula = cls.extrair_matricula_da_pagina(texto)

            if matricula:
                matricula_atual = matricula
            elif not matricula_atual:
                sem_matricula += 1
                continue

            if matricula_atual not in paginas_por_matricula:
                paginas_por_matricula[matricula_atual] = []
            paginas_por_matricula[matricula_atual].append(idx)

        logger.info(
            f"Mapeamento concluído: {len(paginas_por_matricula)} colaboradores distintos "
            f"identificados em {total_paginas} páginas ({sem_matricula} páginas não identificadas)."
        )

        # 2. Gravação rápida de cada PDF individualmente
        arquivos_gerados: Dict[str, Path] = {}
        total_colabs = len(paginas_por_matricula)

        for i, (matricula, paginas_indices) in enumerate(paginas_por_matricula.items(), start=1):
            caminho_saida = destino / f"{matricula}.pdf"

            sub_doc = pymupdf.open()
            for p_idx in paginas_indices:
                sub_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)

            sub_doc.save(str(caminho_saida), garbage=4, deflate=True)
            sub_doc.close()

            arquivos_gerados[matricula] = caminho_saida

            if i % 100 == 0 or i == total_colabs:
                logger.info(f"Progresso: {i}/{total_colabs} cartões individuais salvos...")

        doc.close()
        logger.info(
            f"Passo 8 concluído com sucesso: {len(arquivos_gerados)} cartões ponto individuais salvos em '{destino}'."
        )
        return arquivos_gerados
