import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from core.config import settings
from schemas.colaborador import Colaborador
from schemas.execucao import (
    ExecucaoResponse,
    ModoExecucao,
    PeriodoCartao,
    RegistroExecucaoColaborador,
    StatusExecucao,
)
from services.colaboradores_service import ColaboradoresService
from services.email_service import EmailService
from services.pdf_splitter_service import PdfSplitterService
from services.relatorio_service import RelatorioService
from services.senior_service import SeniorService

logger = logging.getLogger(__name__)


class OrquestradorCartaoPonto:
    """Orquestrador completo do fluxo de extração, separação e envio de cartões de ponto."""

    def __init__(self):
        self.senior_service = SeniorService()
        self.colaboradores_service = ColaboradoresService()
        self.splitter_service = PdfSplitterService()
        self.email_service = EmailService()
        self.relatorio_service = RelatorioService()

    def _obter_mapa_pdfs(
        self,
        caminho_pdf_consolidado: Path,
        extrair_senior: bool,
        caminho_consolidado_existente: Optional[str],
        periodo: PeriodoCartao,
    ) -> Dict[str, Path]:
        """Obtém ou extrai o PDF consolidado e retorna o mapa de cartões individuais."""
        if caminho_consolidado_existente and Path(caminho_consolidado_existente).exists():
            caminho_pdf_consolidado = Path(caminho_consolidado_existente)
        elif extrair_senior:
            try:
                _, caminho_extraido = self.senior_service.executar_fluxo_extracao(
                    caminho_saida_pdf=caminho_pdf_consolidado,
                    modo=periodo.modo_aplicado,
                )
                if caminho_extraido:
                    caminho_pdf_consolidado = caminho_extraido
            except Exception as erro:
                logger.error(f"Erro durante a extração no Senior: {erro}", exc_info=True)

        if caminho_pdf_consolidado.exists():
            try:
                return self.splitter_service.dividir_cartoes_ponto(
                    caminho_consolidado=caminho_pdf_consolidado,
                    pasta_destino=settings.REDE_PASTA_INDIVIDUAIS,
                )
            except Exception as erro:
                logger.error(f"Erro na separação do PDF consolidado: {erro}", exc_info=True)
                return {}

        mapa_existente: Dict[str, Path] = {}
        pasta_individuais = Path(settings.REDE_PASTA_INDIVIDUAIS)
        if pasta_individuais.exists():
            for arquivo in pasta_individuais.glob("*.pdf"):
                matricula = arquivo.stem.replace("Cartao_Ponto_", "")
                mapa_existente[matricula] = arquivo
        return mapa_existente

    def _processar_colaborador(
        self,
        colaborador: Colaborador,
        mapa_pdfs_individuais: Dict[str, Path],
        data_execucao: str,
        modo_aplicado: str,
        enviar_email: bool,
    ) -> RegistroExecucaoColaborador:
        """Processa o envio individual de um colaborador e retorna seu registro de auditoria."""
        registro = RegistroExecucaoColaborador(
            data_execucao=data_execucao,
            matricula=colaborador.matricula,
            colaborador=colaborador.nome,
            email=colaborador.email,
            status=StatusExecucao.PENDENTE,
            motivo_erro="",
        )

        matricula_limpa = str(int(colaborador.matricula)) if colaborador.matricula.isdigit() else colaborador.matricula
        caminho_anexo = mapa_pdfs_individuais.get(colaborador.matricula) or mapa_pdfs_individuais.get(matricula_limpa)

        if not caminho_anexo or not Path(caminho_anexo).exists():
            registro.status = StatusExecucao.ERRO
            registro.motivo_erro = f"Cartão de ponto PDF não localizado para a matrícula {colaborador.matricula}."
            return registro

        if not enviar_email:
            registro.status = StatusExecucao.SUCESSO
            registro.motivo_erro = "Processado com sucesso (envio de e-mail desativado)."
            return registro

        try:
            self.email_service.enviar_cartao_ponto(
                destinatario_email=colaborador.email,
                nome_colaborador=colaborador.nome,
                caminho_pdf_anexo=caminho_anexo,
                modo=modo_aplicado,
            )
            registro.status = StatusExecucao.SUCESSO
        except Exception as erro_envio:
            registro.status = StatusExecucao.ERRO
            registro.motivo_erro = f"Falha no envio de e-mail: {erro_envio}"

        return registro

    def executar(
        self,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
        enviar_email: bool = True,
        extrair_senior: bool = True,
        caminho_consolidado_existente: Optional[str] = None,
        matriculas_filtro: Optional[List[str]] = None,
    ) -> ExecucaoResponse:
        """Executa o fluxo completo de extração, separação e disparo de cartões de ponto."""
        momento_inicio = datetime.now()
        data_execucao = momento_inicio.strftime("%d/%m/%Y %H:%M:%S")
        logger.info(f"Início da execução do robô RH Cartão Ponto: {data_execucao}")

        periodo = self.senior_service.calcular_periodo_datas(
            data_referencia=momento_inicio.date(),
            modo=modo,
        )

        colaboradores = self.colaboradores_service.carregar_colaboradores()
        if matriculas_filtro:
            colaboradores = [colab for colab in colaboradores if colab.matricula in matriculas_filtro]

        if not colaboradores:
            return ExecucaoResponse(
                sucesso=False,
                modo=periodo.modo_aplicado,
                periodo=periodo,
                total_colaboradores=0,
                total_sucesso=0,
                total_erro=0,
                mensagem="Nenhum colaborador encontrado na planilha ou após aplicação do filtro.",
            )

        pasta_consolidado = Path(settings.REDE_PASTA_CONSOLIDADO)
        pasta_consolidado.mkdir(parents=True, exist_ok=True)
        marca_tempo = momento_inicio.strftime("%d%m%Y_%H%M")
        caminho_pdf_consolidado = pasta_consolidado / f"Cartao_Ponto_Consolidado_{marca_tempo}.pdf"

        mapa_pdfs_individuais = self._obter_mapa_pdfs(
            caminho_pdf_consolidado=caminho_pdf_consolidado,
            extrair_senior=extrair_senior,
            caminho_consolidado_existente=caminho_consolidado_existente,
            periodo=periodo,
        )

        registros_relatorio: List[RegistroExecucaoColaborador] = []
        total_sucesso = 0
        total_erro = 0

        for colaborador in colaboradores:
            registro = self._processar_colaborador(
                colaborador=colaborador,
                mapa_pdfs_individuais=mapa_pdfs_individuais,
                data_execucao=data_execucao,
                modo_aplicado=periodo.modo_aplicado,
                enviar_email=enviar_email,
            )
            if registro.status == StatusExecucao.SUCESSO:
                total_sucesso += 1
            else:
                total_erro += 1
            registros_relatorio.append(registro)

        caminho_relatorio = None
        try:
            caminho_relatorio = self.relatorio_service.gerar_relatorio_execucao(
                registros=registros_relatorio,
                pasta_destino=settings.REDE_PASTA_RELATORIOS,
                momento_execucao=momento_inicio,
            )
        except Exception as erro_relatorio:
            logger.error(f"Erro ao gerar planilha de relatório: {erro_relatorio}", exc_info=True)

        return ExecucaoResponse(
            sucesso=total_erro == 0,
            modo=periodo.modo_aplicado,
            periodo=periodo,
            total_colaboradores=len(colaboradores),
            total_sucesso=total_sucesso,
            total_erro=total_erro,
            caminho_consolidado=str(caminho_pdf_consolidado) if caminho_pdf_consolidado.exists() else None,
            caminho_relatorio=str(caminho_relatorio) if caminho_relatorio else None,
            mensagem=f"Execução finalizada: {total_sucesso} sucessos e {total_erro} erros.",
        )
