from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from core.config import settings
from schemas.execucao import ExecucaoRequest, ExecucaoResponse, ModoExecucao, PeriodoCartao
from schemas.colaborador import Colaborador
from services.orquestrador import OrquestradorCartaoPonto
from services.senior_service import SeniorService
from services.colaboradores_service import ColaboradoresService

router = APIRouter()
orquestrador = OrquestradorCartaoPonto()


@router.post("/executar", response_model=ExecucaoResponse, summary="Dispara o fluxo de envio de cartão ponto")
async def disparar_execucao(request: ExecucaoRequest):
    """
    Executa o fluxo completo conforme o PDD:
    - Extração no Senior Desktop via imagem
    - Divisão do PDF consolidado por matrícula
    - Envio dos e-mails
    - Geração da planilha de relatório de controle
    """
    try:
        resultado = orquestrador.executar(
            modo=request.modo,
            enviar_email=request.enviar_email,
            extrair_senior=request.extrair_senior,
            matriculas_filtro=request.matriculas_filtro,
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante a execução do processo: {str(e)}")


@router.get("/periodo", response_model=PeriodoCartao, summary="Calcula o período de apuração conforme a regra do PDD")
async def obter_periodo(modo: ModoExecucao = Query(ModoExecucao.AUTO, description="Modo 20, 30, 04 ou auto")):
    """
    Calcula as datas inicial e final para apuração do ponto:
    - Dia 20: 20 do mês anterior a 19 do mês atual
    - Dia 30: 20 do mês anterior a 19 do mês atual
    - Dia 04: 20 do penúltimo mês a 19 do mês anterior
    """
    try:
        return SeniorService.calcular_periodo_datas(modo=modo)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/colaboradores", response_model=List[Colaborador], summary="Lista colaboradores da planilha")
async def listar_colaboradores():
    """Lê e retorna a lista de colaboradores da planilha Excel configurada."""
    try:
        return ColaboradoresService.carregar_colaboradores()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar colaboradores: {str(e)}")


@router.get("/status-diretorios", summary="Verifica status das pastas de rede e arquivos")
async def verificar_diretorios():
    """Verifica a existência das pastas e arquivos necessários para a automação."""
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
            "templates_cadastrados": [
                f.name for f in Path(settings.SENIOR_TEMPLATES_DIR).glob("*.png")
            ] if Path(settings.SENIOR_TEMPLATES_DIR).exists() else [],
        },
    }

