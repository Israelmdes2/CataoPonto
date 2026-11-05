import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.config import settings
from schemas.colaborador import Colaborador
from schemas.execucao import (
    ModoExecucao,
    StatusExecucao,
    RegistroExecucaoColaborador,
    ExecucaoRequest,
    ExecucaoResponse,
    PeriodoCartao,
)
from services.colaboradores_service import ColaboradoresService
from services.senior_service import SeniorService
from services.pdf_splitter_service import PdfSplitterService
from services.email_service import EmailService
from services.relatorio_service import RelatorioService

logger = logging.getLogger(__name__)


class OrquestradorCartaoPonto:
    def __init__(self):
        self.senior_service = SeniorService()
        self.colaboradores_service = ColaboradoresService()
        self.splitter_service = PdfSplitterService()
        self.email_service = EmailService()
        self.relatorio_service = RelatorioService()

    def executar(
        self,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
        enviar_email: bool = True,
        extrair_senior: bool = True,
        caminho_consolidado_existente: Optional[str] = None,
        matriculas_filtro: Optional[List[str]] = None,
    ) -> ExecucaoResponse:
        """
        Executa o fluxo completo de Envio de Cartão Ponto (P.A) - Unimed Vale do Aço:
        1. Carrega dados de colaboradores da planilha
        2. Determina período e modo (04, 20 ou 30)
        3. Extrai o PDF consolidado do sistema Senior Desktop (OpenCV + PyAutoGUI)
        4. Separa o PDF consolidado em cartões individuais por matrícula
        5. Dispara e-mails individuais com os cartões anexados
        6. Gera a planilha Excel de controle da execução
        """
        momento_inicio = datetime.now()
        data_exec_str = momento_inicio.strftime("%d/%m/%Y %H:%M:%S")
        logger.info(f"=== INÍCIO DA EXECUÇÃO DO ROBÔ RH CARTÃO PONTO: {data_exec_str} ===")

        # 1. Determinação de Modo e Período
        periodo = self.senior_service.calcular_periodo_datas(
            data_referencia=momento_inicio.date(),
            modo=modo,
        )
        logger.info(
            f"Modo de execução selecionado: [{periodo.modo_aplicado}]. "
            f"Período de Apuração: {periodo.data_inicial} até {periodo.data_final}"
        )

        # 2. Carregar Colaboradores da Planilha
        colaboradores = self.colaboradores_service.carregar_colaboradores()
        if matriculas_filtro:
            colaboradores = [c for c in colaboradores if c.matricula in matriculas_filtro]
            logger.info(f"Filtro aplicado: {len(colaboradores)} colaboradores selecionados.")

        if not colaboradores:
            logger.warning("Nenhum colaborador encontrado para processamento.")
            return ExecucaoResponse(
                sucesso=False,
                modo=periodo.modo_aplicado,
                periodo=periodo,
                total_colaboradores=0,
                total_sucesso=0,
                total_erro=0,
                mensagem="Nenhum colaborador encontrado na planilha ou após aplicação do filtro.",
            )

        # 3. Extração no Senior Desktop
        pasta_consolidado = Path(settings.REDE_PASTA_CONSOLIDADO)
        pasta_consolidado.mkdir(parents=True, exist_ok=True)
        timestamp_arquivo = momento_inicio.strftime("%d%m%Y_%H%M")
        caminho_pdf_consolidado = pasta_consolidado / f"Cartao_Ponto_Consolidado_{timestamp_arquivo}.pdf"

        if caminho_consolidado_existente and Path(caminho_consolidado_existente).exists():
            logger.info(f"Utilizando arquivo consolidado pré-existente: {caminho_consolidado_existente}")
            caminho_pdf_consolidado = Path(caminho_consolidado_existente)
        elif extrair_senior:
            try:
                _, caminho_pdf_consolidado = self.senior_service.executar_fluxo_extracao(
                    caminho_saida_pdf=caminho_pdf_consolidado,
                    modo=periodo.modo_aplicado,
                )
            except Exception as e:
                logger.error(f"Erro durante a extração no sistema Senior: {e}", exc_info=True)
        else:
            logger.info("Extração no Senior ignorada conforme parâmetro extrair_senior=False.")

        # 4. Divisão do PDF Consolidado em Cartões Individuais
        mapa_pdfs_individuais = {}
        if caminho_pdf_consolidado.exists():
            try:
                mapa_pdfs_individuais = self.splitter_service.dividir_cartoes_ponto(
                    caminho_consolidado=caminho_pdf_consolidado,
                    pasta_destino=settings.REDE_PASTA_INDIVIDUAIS,
                )
            except Exception as e:
                logger.error(f"Erro na separação do PDF consolidado: {e}", exc_info=True)
        else:
            logger.warning(
                f"Arquivo PDF consolidado não encontrado em: {caminho_pdf_consolidado}. "
                "Verificando se já existem cartões individuais na pasta de destino."
            )
            # Busca se já existem cartões na pasta individual
            pasta_indiv = Path(settings.REDE_PASTA_INDIVIDUAIS)
            if pasta_indiv.exists():
                for p in pasta_indiv.glob("Cartao_Ponto_*.pdf"):
                    # Extrai matrícula do nome
                    mat = p.stem.replace("Cartao_Ponto_", "")
                    mapa_pdfs_individuais[mat] = p

        # 5. Processamento Individual e Envio de E-mails
        registros_relatorio: List[RegistroExecucaoColaborador] = []
        total_sucesso = 0
        total_erro = 0

        for colab in colaboradores:
            reg = RegistroExecucaoColaborador(
                data_execucao=data_exec_str,
                matricula=colab.matricula,
                colaborador=colab.nome,
                email=colab.email,
                status=StatusExecucao.PENDENTE,
                motivo_erro="",
            )

            # Localiza o PDF do colaborador (tenta matrícula exata e sem zeros à esquerda)
            mat_limpa = str(int(colab.matricula)) if colab.matricula.isdigit() else colab.matricula
            pdf_path = mapa_pdfs_individuais.get(colab.matricula) or mapa_pdfs_individuais.get(mat_limpa)

            if not pdf_path or not Path(pdf_path).exists():
                reg.status = StatusExecucao.ERRO
                reg.motivo_erro = f"Cartão de ponto PDF não localizado para a matrícula {colab.matricula}."
                total_erro += 1
                registros_relatorio.append(reg)
                continue

            if not enviar_email:
                reg.status = StatusExecucao.SUCESSO
                reg.motivo_erro = "Processado com sucesso (envio de e-mail desativado)."
                total_sucesso += 1
                registros_relatorio.append(reg)
                continue

            # Envia e-mail
            try:
                self.email_service.enviar_cartao_ponto(
                    destinatario_email=colab.email,
                    nome_colaborador=colab.nome,
                    caminho_pdf_anexo=pdf_path,
                    modo=periodo.modo_aplicado,
                )
                reg.status = StatusExecucao.SUCESSO
                total_sucesso += 1
            except Exception as ex_mail:
                reg.status = StatusExecucao.ERRO
                reg.motivo_erro = f"Falha no envio de e-mail: {str(ex_mail)}"
                total_erro += 1

            registros_relatorio.append(reg)

        # 6. Geração do Relatório de Controle da Execução (Excel)
        caminho_relatorio = None
        try:
            caminho_relatorio = self.relatorio_service.gerar_relatorio_execucao(
                registros=registros_relatorio,
                pasta_destino=settings.REDE_PASTA_RELATORIOS,
                momento_execucao=momento_inicio,
            )
        except Exception as ex_rel:
            logger.error(f"Erro ao gerar planilha de relatório de execução: {ex_rel}", exc_info=True)

        logger.info(
            f"=== EXECUÇÃO FINALIZADA: {total_sucesso} sucessos, {total_erro} erros de {len(colaboradores)} total. ==="
        )

        return ExecucaoResponse(
            sucesso=(total_erro == 0),
            modo=periodo.modo_aplicado,
            periodo=periodo,
            total_colaboradores=len(colaboradores),
            total_sucesso=total_sucesso,
            total_erro=total_erro,
            caminho_consolidado=str(caminho_pdf_consolidado) if caminho_pdf_consolidado.exists() else None,
            caminho_relatorio=str(caminho_relatorio) if caminho_relatorio else None,
            mensagem=(
                f"Execução concluída com sucesso no modo dia {periodo.modo_aplicado}."
                if total_erro == 0
                else f"Execução finalizada com {total_erro} falha(s). Verifique o relatório de controle."
            ),
        )

