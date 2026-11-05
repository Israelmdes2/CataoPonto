from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from schemas.colaborador import Colaborador


class ModoExecucao(str, Enum):
    DIA_20 = "20"
    DIA_30 = "30"
    DIA_04 = "04"
    AUTO = "auto"


class StatusExecucao(str, Enum):
    SUCESSO = "Sucesso"
    ERRO = "Erro"
    IGNORADO = "Ignorado"
    PENDENTE = "Pendente"


class PeriodoCartao(BaseModel):
    data_inicial: str  # formato DD/MM/AAAA
    data_final: str    # formato DD/MM/AAAA
    modo_aplicado: str


class RegistroExecucaoColaborador(BaseModel):
    data_execucao: str
    matricula: str
    colaborador: str
    email: str
    status: StatusExecucao
    motivo_erro: Optional[str] = ""


class ExecucaoRequest(BaseModel):
    modo: ModoExecucao = ModoExecucao.AUTO
    enviar_email: bool = True
    extrair_senior: bool = True
    matriculas_filtro: Optional[List[str]] = None


class ExecucaoResponse(BaseModel):
    sucesso: bool
    modo: str
    periodo: Optional[PeriodoCartao] = None
    total_colaboradores: int
    total_sucesso: int
    total_erro: int
    caminho_consolidado: Optional[str] = None
    caminho_relatorio: Optional[str] = None
    mensagem: str

