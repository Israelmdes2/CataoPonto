"""Script de execução local via terminal para o Robô RH - Envio de Cartão Ponto."""

import argparse
import sys
from pathlib import Path

DIRETORIO_RAIZ = Path(__file__).resolve().parent
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

from services.colaboradores_service import ColaboradoresService
from services.orquestrador import OrquestradorCartaoPonto
from services.senior_service import SeniorService


def main() -> None:
    """Interpreta os argumentos de linha de comando e executa o fluxo selecionado."""
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
        help="Lista os colaboradores encontrados na planilha e encerra",
    )
    parser.add_argument(
        "--ver-periodo",
        action="store_true",
        help="Calcula e exibe as datas inicial e final para o modo selecionado",
    )
    argumentos = parser.parse_args()

    if argumentos.ver_periodo:
        periodo = SeniorService.calcular_periodo_datas(modo=argumentos.modo)
        print(f"\nModo: Dia {periodo.modo_aplicado} | {periodo.data_inicial} até {periodo.data_final}\n")
        return

    if argumentos.listar_colaboradores:
        colaboradores = ColaboradoresService.carregar_colaboradores()
        print(f"\nTotal: {len(colaboradores)} colaborador(es):")
        for colaborador in colaboradores:
            print(
                f" - {colaborador.matricula:<8} | {colaborador.nome:<30} | {colaborador.email}"
            )
        print()
        return

    orquestrador = OrquestradorCartaoPonto()
    resultado = orquestrador.executar(
        modo=argumentos.modo,
        enviar_email=not argumentos.sem_email,
        extrair_senior=not argumentos.sem_senior,
        caminho_consolidado_existente=argumentos.consolidado,
        matriculas_filtro=argumentos.matricula,
    )

    print("\n" + "=" * 60)
    print(f"Sucesso: {'SIM' if resultado.sucesso else 'NÃO'} | Modo: Dia {resultado.modo}")
    if resultado.periodo:
        print(f"Período: {resultado.periodo.data_inicial} até {resultado.periodo.data_final}")
    print(
        f"Colaboradores: {resultado.total_colaboradores} | "
        f"Sucessos: {resultado.total_sucesso} | Falhas: {resultado.total_erro}"
    )
    if resultado.caminho_consolidado:
        print(f"PDF Consolidado: {resultado.caminho_consolidado}")
    if resultado.caminho_relatorio:
        print(f"Relatório Excel: {resultado.caminho_relatorio}")
    print(f"Mensagem: {resultado.mensagem}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
