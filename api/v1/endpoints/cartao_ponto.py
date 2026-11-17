from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Query

from core.config import settings
from schemas.colaborador import Colaborador
from schemas.execucao import ExecucaoRequest, ExecucaoResponse, ModoExecucao, PeriodoCartao
from services.colaboradores_service import ColaboradoresService
from services.orquestrador import OrquestradorCartaoPonto
from services.senior_service import SeniorService

router = APIRouter()
orquestrador = OrquestradorCartaoPonto()


@router.post("/executar", response_model=ExecucaoResponse, summary="Dispara o fluxo de envio de cartão ponto")
async def disparar_execucao(requisicao: ExecucaoRequest):
    """Executa o fluxo completo de extração, divisão, disparo de e-mails e relatório."""
    try:
        return orquestrador.executar(
            modo=requisicao.modo,
            enviar_email=requisicao.enviar_email,
            extrair_senior=requisicao.extrair_senior,
            matriculas_filtro=requisicao.matriculas_filtro,
        )
    except Exception as erro:
        raise HTTPException(status_code=500, detail=f"Erro durante a execução do processo: {erro}") from erro


@router.get("/periodo", response_model=PeriodoCartao, summary="Calcula o período de apuração")
async def obter_periodo(modo: ModoExecucao = Query(ModoExecucao.AUTO, description="Modo 20, 30, 04 ou auto")):
    """Calcula as datas inicial e final de apuração conforme o modo informado."""
    try:
        return SeniorService.calcular_periodo_datas(modo=modo)
    except Exception as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro


@router.get("/colaboradores", response_model=List[Colaborador], summary="Lista colaboradores da planilha")
async def listar_colaboradores():
    """Lê e retorna os colaboradores cadastrados na planilha configurada."""
    try:
        return ColaboradoresService.carregar_colaboradores()
    except Exception as erro:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar colaboradores: {erro}") from erro


@router.get("/status-diretorios", summary="Verifica status das pastas de rede e arquivos")
async def verificar_diretorios():
    """Verifica a disponibilidade das pastas e arquivos necessários para o robô."""
    return {
        "pasta_consolidado": {
            "caminho": settings.REDE_PASTA_CONSOLIDADO,
            "existe": Path(settings.REDE_PASTA_CONSOLIDADO).exists(),
        },
        "pasta_individuais": {
            "caminho": settings.REDE_PASTA_INDIVIDUAIS,
            "existe": Path(settings.REDE_PASTA_INDIVIDUAIS).exists(),
        },
        "pasta_relatorios": {
            "caminho": settings.REDE_PASTA_RELATORIOS,
            "existe": Path(settings.REDE_PASTA_RELATORIOS).exists(),
        },
        "planilha_colaboradores": {
            "caminho": settings.PLANILHA_COLABORADORES_PATH,
            "existe": Path(settings.PLANILHA_COLABORADORES_PATH).exists(),
        },
        "templates_dir": {
            "caminho": settings.SENIOR_TEMPLATES_DIR,
            "existe": Path(settings.SENIOR_TEMPLATES_DIR).exists(),
        },
    }
