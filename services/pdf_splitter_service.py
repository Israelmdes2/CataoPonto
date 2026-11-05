import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple
from pypdf import PdfReader, PdfWriter

from core.config import settings

logger = logging.getLogger(__name__)


class PdfSplitterService:
    @staticmethod
    def extrair_matricula_da_pagina(texto_pagina: str) -> str | None:
        """
        Busca o identificador do empregado/matrícula no texto da página.
        Exemplos típicos do Senior:
        'Empregado: 00012345' ou 'Empregado: 12345' ou 'Colaborador: 12345'
        """
        if not texto_pagina:
            return None

        # Regex para capturar após "Empregado:" ou "Empregado :" os dígitos da matrícula
        match = re.search(r"empregado\s*:\s*(\d+)", texto_pagina, re.IGNORECASE)
        if match:
            # Remove zeros à esquerda para unificar com matrículas da planilha
            return str(int(match.group(1)))

        # Fallback para regex genérico de matrícula
        match_mat = re.search(r"matr[íi]cula\s*:\s*(\d+)", texto_pagina, re.IGNORECASE)
        if match_mat:
            return str(int(match_mat.group(1)))

        return None

    @classmethod
    def dividir_cartoes_ponto(
        cls,
        caminho_consolidado: str | Path,
        pasta_destino: str | Path | None = None,
    ) -> Dict[str, Path]:
        """
        Lê o PDF consolidado gerado pelo Senior, agrupa as páginas por matrícula
        e salva cada cartão de ponto individualmente.
        Retorna: Dict {matricula: caminho_pdf_individual}
        """
        caminho_pdf = Path(caminho_consolidado)
        if not caminho_pdf.exists():
            raise FileNotFoundError(f"Arquivo consolidado não encontrado: {caminho_pdf}")

        destino = Path(pasta_destino or settings.REDE_PASTA_INDIVIDUAIS)
        destino.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(caminho_pdf))
        total_paginas = len(reader.pages)
        logger.info(f"Processando PDF consolidado '{caminho_pdf.name}' com {total_paginas} páginas...")

        # Mapeamento: matricula -> lista de indices de paginas
        paginas_por_matricula: Dict[str, List[int]] = {}
        matricula_atual: str | None = None

        for idx, page in enumerate(reader.pages):
            texto = page.extract_text() or ""
            matricula = cls.extrair_matricula_da_pagina(texto)

            if matricula:
                matricula_atual = matricula
            elif not matricula_atual:
                logger.warning(f"Página {idx + 1} sem identificação de Empregado e sem matrícula anterior definida.")
                continue

            if matricula_atual not in paginas_por_matricula:
                paginas_por_matricula[matricula_atual] = []
            paginas_por_matricula[matricula_atual].append(idx)

        # Agora grava cada PDF individualmente
        arquivos_gerados: Dict[str, Path] = {}

        for matricula, paginas_indices in paginas_por_matricula.items():
            writer = PdfWriter()
            for p_idx in paginas_indices:
                writer.add_page(reader.pages[p_idx])

            nome_arquivo = f"Cartao_Ponto_{matricula}.pdf"
            caminho_saida = destino / nome_arquivo

            with open(caminho_saida, "wb") as f_out:
                writer.write(f_out)

            arquivos_gerados[matricula] = caminho_saida
            logger.debug(f"Salvo cartão ponto da matrícula {matricula}: {caminho_saida.name} ({len(paginas_indices)} pág.)")

        logger.info(
            f"Divisão concluída: {len(arquivos_gerados)} cartões ponto individuais salvos em '{destino}'."
        )
        return arquivos_gerados

