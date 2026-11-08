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
                import pyperclip
                pyperclip.copy(user.lower())
                gui.hotkey("ctrl", "v")
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
            self._clicar_se_encontrar(template, timeout=4, descricao=desc)
            time.sleep(0.3)

        return True

    def selecionar_relatorio_702(self, timeout_janela: int = 15) -> bool:
        """
        PASSO 5:
        1. Aguardar a janela 'Seleção de Modelos para Execução';
        2. Rolar a grade até encontrar estritamente o modelo 702 ('UnimedVA - Cartão Ponto Portal');
        3. Clicar no NOME da opção 702 com alta precisão visual (sem falsos positivos);
        4. Clicar no botão 'Executar'.
        """
        logger.info("Iniciando Passo 5: Seleção de Modelos para Execução (Código 702)...")

        # 1. Aguarda a janela abrir (identificada pelo botão Executar ou pelo Título)
        tpl_titulo = self._obter_template("titulo_selecao_modelos.png")
        tpl_exec = self._obter_template("botao_executar.png")
        tpl_702_oficial = self._obter_template("opcao_702_oficial.png")
        tpl_nome_oficial = self._obter_template("nome_702_oficial.png")

        pos_exec = None
        if tpl_exec:
            pos_exec = gui.wait_for(str(tpl_exec), timeout=timeout_janela, confidence=self.confidence)

        if not pos_exec and tpl_titulo:
            pos_tit = gui.wait_for(str(tpl_titulo), timeout=4, confidence=self.confidence)
            if pos_tit:
                if tpl_exec:
                    pos_exec = gui.wait_for(str(tpl_exec), timeout=3, confidence=self.confidence)
                if not pos_exec:
                    pos_exec = (pos_tit[0] + 510, pos_tit[1] + 35)

        if not pos_exec:
            logger.warning("Janela 'Seleção de Modelos para Execução' não encontrada após timeout.")
            return False

        logger.info(f"Janela de Modelos aberta! Botão Executar em: {pos_exec}")

        # Coordenadas calibradas na grade e na barra de rolagem
        x_grade = pos_exec[0] - 300
        y_grade = pos_exec[1] + 60
        x_trilho_barra = pos_exec[0] - 55
        y_trilho_barra = pos_exec[1] + 110
        y_seta_barra = pos_exec[1] + 165

        def _buscar_702_estrito():
            """Busca estritamente o template oficial com alta confiança (sem sensibilidade / sem falsos positivos)."""
            for tpl in [tpl_702_oficial, tpl_nome_oficial]:
                if not tpl:
                    continue
                for conf in [0.88, 0.82]:
                    p = gui.locate_center_on_screen(str(tpl), confidence=conf)
                    if p:
                        return p, tpl
            return None, None

        # 2. Clica no centro da grade para focar o controle
        gui.click(x_grade, y_grade)
        time.sleep(0.3)

        # 3. Loop de rolagem multi-método (scroll do mouse + PageDown + clique no trilho da barra)
        pos_702 = None
        qual_tpl = None

        logger.info("Verificando se opção 702 já está visível ou descendo a grade...")
        pos_702, qual_tpl = _buscar_702_estrito()

        if not pos_702:
            for ciclo in range(25):
                # Método 1: Roda o scroll do mouse para baixo sobre a grade
                try:
                    gui.scroll(-4)
                except Exception:
                    pass

                # Método 2: Tecla PageDown e Seta para Baixo
                try:
                    gui.press("pagedown")
                    gui.press("down")
                except Exception:
                    pass

                # Método 3: Clique no trilho inferior da barra de rolagem e na seta física
                try:
                    gui.click(x_trilho_barra, y_trilho_barra)
                    gui.click(x_trilho_barra, y_seta_barra)
                except Exception:
                    pass

                time.sleep(0.12)
                pos_702, qual_tpl = _buscar_702_estrito()
                if pos_702:
                    logger.info(f"Opção 702 localizada com sucesso no ciclo {ciclo + 1} em {pos_702}!")
                    break

        if not pos_702:
            logger.warning("Opção 702 ('UnimedVA - Cartão Ponto Portal') NÃO encontrada após rolagem completa.")
            return False

        # 4. Calcula o ponto exato do clique no NOME 'UnimedVA - Cartão Ponto Portal'
        if qual_tpl and "opcao_702_oficial" in str(qual_tpl):
            x_nome = pos_702[0] + 35
            y_nome = pos_702[1]
        else:
            x_nome = pos_702[0]
            y_nome = pos_702[1]

        logger.info(f"Clicando com precisão no NOME da opção 702 em ({x_nome}, {y_nome})...")
        gui.click(x_nome, y_nome)
        time.sleep(0.3)
        gui.click(x_nome, y_nome)
        time.sleep(0.8)

        # 5. Clica no botão Executar
        logger.info(f"Clicando no botão Executar em {pos_exec}...")
        gui.click(pos_exec[0], pos_exec[1])
        time.sleep(3)

        logger.info("Passo 5 executado com sucesso!")
        return True

    def calcular_periodo_pdd(self, dia_simulado: Optional[int] = 4) -> tuple[str, str]:
        """
        Calcula as datas inicial e final de apuração de acordo com a regra do PDD (Passo 6):
        - Dia 20: Início dia 20 mês anterior | Fim dia 19 mês atual
        - Dia 30: Início dia 20 mês anterior | Fim dia 19 mês atual
        - Dia 04: Início dia 20 penúltimo mês | Fim dia 19 mês anterior
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # =========================================================================
        # SIMULAÇÃO DE TESTE DO DIA 04 (PDD Passo 6)
        # Para produção, comente dia_exec = dia_simulado e descomente dia_exec = agora.day
        # =========================================================================
        agora = datetime.now()
        dia_exec = dia_simulado if dia_simulado is not None else agora.day

        if dia_exec == 4:
            # Dia 04:
            # Data Inicial: dia 20 do penúltimo mês (agora - 2 meses)
            # Data Final: dia 19 do mês anterior (agora - 1 mês)
            dt_ini = (agora - relativedelta(months=2)).replace(day=20)
            dt_fim = (agora - relativedelta(months=1)).replace(day=19)
        elif dia_exec in (20, 30):
            # Dias 20 e 30:
            # Data Inicial: dia 20 do mês anterior (agora - 1 mês)
            # Data Final: dia 19 do mês atual
            dt_ini = (agora - relativedelta(months=1)).replace(day=20)
            dt_fim = agora.replace(day=19)
        else:
            # Fallback padrão: regra do dia 04
            dt_ini = (agora - relativedelta(months=2)).replace(day=20)
            dt_fim = (agora - relativedelta(months=1)).replace(day=19)

        str_ini = dt_ini.strftime("%d/%m/%Y")
        str_fim = dt_fim.strftime("%d/%m/%Y")
        logger.info(f"Período de apuração calculado para o dia {dia_exec:02d}: {str_ini} até {str_fim}")
        return str_ini, str_fim

    def preencher_datas_e_gerar(self, data_inicial: Optional[str] = None, data_final: Optional[str] = None, timeout_janela: int = 15) -> bool:
        """
        PASSO 6:
        1. Aguardar o modal 'FGETENTRANCE - Valores de Entrada';
        2. Preencher 'Data Inicial';
        3. Preencher 'Data Final';
        4. Clicar no botão 'OK' (aguardar processamento de 7 a 10 min).
        """
        # Se as datas não foram passadas, calcula automaticamente pela regra do PDD
        if not data_inicial or not data_final:
            data_inicial, data_final = self.calcular_periodo_pdd(dia_simulado=4)

        logger.info(f"Iniciando Passo 6: Preenchimento de Valores de Entrada ({data_inicial} até {data_final})...")

        # 1. Aguarda a janela 'Valores de Entrada' abrir (identificada pelo título, botão Ok ou label)
        tpl_tit = self._obter_template("titulo_valores_entrada.png")
        tpl_ok = self._obter_template("botao_ok_entrada.png")
        tpl_lbl_ini = self._obter_template("label_data_inicial.png")
        tpl_lbl_fim = self._obter_template("label_data_final.png")

        pos_lbl_ini = None
        if tpl_lbl_ini:
            pos_lbl_ini = gui.wait_for(str(tpl_lbl_ini), timeout=timeout_janela, confidence=0.75)

        if not pos_lbl_ini and tpl_tit:
            pos_t = gui.wait_for(str(tpl_tit), timeout=5, confidence=0.75)
            if pos_t:
                # Ancoragem relativa: o label 'Data Inicial:' fica ~45px abaixo e ~50px à direita do título
                pos_lbl_ini = (pos_t[0] + 50, pos_t[1] + 45)

        if not pos_lbl_ini and tpl_ok:
            pos_ok_tmp = gui.wait_for(str(tpl_ok), timeout=5, confidence=0.75)
            if pos_ok_tmp:
                # Ancoragem relativa a partir do botão Ok
                pos_lbl_ini = (pos_ok_tmp[0] - 550, pos_ok_tmp[1] + 25)

        if not pos_lbl_ini:
            logger.warning("Janela 'Valores de Entrada' não encontrada após timeout.")
            return False

        logger.info(f"Janela 'Valores de Entrada' identificada! Label Data Inicial em {pos_lbl_ini}.")

        # 2. Clica no campo de texto da Data Inicial (~65px à direita do label)
        x_campo_ini = pos_lbl_ini[0] + 65
        y_campo_ini = pos_lbl_ini[1]
        logger.info(f"Preenchendo Campo 'Data Inicial' com '{data_inicial}' em ({x_campo_ini}, {y_campo_ini})...")
        gui.click(x_campo_ini, y_campo_ini)
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        # Digita a data sem barras para preencher a máscara nativa do Senior
        gui.type_text(data_inicial.replace("/", ""))
        time.sleep(0.3)

        # 3. Pressiona TAB para avançar diretamente ao campo Data Final
        logger.info(f"Preenchendo Campo 'Data Final' com '{data_final}'...")
        gui.press("tab")
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        gui.type_text(data_final.replace("/", ""))
        time.sleep(0.5)

        # Salva print de auditoria dos campos preenchidos
        try:
            print_preenchido = self.prints_dir / "07_valores_entrada_preenchidos.png"
            gui.screenshot(save_to=str(print_preenchido))
            logger.info(f"Print dos campos preenchidos salvo em: {print_preenchido}")
        except Exception:
            pass

        # 4. Localiza e clica no botão 'Ok'
        pos_ok = None
        if tpl_ok:
            pos_ok = gui.wait_for(str(tpl_ok), timeout=4, confidence=0.75)

        if not pos_ok:
            # Ancoragem alternativa: botão Ok fica ~550px à direita do campo Data Inicial
            pos_ok = (x_campo_ini + 510, y_campo_ini - 20)

        logger.info(f"Clicando no botão 'Ok' da janela Valores de Entrada em {pos_ok}...")
        gui.click(pos_ok[0], pos_ok[1])
        time.sleep(3)

        # Salva print pós-clique no Ok (início do processamento)
        try:
            print_pos_ok = self.prints_dir / "08_inicio_processamento_relatorio.png"
            gui.screenshot(save_to=str(print_pos_ok))
            logger.info(f"Print pós-Ok salvo em: {print_pos_ok}")
        except Exception:
            pass

        logger.info("Passo 6 executado com sucesso! Relatório disparado para geração.")
        return True

    def aguardar_arquivo_pdf_estabilizado(
        self,
        pasta: Path,
        nome_esperado: str,
        timeout_segundos: int = 600,
    ) -> Optional[Path]:
        """
        Aguarda o relatório ser totalmente gerado na pasta pelo Senior,
        aguarda virar .pdf, estabilizar o tamanho (sem alteração por 3s)
        e valida a integridade com PdfReader antes de liberar para o próximo passo.
        """
        from pypdf import PdfReader
        arquivo_alvo = pasta / nome_esperado
        inicio = time.time()
        ultimo_tamanho = -1

        logger.info(f"Monitorando pasta '{pasta}' aguardando arquivo PDF finalizado...")

        while time.time() - inicio < timeout_segundos:
            # 1. Procura pelo arquivo alvo ou arquivos gerados pelo Senior na pasta
            candidato = None

            if arquivo_alvo.exists() and arquivo_alvo.stat().st_size > 0:
                candidato = arquivo_alvo
            else:
                # Se ainda não está com o nome esperado, verifica se há HRCP702.pdf ou HRCP702.imp
                candidatos_pasta = list(pasta.glob("HRCP702*.pdf")) + list(pasta.glob("HRCP702*.imp"))
                if candidatos_pasta:
                    # Pega o mais recente
                    candidatos_pasta.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    mais_recente = candidatos_pasta[0]
                    if mais_recente.stat().st_size > 0:
                        # Se for .imp ou sem a data, tenta renomear para o nome esperado
                        if mais_recente != arquivo_alvo:
                            try:
                                if arquivo_alvo.exists():
                                    arquivo_alvo.unlink()
                                mais_recente.rename(arquivo_alvo)
                                logger.info(f"Arquivo renomeado para o padrão final: {mais_recente.name} -> {arquivo_alvo.name}")
                                candidato = arquivo_alvo
                            except Exception:
                                candidato = mais_recente
                        else:
                            candidato = mais_recente

            # 2. Se encontrou um candidato, testa a estabilização do tamanho e leitura
            if candidato and candidato.exists():
                tam_atual = candidato.stat().st_size
                if tam_atual > 0:
                    if tam_atual == ultimo_tamanho:
                        # Tamanho estável por pelo menos 1 ciclo! Testa se o arquivo está desbloqueado e é um PDF íntegro
                        try:
                            with open(candidato, "rb") as f_test:
                                reader = PdfReader(f_test)
                                num_pags = len(reader.pages)
                                if num_pags > 0:
                                    logger.info(
                                        f"Arquivo PDF validado com sucesso: '{candidato.name}' "
                                        f"({num_pags} páginas, {tam_atual} bytes)."
                                    )
                                    return candidato
                        except Exception as e:
                            logger.info(f"Arquivo ainda sendo finalizado pelo Senior ({e}). Aguardando gravação...")
                    else:
                        logger.info(f"Arquivo em gravação pelo Senior... Tamanho atual: {tam_atual} bytes. Aguardando estabilização...")
                        ultimo_tamanho = tam_atual
                else:
                    logger.info("Arquivo detectado com 0 bytes. Aguardando escrita do Senior...")

            tempo_decorrido = int(time.time() - inicio)
            if tempo_decorrido % 15 == 0 and tempo_decorrido > 0:
                logger.info(f"Aguardando PDF ser finalizado na rede ({tempo_decorrido}s / {timeout_segundos}s)...")

            time.sleep(3)

        logger.error(f"Timeout de {timeout_segundos}s aguardando arquivo PDF ser finalizado em '{pasta}'.")
        return None

    def aguardar_relatorio_e_salvar(self, caminho_destino_pdf: Optional[Path] = None, timeout_segundos: Optional[int] = None) -> Optional[Path]:
        """
        PASSO 7:
        Aguarda o relatório ser gerado pelo Senior, clica no ícone do disquete ('Salvar'),
        navega até a pasta específica com a DATA DA EXECUÇÃO (ex: V:\grp-aud-doc\DIGITALY_CARTAO_PONTO\08112026),
        salva o arquivo como HRCP702_DDMMAAAA.pdf e aguarda a finalização e estabilização completa do PDF.
        """
        from datetime import datetime
        import pyperclip

        timeout_max = timeout_segundos or settings.SENIOR_TIMEOUT_RELATORIO_SEGUNDOS

        # 1. Define a pasta base e a subpasta com a DATA DA EXECUÇÃO (ex: 08112026)
        pasta_base = Path(settings.REDE_PASTA_CONSOLIDADO or r"V:\grp-aud-doc\DIGITALY_CARTAO_PONTO")
        data_hoje_str = datetime.now().strftime("%d%m%Y")
        pasta_destino = pasta_base / data_hoje_str

        try:
            pasta_destino.mkdir(parents=True, exist_ok=True)
            (pasta_destino / "individuais").mkdir(parents=True, exist_ok=True)
            (pasta_destino / "relatorios").mkdir(parents=True, exist_ok=True)
            logger.info(f"Pasta da execução do dia criada/confirmada na rede: {pasta_destino}")
        except Exception as e:
            logger.error(f"Erro ao criar pastas de rede em '{pasta_destino}': {e}")

        nome_consolidado_padrao = f"HRCP702_{data_hoje_str}.pdf"
        if caminho_destino_pdf:
            arquivo_final = Path(caminho_destino_pdf)
            arquivo_final.parent.mkdir(parents=True, exist_ok=True)
        else:
            arquivo_final = pasta_destino / nome_consolidado_padrao

        logger.info(f"PASSO 7: Aguardando relatório ser gerado pelo Senior (timeout: {timeout_max}s / ~{timeout_max//60} min)...")
        logger.info(f"Arquivo final será salvo em: {arquivo_final}")

        tpl_disquete = self._obter_template("icone_salvar_disquete.png")
        tpl_tit_rel = self._obter_template("titulo_visualizacao_relatorio.png")
        tpl_vis = self._obter_template("barra_visualizar_100.png")
        tpl_btn_salvar = self._obter_template("botao_salvar_dialogo.png")

        inicio = time.time()
        pos_disquete = None

        # 2. Polling até a janela do relatório abrir
        while time.time() - inicio < timeout_max:
            if tpl_disquete:
                pos_disquete = gui.locate_center_on_screen(str(tpl_disquete), confidence=0.75)
                if pos_disquete:
                    logger.info(f"Ícone de Salvar (Disquete) detectado em: {pos_disquete}!")
                    break

            if tpl_tit_rel:
                pos_tit = gui.locate_center_on_screen(str(tpl_tit_rel), confidence=0.75)
                if pos_tit:
                    logger.info("Título 'Visualização do Relatório' detectado!")
                    pos_disquete = (pos_tit[0] + 240, pos_tit[1] + 25)
                    break

            if tpl_vis:
                pos_vis = gui.locate_center_on_screen(str(tpl_vis), confidence=0.75)
                if pos_vis:
                    logger.info(f"Barra de ferramentas do relatório detectada em {pos_vis}!")
                    pos_disquete = (pos_vis[0] + 62, pos_vis[1])
                    break

            tempo_decorrido = int(time.time() - inicio)
            if tempo_decorrido % 15 == 0:
                logger.info(f"Aguardando geração do relatório no Senior... ({tempo_decorrido}s decorridos)")

            time.sleep(2)

        if not pos_disquete:
            logger.error(f"Timeout de {timeout_max}s: Janela de relatório não apareceu na tela.")
            return None

        # 3. Foca na janela de Visualização e clica no disquete
        logger.info("Trazendo janela 'Visualização do Relatório' para foco...")
        gui.focar_janela("Visualização do Relatório")
        time.sleep(0.5)

        logger.info(f"Clicando no ícone do disquete (Salvar) em {pos_disquete}...")
        gui.click(pos_disquete[0], pos_disquete[1])
        time.sleep(2)

        # 4. Navega obrigatoriamente para dentro da pasta da data (ex: V:\grp-aud-doc\DIGITALY_CARTAO_PONTO\08112026)
        logger.info(f"Navegando o diálogo Salvar como para a pasta da data: '{pasta_destino}'...")
        gui.hotkey("alt", "n")
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        pyperclip.copy(str(pasta_destino))
        gui.hotkey("ctrl", "v")
        time.sleep(0.3)
        gui.press("enter")
        time.sleep(1.2)

        # 5. Preenche o nome do arquivo no campo 'Nome:'
        nome_arquivo = arquivo_final.name
        logger.info(f"Inserindo nome do arquivo '{nome_arquivo}' no campo Nome...")
        gui.hotkey("alt", "n")
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        pyperclip.copy(nome_arquivo)
        gui.hotkey("ctrl", "v")
        time.sleep(0.5)

        # 6. Clica em 'Salvar'
        salvo_clicado = False
        if tpl_btn_salvar:
            pos_btn_salvar = gui.locate_center_on_screen(str(tpl_btn_salvar), confidence=0.75)
            if pos_btn_salvar:
                logger.info(f"Clicando no botão 'Salvar' em {pos_btn_salvar}...")
                gui.click(pos_btn_salvar[0], pos_btn_salvar[1])
                salvo_clicado = True

        if not salvo_clicado:
            logger.info("Acionando botão 'Salvar' via atalho Alt+S / Enter...")
            gui.hotkey("alt", "s")
            time.sleep(0.3)
            gui.press("enter")

        time.sleep(1.5)

        # Trata possível modal de confirmação de substituição ('Deseja substituí-lo? Sim')
        gui.hotkey("alt", "s")
        time.sleep(0.3)
        gui.press("enter")
        time.sleep(2)

        # 7. Aguarda o arquivo ser totalmente carregado na pasta, virar .pdf e estabilizar o tamanho
        logger.info(f"Aguardando arquivo ser gerado e estabilizado como PDF em '{pasta_destino}'...")
        arquivo_validado = self.aguardar_arquivo_pdf_estabilizado(
            pasta=pasta_destino,
            nome_esperado=arquivo_final.name,
            timeout_segundos=timeout_max,
        )

        # Salva print de auditoria do Passo 7
        try:
            print_salvo = self.prints_dir / "10_relatorio_consolidado_salvo.png"
            gui.screenshot(save_to=str(print_salvo))
            logger.info(f"Print pós-salvamento registrado em: {print_salvo}")
        except Exception:
            pass

        if arquivo_validado and arquivo_validado.exists():
            logger.info(f"Passo 7 executado com sucesso! Arquivo consolidado pronto: {arquivo_validado}")
            return arquivo_validado
        else:
            logger.warning("Passo 7 concluído mas a gravação e estabilização do arquivo não pôde ser confirmada.")
            return arquivo_final

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
