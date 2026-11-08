import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from pypdf import PdfReader, PdfWriter

from core.config import settings

logger = logging.getLogger(__name__)


class PdfSplitterService:
    @staticmethod
    def extrair_matricula_da_pagina(texto_pagina: str) -> Optional[str]:
        """
        Busca o identificador do empregado/matrícula no texto da página.
        Exemplo exato do relatório 702 da Unimed Vale do Aço:
        'Empregado:    3898         CLEMILDA BELIZARIO LOURENCO LIDA'
        """
        if not texto_pagina:
            return None

        # Regex para capturar após 'Empregado:' os dígitos do código/matrícula
        match = re.search(r"empregado\s*:\s*(\d+)", texto_pagina, re.IGNORECASE)
        if match:
            # Retorna o código numérico limpo (ex: '3898')
            return str(int(match.group(1)))

        # Fallback para regex genérico de matrícula / cadastro / colaborador
        match_alt = re.search(r"(?:cadastro|matr[íi]cula|colaborador)\s*:\s*(\d+)", texto_pagina, re.IGNORECASE)
        if match_alt:
            return str(int(match_alt.group(1)))

        return None

    @classmethod
    def dividir_cartoes_ponto(
        cls,
        caminho_consolidado: str | Path,
        pasta_destino: Optional[str | Path] = None,
    ) -> Dict[str, Path]:
        """
        PASSO 8 DO PDD:
        Lê o PDF consolidado gerado pelo Senior (ex: HRCP702_08112026.pdf),
        identifica dentro de cada página o código do Empregado
        e salva cada cartão individual com o número desse código na pasta de rede informada:
        V:\\grp-aud-doc\\DIGITALY_CARTAO_PONTO\\individuais\\<codigo>.pdf (ex: 3898.pdf).

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

        # Mapeamento: matricula -> lista de indices de paginas (agrupa se um colaborador tiver mais de 1 página)
        paginas_por_matricula: Dict[str, List[int]] = {}
        matricula_atual: Optional[str] = None

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

        # Grava cada PDF individualmente com o número do código como nome
        arquivos_gerados: Dict[str, Path] = {}

        for matricula, paginas_indices in paginas_por_matricula.items():
            writer = PdfWriter()
            for p_idx in paginas_indices:
                writer.add_page(reader.pages[p_idx])

            # Conforme especificado: salva com o número do código (ex: 3898.pdf)
            nome_arquivo = f"{matricula}.pdf"
            caminho_saida = destino / nome_arquivo

            with open(caminho_saida, "wb") as f_out:
                writer.write(f_out)

            arquivos_gerados[matricula] = caminho_saida
            logger.info(f"Cartão individual salvo: {caminho_saida.name} ({len(paginas_indices)} pág.) em '{destino}'")

        logger.info(
            f"Passo 8 concluído com sucesso: {len(arquivos_gerados)} cartões ponto individuais salvos em '{destino}'."
        )
        return arquivos_gerados
