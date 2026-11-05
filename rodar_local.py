"""
Script de execução local e depuração do Robô RH - Envio de Cartão Ponto.
Padrão Digitaly Technology para testes rápidos e execuções manuais.
"""
import argparse
import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger
from services.orquestrador import OrquestradorCartaoPonto
from services.colaboradores_service import ColaboradoresService
from services.senior_service import SeniorService

logger = get_logger("rodar_local")


def main():
    parser = argparse.ArgumentParser(
        description="Executa o robô RH - Envio de Cartão Ponto (Unimed Vale do Aço)"
    )
    parser.add_argument(
        "--modo",
        choices=["20", "30", "04", "auto"],
        default="auto",
        help="Modo de execução (dia 20, 30, 04 ou auto baseado na data atual)",
    )
    parser.add_argument(
        "--sem-email",
        action="store_true",
        help="Executa o processo sem disparar e-mails reais",
    )
    parser.add_argument(
        "--sem-senior",
        action="store_true",
        help="Pula a extração no Senior Desktop e usa arquivos locais já baixados",
    )
    parser.add_argument(
        "--consolidado",
        type=str,
        default=None,
        help="Caminho de um arquivo PDF consolidado existente para testes",
    )
    parser.add_argument(
        "--matricula",
        type=str,
        nargs="+",
        default=None,
        help="Filtra uma ou mais matrículas para processamento pontual",
    )
    parser.add_argument(
        "--listar-colaboradores",
        action="store_true",
        help="Apenas lista os colaboradores encontrados na planilha e encerra",
    )
    parser.add_argument(
        "--ver-periodo",
        action="store_true",
        help="Apenas calcula e exibe as datas inicial e final para o modo selecionado",
    )

    args = parser.parse_args()

    # Opção: Apenas ver período calculado
    if args.ver_periodo:
        periodo = SeniorService.calcular_periodo_datas(modo=args.modo)
        print(f"\n[PERÍODO CALCULADO - PDD]")
        print(f"Modo Aplicado: Dia {periodo.modo_aplicado}")
        print(f"Data Inicial : {periodo.data_inicial}")
        print(f"Data Final   : {periodo.data_final}\n")
        return

    # Opção: Apenas listar colaboradores da planilha
    if args.listar_colaboradores:
        print("\nCarregando colaboradores da planilha...")
        colabs = ColaboradoresService.carregar_colaboradores()
        print(f"Total: {len(colabs)} colaborador(es) encontrado(s):")
        for c in colabs:
            print(f" - Matrícula: {c.matricula:<8} | Nome: {c.nome:<30} | Setor: {c.setor:<20} | Email: {c.email}")
        print()
        return

    # Execução do Orquestrador
    print(f"\nIniciando execução no modo: [{args.modo}]...")
    orquestrador = OrquestradorCartaoPonto()
    resultado = orquestrador.executar(
        modo=args.modo,
        enviar_email=(not args.sem_email),
        extrair_senior=(not args.sem_senior),
        caminho_consolidado_existente=args.consolidado,
        matriculas_filtro=args.matricula,
    )

    print("\n" + "=" * 60)
    print("RESULTADO DA EXECUÇÃO:")
    print("=" * 60)
    print(f"Sucesso Geral: {'SIM' if resultado.sucesso else 'NÃO'}")
    print(f"Modo: Dia {resultado.modo}")
    if resultado.periodo:
        print(f"Período: {resultado.periodo.data_inicial} até {resultado.periodo.data_final}")
    print(f"Total Colaboradores: {resultado.total_colaboradores}")
    print(f"Total Sucessos     : {resultado.total_sucesso}")
    print(f"Total Falhas       : {resultado.total_erro}")
    if resultado.caminho_consolidado:
        print(f"PDF Consolidado    : {resultado.caminho_consolidado}")
    if resultado.caminho_relatorio:
        print(f"Relatório Excel    : {resultado.caminho_relatorio}")
    print(f"Mensagem           : {resultado.mensagem}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

