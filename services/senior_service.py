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

    def focar_janela_senior(self) -> bool:
        """Garante que a janela do Senior esteja em primeiro plano absoluto."""
        return gui.focar_senior_geral()

    def _esta_visivel(self, nome_template: str, confidence: float = 0.70) -> bool:
        """Verifica se um elemento visual está presente na tela sem bloquear."""
        tpl = self._obter_template(nome_template)
        if not tpl:
            return False
        return gui.is_visible(str(tpl), confidence=confidence)

    def tratar_obstaculos_conhecidos(self) -> bool:
        """
        Motor de Auto-Recuperação (Self-Healing):
        Detecta e resolve obstáculos intermediários antes do próximo passo:
        1. Foca a janela do Senior;
        2. Clica no ícone de módulo (colaboradores) caso apareça;
        3. Retorna True se tratou alguma condição.
        """
        self.focar_janela_senior()

        # 1. Ícone de seleção de módulo (Homologação / hub)
        tpl_mod = self._obter_template("icone_modulo.png")
        if tpl_mod and gui.is_visible(str(tpl_mod), confidence=0.70):
            logger.info("Auto-recuperação: Ícone de módulo detectado na tela. Clicando para expandir...")
            pos = gui.locate_center_on_screen(str(tpl_mod), confidence=0.70)
            if pos:
                gui.click(pos[0], pos[1])
                time.sleep(2)
                return True

        return False

    def _clicar_icone_modulo_se_necessario(self, timeout: int = 6) -> bool:
        """Mantido para compatibilidade: trata a transição de módulo."""
        return self.tratar_obstaculos_conhecidos()

    def garantir_menu_principal_pronto(self, timeout: float = 30.0) -> bool:
        """
        Garante que o módulo está ativo e a barra de menus ('Cálculos') visível:
        1. Se Cálculos já está visível: retorna True imediatamente.
        2. Se o ícone das 3 pessoas (colaboradores) estiver na tela: clica nele para abrir o módulo.
        3. Aguarda a renderização dos menus principais.
        """
        logger.info(f"Garantindo que o módulo e menus do Senior estão prontos (timeout: {timeout}s)...")
        deadline = time.time() + timeout
        tpl_calc = self._obter_template("menu_calculos.png")
        tpl_mod = self._obter_template("icone_modulo.png")

        while time.time() < deadline:
            self.focar_janela_senior()

            # 1. Se Cálculos já está visível, sucesso imediato
            if tpl_calc and gui.is_visible(str(tpl_calc), confidence=0.70):
                logger.info("Menu principal ('Cálculos') confirmado e pronto!")
                return True

            # 2. Se o ícone das 3 pessoas estiver na tela, clica nele
            if tpl_mod and gui.is_visible(str(tpl_mod), confidence=0.68):
                pos = gui.locate_center_on_screen(str(tpl_mod), confidence=0.68)
                if pos:
                    logger.info(f"Ícone de módulo (3 colaboradores) detectado em {pos}. Clicando para abrir módulo...")
                    gui.click(pos[0], pos[1])
                    time.sleep(3)
                    continue

            self.tratar_obstaculos_conhecidos()
            time.sleep(1.0)

        logger.warning(f"Timeout de {timeout}s: Menu principal não foi detectado.")
        return False

    def _clicar_se_encontrar(self, nome_template: str, timeout: int = 10, descricao: str = "", tentar_recuperar: bool = True) -> bool:
        """Localiza o template na tela usando Visão Computacional com auto-recuperação e clica."""
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

            # Tentativa de Self-Healing se habilitado
            if tentar_recuperar:
                logger.info(f"Elemento '{desc}' não visto de imediato. Tentando auto-recuperação...")
                if self.tratar_obstaculos_conhecidos():
                    pos_retry = gui.wait_for(str(template_path), timeout=5, confidence=self.confidence)
                    if pos_retry:
                        gui.click(pos_retry[0], pos_retry[1])
                        logger.info(f"Elemento '{desc}' clicado após auto-recuperação!")
                        return True

            logger.warning(f"Elemento visual '{desc}' não encontrado na tela após {timeout}s.")
            return False
        except Exception as e:
            logger.error(f"Erro ao tentar localizar visualmente '{desc}': {e}")
            return False

    def abrir_sistema_senior(self, ambiente: str = "homologacao") -> bool:
        """Dispara o Senior diretamente sem abrir pastas do Explorer."""
        logger.info(f"Iniciando Senior ({ambiente}) diretamente pelo executável...")
        is_hml = "homolog" in ambiente.lower()
        srv_dir = "Senior_HML" if is_hml else "Senior"
        srv_host = "SRVVETORH-HML" if is_hml else "SRVVETORH"
        senior_dir = r"C:\Senior-hml" if is_hml else r"C:\Senior"
        exe_unc = f"\\\\{srv_host}\\\\{srv_dir}\\Iniciar.exe"
        args = f'-SystemModule:VETORH.RONDA -seniordir:"{senior_dir}\\"'

        try:
            subprocess.Popen(f'"{exe_unc}" {args}', shell=True)
            time.sleep(6)
            self.focar_janela_senior()
            return True
        except Exception as e:
            logger.error(f"Erro ao disparar Senior via UNC: {e}")

        exe_local = Path(senior_dir) / "Vetorh" / "RONDA.EXE"
        if exe_local.exists():
            try:
                subprocess.Popen([str(exe_local)], cwd=str(exe_local.parent))
                time.sleep(6)
                self.focar_janela_senior()
                return True
            except Exception as e:
                logger.error(f"Erro ao disparar Senior local: {e}")

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

        # Verifica se ainda está na tela de seleção do módulo (HML)
        self._clicar_icone_modulo_se_necessario(timeout=3)

        # Estratégia 1: Ancoragem pelo botão azul 'Autenticar'
        tpl_btn = self._obter_template("botao_autenticar.png")
        if tpl_btn:
            pos_btn = gui.wait_for(str(tpl_btn), timeout=12, confidence=self.confidence)
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
        
        # Garante que a tela de menus está pronta e desobstruída antes de navegar
        self.garantir_menu_principal_pronto(timeout=25)

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

    def selecionar_relatorio_702(self, timeout_janela: int = 15) -> bool:
        """
        PASSO 5:
        1. Aguardar a janela 'Seleção de Modelos para Execução';
        2. Descer a barra de rolagem até encontrar a opção 702 ('UnimedVA - Cartão Ponto Portal');
        3. Clicar especificamente no NOME da opção 702 para torná-la ativa;
        4. Clicar no botão 'Executar'.
        """
        logger.info("Iniciando Passo 5: Seleção de Modelos para Execução (Código 702)...")
        self.focar_janela_senior()

        # 1. Aguarda a janela abrir (identificada pelo botão Executar ou pelo Título)
        tpl_titulo = self._obter_template("titulo_selecao_modelos.png")
        tpl_exec = self._obter_template("botao_executar.png")
        tpl_nome = self._obter_template("nome_opcao_702.png")
        tpl_702 = self._obter_template("codigo_702.png")
        tpl_texto_alt = self._obter_template("texto_cartao_ponto_portal.png")

        pos_exec = None
        if tpl_exec:
            pos_exec = gui.wait_for(str(tpl_exec), timeout=timeout_janela, confidence=self.confidence)

        if not pos_exec and tpl_titulo:
            pos_tit = gui.wait_for(str(tpl_titulo), timeout=5, confidence=self.confidence)
            if pos_tit:
                if tpl_exec:
                    pos_exec = gui.wait_for(str(tpl_exec), timeout=5, confidence=self.confidence)
                if not pos_exec:
                    pos_exec = (pos_tit[0] + 510, pos_tit[1] + 35)

        if not pos_exec:
            logger.warning("Janela 'Seleção de Modelos para Execução' não encontrada após timeout.")
            return False

        logger.info(f"Janela de Modelos aberta! Botão Executar em: {pos_exec}")

        # Coordenadas calibradas da barra de rolagem e do nome
        x_barra = pos_exec[0] - 58
        y_barra_topo = pos_exec[1]
        y_barra_fundo = pos_exec[1] + 130
        y_seta_baixo = pos_exec[1] + 142
        # Centro da coluna 'Descrição' (onde fica o nome da opção):
        x_coluna_nome = pos_exec[0] - 350
        y_lista = pos_exec[1] + 50

        def _tentar_localizar_nome_702():
            # Prioridade 1: Buscar o template do nome recortado diretamente da tela
            for tpl in [tpl_nome, tpl_702, tpl_texto_alt]:
                if not tpl:
                    continue
                for conf in [0.80, 0.72, 0.65, 0.58]:
                    p = gui.locate_center_on_screen(str(tpl), confidence=conf)
                    if p:
                        return p
            return None

        # 2. Verifica se o nome da opção 702 já está visível de início
        pos_nome_702 = _tentar_localizar_nome_702()

        # 3. Se ainda não estiver visível, rola a barra de rolagem até o final
        if not pos_nome_702:
            logger.info("Opção 702 ainda não visível no topo. Rolando a barra de rolagem para o final...")
            try:
                gui.move_to(x_barra, y_barra_topo, duration=0.2)
                gui.drag_to(x_barra, y_barra_fundo, duration=0.6)
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Falha ao arrastar barra de rolagem: {e}")

            pos_nome_702 = _tentar_localizar_nome_702()

        # Estratégia 2: Clica no trilho inferior da barra de rolagem e na seta para baixo
        if not pos_nome_702:
            logger.info("Clicando no trilho inferior da barra de rolagem e na seta para baixo...")
            for _ in range(6):
                gui.click(x_barra, y_barra_fundo)
                time.sleep(0.2)
                gui.click(x_barra, y_seta_baixo)
                time.sleep(0.2)
                pos_nome_702 = _tentar_localizar_nome_702()
                if pos_nome_702:
                    break

        # Estratégia 3: Foca na lista e usa teclas PageDown / Down
        if not pos_nome_702:
            logger.info("Focando na lista para enviar teclas PageDown / Down...")
            gui.click(x_coluna_nome, y_lista)
            time.sleep(0.3)
            for _ in range(10):
                gui.press("pagedown")
                time.sleep(0.25)
                pos_nome_702 = _tentar_localizar_nome_702()
                if pos_nome_702:
                    break
                gui.press("down")
                time.sleep(0.15)
                pos_nome_702 = _tentar_localizar_nome_702()
                if pos_nome_702:
                    break

        # 4. Fallback de Seleção se a lista já estiver totalmente no final:
        # No final da lista, o nome 'UnimedVA - Cartão Ponto Portal' fica na última linha
        if not pos_nome_702:
            logger.warning("Nome 702 não detectado por visão exata. Clicando na última linha da coluna Nome...")
            y_ultima_linha = pos_exec[1] + 120
            pos_nome_702 = (x_coluna_nome, y_ultima_linha)

        # 5. Clica especificamente no NOME da opção 702 (com duplo clique de garantia para seleção ativa)
        logger.info(f"Clicando no NOME da opção 702 ('UnimedVA - Cartão Ponto Portal') em {pos_nome_702}...")
        gui.click(pos_nome_702[0], pos_nome_702[1])
        time.sleep(0.3)
        gui.click(pos_nome_702[0], pos_nome_702[1])
        time.sleep(0.8)

        # Salva print da opção selecionada para auditoria
        try:
            print_702 = self.prints_dir / "05_opcao_702_selecionada.png"
            gui.screenshot(save_to=str(print_702))
            logger.info(f"Print pós-seleção do nome do 702 salvo em: {print_702}")
        except Exception:
            pass

        # 6. Clica no botão Executar
        logger.info(f"Opção 702 selecionada com sucesso! Clicando no botão Executar em {pos_exec}...")
        gui.click(pos_exec[0], pos_exec[1])
        time.sleep(3)

        # Salva print pós-Executar para auditoria do Passo 6
        try:
            print_pos_exec = self.prints_dir / "06_tela_parametros_datas.png"
            gui.screenshot(save_to=str(print_pos_exec))
            logger.info(f"Print pós-Executar salvo em: {print_pos_exec}")
        except Exception:
            pass

        logger.info("Passo 5 executado com sucesso!")
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
