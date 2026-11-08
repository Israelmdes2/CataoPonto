import logging
import os
import subprocess
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple

from core.config import settings
from infrastructure.automation import vision, gui
from schemas.execucao import PeriodoCartao, ModoExecucao

logger = logging.getLogger(__name__)


def _subtrair_meses(ano: int, mes: int, meses_a_subtrair: int) -> Tuple[int, int]:
    """Subtrai meses de forma puramente nativa sem dependência externa."""
    total_meses = (ano * 12 + mes - 1) - meses_a_subtrair
    novo_ano = total_meses // 12
    novo_mes = (total_meses % 12) + 1
    return novo_ano, novo_mes


class SeniorService:
    def __init__(self, ambiente: str = "homologacao"):
        self.ambiente = "homologacao" if "homolog" in ambiente.lower() else "producao"
        self.templates_dir = Path(settings.SENIOR_TEMPLATES_DIR)
        self.confidence = settings.SENIOR_CONFIDENCE
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def calcular_periodo_datas(
        data_referencia: Optional[date] = None,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
    ) -> PeriodoCartao:
        """
        Calcula as datas inicial e final rigorosamente de acordo com o PDD:
        - Dia 20: Inicial = dia 20 mês anterior | Final = dia 19 mês atual
        - Dia 30: Inicial = dia 20 mês anterior | Final = dia 19 mês atual
        - Dia 04: Inicial = dia 20 do penúltimo mês | Final = dia 19 mês anterior
        """
        ref = data_referencia or date.today()
        modo_str = modo.value if isinstance(modo, ModoExecucao) else str(modo)

        if modo_str == "auto":
            dia = ref.day
            if dia <= 10:
                modo_str = "04"
            elif dia <= 25:
                modo_str = "20"
            else:
                modo_str = "30"

        if modo_str in ("20", "30"):
            ano_ini, mes_ini = _subtrair_meses(ref.year, ref.month, 1)
            dt_ini = date(ano_ini, mes_ini, 20)
            dt_fim = date(ref.year, ref.month, 19)
        elif modo_str == "04":
            ano_ini, mes_ini = _subtrair_meses(ref.year, ref.month, 2)
            dt_ini = date(ano_ini, mes_ini, 20)
            ano_fim, mes_fim = _subtrair_meses(ref.year, ref.month, 1)
            dt_fim = date(ano_fim, mes_fim, 19)
        else:
            raise ValueError(f"Modo de execução inválido: {modo_str}. Use '20', '30', '04' ou 'auto'.")

        return PeriodoCartao(
            data_inicial=dt_ini.strftime("%d/%m/%Y"),
            data_final=dt_fim.strftime("%d/%m/%Y"),
            modo_aplicado=modo_str,
        )

    def _obter_template(self, nome_arquivo: str) -> Optional[Path]:
        """
        Verifica se o template visual PNG existe:
        1. Prioridade: pasta específica do ambiente (assets/templates/{ambiente}/)
        2. Fallback: pasta raiz de templates (assets/templates/)
        """
        caminho_amb = self.templates_dir / self.ambiente / nome_arquivo
        if caminho_amb.exists():
            return caminho_amb
        caminho_raiz = self.templates_dir / nome_arquivo
        if caminho_raiz.exists():
            return caminho_raiz
        return None

    def _clicar_se_encontrar(self, nome_template: str, timeout: int = 10, descricao: str = "") -> bool:
        """Localiza o template na tela usando Visão Computacional / PyAutoGUI e clica."""
        template_path = self._obter_template(nome_template)
        desc = descricao or nome_template

        if not template_path:
            logger.warning(
                f"[TEMPLATE VISUAL AUSENTE] O template '{nome_template}' não foi encontrado em '{self.templates_dir}'. "
                f"Capture o print do elemento '{desc}' e salve como '{nome_template}'."
            )
            return False

        logger.info(f"Procurando elemento visual na tela: {desc} ({nome_template})...")
        try:
            pos = gui.wait_for(str(template_path), timeout=timeout, confidence=self.confidence)
            if pos:
                x, y = pos
                gui.click(x, y)
                logger.info(f"Elemento '{desc}' clicado na posição ({x}, {y}).")
                return True
            else:
                logger.warning(f"Elemento visual '{desc}' não encontrado na tela após {timeout}s.")
                return False
        except Exception as e:
            logger.error(f"Erro ao tentar localizar visualmente '{desc}': {e}")
            return False

    def abrir_sistema_senior(self, ambiente: str = "homologacao") -> bool:
        """
        PASSO 2:
        1. Acessar a área de trabalho e abrir a pasta 'Senior';
        2. Abrir a opção 'Controle de Ponto e Refeitório'.
        """
        logger.info(f"Iniciando abertura do sistema Senior ({ambiente})...")

        # Prioridade 1: Executável configurado no .env por ambiente (HML ou PROD)
        caminho_env = (
            settings.SENIOR_EXECUTAVEL_HML
            if "homolog" in ambiente.lower()
            else settings.SENIOR_EXECUTAVEL_PROD
        ) or settings.SENIOR_EXECUTAVEL

        if caminho_env and Path(caminho_env).exists():
            caminho = str(caminho_env)
            logger.info(f"Executando Senior via caminho configurado ({ambiente}): {caminho}")
            try:
                if caminho.lower().endswith('.lnk'):
                    os.startfile(caminho)
                else:
                    subprocess.Popen([caminho])
                time.sleep(8)
                return True
            except Exception as e:
                logger.error(f"Erro ao abrir Senior via caminho direto: {e}")

        # Tenta clicar no atalho da Área de Trabalho por imagem
        sucesso_pasta = self._clicar_se_encontrar("pasta_senior.png", timeout=5, descricao="Pasta Senior na Área de Trabalho")
        if sucesso_pasta:
            time.sleep(2)
            self._clicar_se_encontrar("modulo_ponto.png", timeout=5, descricao="Controle de Ponto e Refeitório")
            time.sleep(5)
            return True

        logger.warning(
            "Não foi possível abrir o Senior automaticamente por template visual. "
            "Certifique-se de que a aplicação está aberta na tela ou configure SENIOR_EXECUTAVEL no .env."
        )
        return False

    def autenticar_senior(self, usuario: Optional[str] = None, senha: Optional[str] = None) -> bool:
        """
        PASSO 3:
        1. Inserir Login;
        2. Inserir Senha;
        3. Clicar no botão 'Autenticar'.
        """
        user = (usuario or settings.SENIOR_LOGIN or "").strip().lower()
        password = senha or settings.SENIOR_PASSWORD
        logger.info(f"Realizando autenticação do usuário '{user}' no Senior...")

        # Estratégia 1: Ancoragem pelo botão azul 'Autenticar'
        tpl_btn = self._obter_template("botao_autenticar.png")
        if tpl_btn:
            pos_btn = gui.wait_for(str(tpl_btn), timeout=8, confidence=self.confidence)
            if pos_btn:
                logger.info(f"Botão 'Autenticar' localizado em: {pos_btn}. Navegando para campos por ancoragem.")
                # O campo de usuário fica ~93px acima do centro do botão Autenticar (calibrado em 1080p)
                x_user = pos_btn[0]
                y_user = pos_btn[1] - 93
                gui.click(x_user, y_user)
                time.sleep(0.5)
                gui.hotkey("ctrl", "a")
                gui.press("backspace")
                gui.type_text(user)
                gui.press("tab")
                time.sleep(0.5)
                gui.type_text(password)
                time.sleep(0.5)
                gui.click(pos_btn[0], pos_btn[1])
                time.sleep(5)
                return True

        # Estratégia 2: Busca direta pelo campo de login
        clicou_login = self._clicar_se_encontrar("campo_login.png", timeout=5, descricao="Campo de Login")
        if clicou_login:
            gui.hotkey("ctrl", "a")
            gui.press("backspace")
            gui.type_text(user)
            gui.press("tab")
            time.sleep(0.5)
            gui.type_text(password)
            time.sleep(0.5)
            self._clicar_se_encontrar("botao_autenticar.png", timeout=5, descricao="Botão Autenticar")
            time.sleep(5)
            return True

        return False

    def navegar_para_cartao_ponto(self) -> bool:
        """
        PASSO 4:
        1. Clicar na aba 'Cálculos';
        2. Selecionar a opção 'Apuração';
        3. Selecionar a opção 'Listar';
        4. Clicar na opção 'Cartão Ponto'.
        """
        logger.info("Navegando pelos menus: Cálculos -> Apuração -> Listar -> Cartão Ponto...")
        steps = [
            ("menu_calculos.png", "Aba Cálculos"),
            ("menu_apuracao.png", "Opção Apuração"),
            ("menu_listar.png", "Opção Listar"),
            ("menu_cartao_ponto.png", "Opção Cartão Ponto"),
        ]

        for template, desc in steps:
            time.sleep(1)
            self._clicar_se_encontrar(template, timeout=5, descricao=desc)

        return True

    def selecionar_relatorio_702(self) -> bool:
        """
        PASSO 5:
        1. Selecionar a opção equivalente ao código '702';
        2. Clicar no botão 'Executar'.
        """
        logger.info("Selecionando relatório código 702 e clicando em Executar...")
        self._clicar_se_encontrar("codigo_702.png", timeout=5, descricao="Relatório Código 702")
        time.sleep(1)
        self._clicar_se_encontrar("botao_executar.png", timeout=5, descricao="Botão Executar")
        time.sleep(3)
        return True

    def preencher_datas_e_gerar(self, data_inicial: str, data_final: str) -> bool:
        """
        PASSO 6:
        1. Preencher 'Data Inicial';
        2. Preencher 'Data Final';
        3. Clicar no botão 'OK' (aguardar processamento de 7 a 10 min).
        """
        logger.info(f"Preenchendo período de apuração: {data_inicial} até {data_final}...")

        clicou_ini = self._clicar_se_encontrar("campo_data_inicial.png", timeout=5, descricao="Campo Data Inicial")
        if clicou_ini:
            gui.hotkey("ctrl", "a")
            gui.press("backspace")
            gui.type_text(data_inicial.replace("/", ""))
            gui.press("tab")
            time.sleep(0.5)
            gui.type_text(data_final.replace("/", ""))
            time.sleep(0.5)

        self._clicar_se_encontrar("botao_ok.png", timeout=5, descricao="Botão OK da tela de parâmetros")
        return True

    def aguardar_relatorio_e_salvar(self, caminho_destino_pdf: Path) -> Path:
        """
        PASSO 7:
        Aguarda o relatório ser gerado pelo Senior (pode levar 7 a 10 min)
        e salva na pasta de rede informada.
        """
        timeout_max = settings.SENIOR_TIMEOUT_RELATORIO_SEGUNDOS
        logger.info(f"Aguardando a conclusão da geração do relatório (timeout máximo: {timeout_max}s)...")

        inicio = time.time()
        encontrou_visualizador = False

        while time.time() - inicio < timeout_max:
            # Procura por template da janela de visualização do relatório
            pos = None
            tpl = self._obter_template("relatorio_visualizador.png")
            if tpl:
                pos = gui.locate_on_screen(str(tpl), confidence=self.confidence)

            if pos:
                encontrou_visualizador = True
                logger.info("Janela do relatório finalizado detectada com sucesso na tela!")
                break

            time.sleep(10)
            logger.debug(f"Aguardando geração do relatório no Senior... ({int(time.time() - inicio)}s decorridos)")

        caminho_destino_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Salvar o documento via menu/botão Salvar ou Ctrl+S
        logger.info(f"Salvando o documento na pasta compartilhada: {caminho_destino_pdf}...")
        self._clicar_se_encontrar("botao_salvar_relatorio.png", timeout=5, descricao="Botão Salvar do Visualizador")
        time.sleep(2)

        # Digita o caminho completo do arquivo na caixa de diálogo de salvar do Windows
        gui.type_text(str(caminho_destino_pdf))
        time.sleep(1)
        gui.press("enter")
        time.sleep(3)

        return caminho_destino_pdf

    def executar_fluxo_extracao(
        self,
        caminho_saida_pdf: Path,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
    ) -> Tuple[PeriodoCartao, Path]:
        """Executa a sequência completa de passos do Senior Desktop."""
        periodo = self.calcular_periodo_datas(modo=modo)
        logger.info(
            f"Iniciando extração no Senior para o modo [{periodo.modo_aplicado}]. Período: {periodo.data_inicial} a {periodo.data_final}"
        )

        self.abrir_sistema_senior()
        self.autenticar_senior()
        self.navegar_para_cartao_ponto()
        self.selecionar_relatorio_702()
        self.preencher_datas_e_gerar(periodo.data_inicial, periodo.data_final)
        caminho_final = self.aguardar_relatorio_e_salvar(caminho_saida_pdf)

        return periodo, caminho_final
