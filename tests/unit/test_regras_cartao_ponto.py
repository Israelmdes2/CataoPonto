from datetime import date
from services.senior_service import SeniorService
from services.email_service import EmailService
from schemas.execucao import ModoExecucao


def test_calculo_periodo_dia_20():
    # Executado em 20/11/2026: deve cobrir 20/10/2026 a 19/11/2026
    dt_ref = date(2026, 11, 20)
    periodo = SeniorService.calcular_periodo_datas(data_referencia=dt_ref, modo=ModoExecucao.DIA_20)
    assert periodo.data_inicial == "20/10/2026"
    assert periodo.data_final == "19/11/2026"
    assert periodo.modo_aplicado == "20"


def test_calculo_periodo_dia_30():
    # Executado em 30/11/2026: deve cobrir 20/10/2026 a 19/11/2026
    dt_ref = date(2026, 11, 30)
    periodo = SeniorService.calcular_periodo_datas(data_referencia=dt_ref, modo=ModoExecucao.DIA_30)
    assert periodo.data_inicial == "20/10/2026"
    assert periodo.data_final == "19/11/2026"
    assert periodo.modo_aplicado == "30"


def test_calculo_periodo_dia_04():
    # Executado em 04/11/2026: deve cobrir 20/09/2026 (penúltimo mês) a 19/10/2026 (mês anterior)
    dt_ref = date(2026, 11, 4)
    periodo = SeniorService.calcular_periodo_datas(data_referencia=dt_ref, modo=ModoExecucao.DIA_04)
    assert periodo.data_inicial == "20/09/2026"
    assert periodo.data_final == "19/10/2026"
    assert periodo.modo_aplicado == "04"


def test_conteudo_email_conferencia():
    assunto, corpo = EmailService.obter_conteudo_email("Carlos Silva", modo="20")
    assert assunto == "Espelho de Ponto – Conferência das Marcações"
    assert "Prezado(a) Carlos Silva" in corpo
    assert "conferência das marcações" in corpo


def test_conteudo_email_fechamento():
    assunto, corpo = EmailService.obter_conteudo_email("Carlos Silva", modo="30")
    assert assunto == "Espelho de Ponto – Fechamento do Período"
    assert "Prezado(a) Carlos Silva" in corpo
    assert "Segue o espelho de ponto finalizado" in corpo

