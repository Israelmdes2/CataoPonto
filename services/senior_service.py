import ctypes
import logging
import subprocess
import time
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple

import psutil
import pyperclip
from dateutil.relativedelta import relativedelta
from pypdf import PdfReader

from core.config import settings
from infrastructure.automation import gui
from schemas.execucao import ModoExecucao, PeriodoCartao

logger = logging.getLogger(__name__)

TERMOS_JANELA_SENIOR = (
    "controle de ponto e refeitório",
    "gestão de pessoas",
    "vetorh",
    "ronda",
    "senior",
    "seleção de modelos",
    "modelos para execução",
)
EXECUTAVEIS_SENIOR = {"ronda.exe", "iniciar.exe", "rubi.exe", "cs.exe", "senior.exe"}
PASTA_REDE_PADRAO = r"V:\grp-aud-doc\DIGITALY_CARTAO_PONTO"


def _subtrair_meses(ano: int, mes: int, meses_a_subtrair: int) -> Tuple[int, int]:
    total_meses = (ano * 12 + mes - 1) - meses_a_subtrair
    return total_meses // 12, (total_meses % 12) + 1


class SeniorService:
    """Serviço de automação visual do sistema Senior Desktop (Vetorh/Ronda)."""

    def __init__(self, ambiente: str = "producao"):
        self.ambiente = "homologacao" if "homolog" in ambiente.lower() else "producao"
        self.templates_dir = Path(settings.SENIOR_TEMPLATES_DIR)
        self.prints_dir = Path("assets/prints") / self.ambiente
        self.confidence = settings.SENIOR_CONFIDENCE
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.pid: Optional[int] = None

    @staticmethod
    def calcular_periodo_datas(
        data_referencia: Optional[date] = None,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
    ) -> PeriodoCartao:
        """Calcula o período de apuração conforme o modo do PDD (04, 20, 30 ou auto)."""
        referencia = data_referencia or date.today()
        modo_str = modo.value if isinstance(modo, ModoExecucao) else str(modo)

        if modo_str == "auto":
            if referencia.day <= 10:
                modo_str = "04"
            elif referencia.day <= 25:
                modo_str = "20"
            else:
                modo_str = "30"

        if modo_str in ("20", "30"):
            ano_ini, mes_ini = _subtrair_meses(referencia.year, referencia.month, 1)
            data_ini = date(ano_ini, mes_ini, 20)
            data_fim = date(referencia.year, referencia.month, 19)
        elif modo_str == "04":
            ano_ini, mes_ini = _subtrair_meses(referencia.year, referencia.month, 2)
            data_ini = date(ano_ini, mes_ini, 20)
            ano_fim, mes_fim = _subtrair_meses(referencia.year, referencia.month, 1)
            data_fim = date(ano_fim, mes_fim, 19)
        else:
            raise ValueError(f"Modo de execução inválido: {modo_str}. Use '20', '30', '04' ou 'auto'.")

        return PeriodoCartao(
            data_inicial=data_ini.strftime("%d/%m/%Y"),
            data_final=data_fim.strftime("%d/%m/%Y"),
            modo_aplicado=modo_str,
        )

    def _obter_template(self, nome_arquivo: str) -> Optional[Path]:
        """Busca o template primeiro na pasta do ambiente e depois na raiz de templates."""
        caminho_ambiente = self.templates_dir / self.ambiente / nome_arquivo
        if caminho_ambiente.exists():
            return caminho_ambiente
        caminho_raiz = self.templates_dir / nome_arquivo
        if caminho_raiz.exists():
            return caminho_raiz
        return None

    @staticmethod
    def _localizar_com_confiancas(
        caminho_template: Optional[Path],
        confiancas: Iterable[float],
    ) -> Optional[Tuple[int, int]]:
        """Tenta localizar um template visual percorrendo níveis decrescentes de confiança."""
        if not caminho_template:
            return None
        for nivel_confianca in confiancas:
            posicao = gui.locate_center_on_screen(str(caminho_template), confidence=nivel_confianca)
            if posicao:
                return posicao
        return None

    def focar_janela_senior(self) -> bool:
        """Coloca a janela ativa do Senior em primeiro plano."""
        return gui.focar_senior_geral()

    def _esta_visivel(self, nome_template: str, confidence: float = 0.70) -> bool:
        """Verifica se um elemento visual está visível na tela sem bloquear."""
        template = self._obter_template(nome_template)
        if not template:
            return False
        return gui.is_visible(str(template), confidence=confidence)

    def tratar_obstaculos_conhecidos(self) -> bool:
        """Foca a janela do Senior e expande o ícone de módulo se estiver bloqueando a tela."""
        self.focar_janela_senior()
        template_modulo = self._obter_template("icone_modulo.png")
        if template_modulo and gui.is_visible(str(template_modulo), confidence=0.70):
            posicao = gui.locate_center_on_screen(str(template_modulo), confidence=0.70)
            if posicao:
                gui.click(posicao[0], posicao[1])
                time.sleep(2)
                return True
        return False

    def _clicar_icone_modulo_se_necessario(self, timeout: int = 6) -> bool:
        """Trata a tela intermediária de seleção de módulo quando exibida."""
        return self.tratar_obstaculos_conhecidos()

    def garantir_menu_principal_pronto(self, timeout: float = 30.0) -> bool:
        """Aguarda até que o menu principal ('Cálculos') esteja visível e desobstruído."""
        prazo_limite = time.time() + timeout
        template_calculos = self._obter_template("menu_calculos.png")
        template_modulo = self._obter_template("icone_modulo.png")

        while time.time() < prazo_limite:
            self.focar_janela_senior()
            if template_calculos and gui.is_visible(str(template_calculos), confidence=0.70):
                return True

            if template_modulo and gui.is_visible(str(template_modulo), confidence=0.68):
                posicao = gui.locate_center_on_screen(str(template_modulo), confidence=0.68)
                if posicao:
                    gui.click(posicao[0], posicao[1])
                    time.sleep(3)
                    continue

            self.tratar_obstaculos_conhecidos()
            time.sleep(1.0)

        logger.warning(f"Menu principal não detectado após {timeout}s.")
        return False

    def _clicar_se_encontrar(
        self,
        nome_template: str,
        timeout: int = 10,
        descricao: str = "",
        tentar_recuperar: bool = True,
    ) -> bool:
        """Localiza o template na tela (com auto-recuperação opcional) e executa o clique."""
        caminho_template = self._obter_template(nome_template)
        nome_legivel = descricao or nome_template

        if not caminho_template:
            logger.warning(f"Template visual ausente: '{nome_template}' ({nome_legivel}).")
            return False

        try:
            posicao = gui.wait_for(str(caminho_template), timeout=timeout, confidence=self.confidence)
            if posicao:
                gui.click(posicao[0], posicao[1])
                return True

            if tentar_recuperar and self.tratar_obstaculos_conhecidos():
                posicao_retentativa = gui.wait_for(str(caminho_template), timeout=5, confidence=self.confidence)
                if posicao_retentativa:
                    gui.click(posicao_retentativa[0], posicao_retentativa[1])
                    return True

            logger.warning(f"Elemento '{nome_legivel}' não encontrado após {timeout}s.")
            return False
        except Exception as erro:
            logger.error(f"Erro ao localizar '{nome_legivel}': {erro}")
            return False

    def abrir_sistema_senior(self, ambiente: str = "producao") -> bool:
        """Dispara o executável do Senior diretamente pelo servidor ou instalação local."""
        eh_homologacao = "homolog" in ambiente.lower()
        pasta_servidor = "Senior_HML" if eh_homologacao else "Senior"
        servidor_host = "SRVVETORH-HML" if eh_homologacao else "SRVVETORH"
        diretorio_senior = r"C:\Senior-hml" if eh_homologacao else r"C:\Senior"
        executavel_rede = f"\\\\{servidor_host}\\{pasta_servidor}\\Iniciar.exe"
        argumentos = f'-SystemModule:VETORH.RONDA -seniordir:"{diretorio_senior}\\"'

        try:
            processo = subprocess.Popen(f'"{executavel_rede}" {argumentos}', shell=True)
            if processo and processo.pid:
                self.pid = processo.pid
            time.sleep(6)
            self.focar_janela_senior()
            return True
        except Exception as erro:
            logger.error(f"Erro ao disparar Senior via rede: {erro}")

        executavel_local = Path(diretorio_senior) / "Vetorh" / "RONDA.EXE"
        if executavel_local.exists():
            try:
                processo = subprocess.Popen([str(executavel_local)], cwd=str(executavel_local.parent))
                if processo and processo.pid:
                    self.pid = processo.pid
                time.sleep(6)
                self.focar_janela_senior()
                return True
            except Exception as erro:
                logger.error(f"Erro ao disparar Senior local: {erro}")

        return False

    def obter_pids_senior(self) -> set[int]:
        """Localiza todos os PIDs de janelas e processos ativos pertencentes ao Senior/Ronda."""
        pids: set[int] = set()
        if self.pid and psutil.pid_exists(self.pid):
            pids.add(self.pid)

        try:
            user32 = ctypes.windll.user32

            def _enumerar_janela(hwnd, _extra):
                if not user32.IsWindowVisible(hwnd):
                    return True
                tamanho = user32.GetWindowTextLengthW(hwnd)
                if tamanho <= 0:
                    return True
                buffer_titulo = ctypes.create_unicode_buffer(tamanho + 1)
                user32.GetWindowTextW(hwnd, buffer_titulo, tamanho + 1)
                titulo = buffer_titulo.value.lower()
                if any(termo in titulo for termo in TERMOS_JANELA_SENIOR):
                    pid_janela = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_janela))
                    if pid_janela.value:
                        pids.add(pid_janela.value)
                return True

            tipo_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(tipo_callback(_enumerar_janela), 0)
        except Exception as erro:
            logger.debug(f"Aviso ao buscar PID por HWND: {erro}")

        try:
            for processo in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
                try:
                    nome = (processo.info["name"] or "").lower()
                    caminho_exe = (processo.info["exe"] or "").lower()
                    linha_comando = " ".join(processo.info.get("cmdline") or []).lower()

                    if nome in EXECUTAVEIS_SENIOR:
                        pids.add(processo.info["pid"])
                    elif "senior" in caminho_exe and ("vetorh" in caminho_exe or "ronda" in caminho_exe):
                        pids.add(processo.info["pid"])
                    elif "senior-hml" in linha_comando or "vetorh.ronda" in linha_comando:
                        pids.add(processo.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as erro:
            logger.debug(f"Aviso ao iterar processos do Senior: {erro}")

        return pids

    def encerrar_senior(self, pid: Optional[int] = None) -> bool:
        """Encerra com segurança os processos pai e filhos do Senior Desktop via PID."""
        pids_alvo = {pid} if pid else self.obter_pids_senior()
        if not pids_alvo:
            return False

        encerrados = 0
        for pid_atual in pids_alvo:
            try:
                if not psutil.pid_exists(pid_atual):
                    continue
                processo = psutil.Process(pid_atual)
                filhos = processo.children(recursive=True)
                for processo_filho in filhos:
                    try:
                        processo_filho.terminate()
                    except Exception:
                        pass
                processo.terminate()

                _, processos_vivos = psutil.wait_procs([processo] + filhos, timeout=3.0)
                for vivo in processos_vivos:
                    try:
                        vivo.kill()
                    except Exception:
                        pass
                encerrados += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                try:
                    subprocess.run(f"taskkill /PID {pid_atual} /T /F", shell=True, capture_output=True)
                    encerrados += 1
                except Exception:
                    pass

        self.pid = None
        return encerrados > 0

    def autenticar_senior(self, usuario: Optional[str] = None, senha: Optional[str] = None) -> bool:
        """Executa o login no Senior preservando maiúsculas/minúsculas via área de transferência."""
        usuario_final = (usuario or settings.SENIOR_LOGIN or "").strip().lower()
        senha_final = senha or settings.SENIOR_PASSWORD
        self._clicar_icone_modulo_se_necessario(timeout=3)

        template_autenticar = self._obter_template("botao_autenticar.png")
        if template_autenticar:
            posicao_botao = gui.wait_for(str(template_autenticar), timeout=12, confidence=self.confidence)
            if posicao_botao:
                # Campo de usuário fica 93px acima do centro do botão Autenticar em 1080p;
                # pyperclip evita perda de Shift/CapsLock durante digitação em sessões RDP.
                gui.click(posicao_botao[0], posicao_botao[1] - 93)
                time.sleep(0.5)
                gui.hotkey("ctrl", "a")
                gui.press("backspace")
                pyperclip.copy(usuario_final)
                gui.hotkey("ctrl", "v")
                gui.press("tab")
                time.sleep(0.5)
                gui.hotkey("ctrl", "a")
                gui.press("backspace")
                pyperclip.copy(senha_final)
                gui.hotkey("ctrl", "v")
                time.sleep(0.2)
                pyperclip.copy("")
                time.sleep(0.5)
                gui.click(posicao_botao[0], posicao_botao[1])
                time.sleep(5)
                return True

        if self._clicar_se_encontrar("campo_login.png", timeout=5, descricao="Campo de Login"):
            gui.hotkey("ctrl", "a")
            gui.press("backspace")
            gui.type_text(usuario_final)
            gui.press("tab")
            time.sleep(0.5)
            gui.type_text(senha_final)
            time.sleep(0.5)
            self._clicar_se_encontrar("botao_autenticar.png", timeout=5, descricao="Botão Autenticar")
            time.sleep(5)
            return True

        return False

    def navegar_para_cartao_ponto(self) -> bool:
        """Navega pelo menu do Senior até Cálculos -> Apuração -> Listar -> Cartão Ponto."""
        self.garantir_menu_principal_pronto(timeout=25)
        etapas_menu = (
            ("menu_calculos.png", "Aba Cálculos"),
            ("menu_apuracao.png", "Opção Apuração"),
            ("menu_listar.png", "Opção Listar"),
            ("menu_cartao_ponto.png", "Opção Cartão Ponto"),
        )
        for template, descricao in etapas_menu:
            self._clicar_se_encontrar(template, timeout=4, descricao=descricao)
            time.sleep(0.3)
        return True

    def _selecionar_modelo_relatorio(
        self,
        codigo: str,
        descricao: str,
        tpl_opcao_nome: str,
        tpl_nome_modelo: str,
        timeout_janela: int = 15,
        direcao_scroll: str = "down",
    ) -> bool:
        """Localiza e aplica duplo clique no modelo desejado na janela Seleção de Modelos."""
        template_titulo = self._obter_template("titulo_selecao_modelos.png")
        template_executar = self._obter_template("botao_executar.png")
        template_opcao = self._obter_template(tpl_opcao_nome)
        template_nome = self._obter_template(tpl_nome_modelo)

        posicao_executar = None
        if template_executar:
            posicao_executar = gui.wait_for(str(template_executar), timeout=timeout_janela, confidence=self.confidence)

        if not posicao_executar and template_titulo:
            posicao_titulo = gui.wait_for(str(template_titulo), timeout=4, confidence=self.confidence)
            if posicao_titulo:
                if template_executar:
                    posicao_executar = gui.wait_for(str(template_executar), timeout=3, confidence=self.confidence)
                if not posicao_executar:
                    posicao_executar = (posicao_titulo[0] + 510, posicao_titulo[1] + 35)

        if not posicao_executar:
            logger.warning("Janela 'Seleção de Modelos para Execução' não encontrada.")
            return False

        x_grade = posicao_executar[0] - 300
        y_grade = posicao_executar[1] + 60
        x_trilho = posicao_executar[0] - 55
        y_trilho = posicao_executar[1] + 110
        y_seta_barra = posicao_executar[1] + 165

        def _buscar_estrito():
            for template in (template_opcao, template_nome):
                posicao = self._localizar_com_confiancas(template, (0.88, 0.82))
                if posicao:
                    return posicao, template
            return None, None

        posicao_modelo, template_usado = _buscar_estrito()
        if not posicao_modelo:
            gui.click(x_grade, y_grade)
            time.sleep(0.3)
            posicao_modelo, template_usado = _buscar_estrito()

        if not posicao_modelo:
            for _ in range(25):
                if direcao_scroll == "up":
                    gui.press("home")
                    gui.scroll(5)
                else:
                    gui.scroll(-4)
                    gui.press("pagedown")
                    gui.press("down")
                    gui.click(x_trilho, y_trilho)
                    gui.click(x_trilho, y_seta_barra)

                time.sleep(0.12)
                posicao_modelo, template_usado = _buscar_estrito()
                if posicao_modelo:
                    break

        if not posicao_modelo:
            logger.warning(f"Modelo {codigo} ('{descricao}') não encontrado na grade.")
            return False

        deslocamento_x = 35 if template_usado and tpl_opcao_nome in str(template_usado) else 0
        x_nome = posicao_modelo[0] + deslocamento_x
        y_nome = posicao_modelo[1]

        # Duplo clique diretamente no nome aciona a abertura imediata do modal Valores de Entrada
        gui.click(x_nome, y_nome)
        time.sleep(0.3)
        gui.click(x_nome, y_nome)
        time.sleep(0.8)
        return True

    def selecionar_relatorio_702(self, timeout_janela: int = 15) -> bool:
        """Seleciona o modelo 702 ('UnimedVA - Cartão Ponto Portal')."""
        return self._selecionar_modelo_relatorio(
            codigo="702",
            descricao="UnimedVA - Cartão Ponto Portal",
            tpl_opcao_nome="opcao_702_oficial.png",
            tpl_nome_modelo="nome_702_oficial.png",
            timeout_janela=timeout_janela,
            direcao_scroll="down",
        )

    def selecionar_relatorio_001(self, timeout_janela: int = 15) -> bool:
        """Seleciona o modelo 001 ('Cartão Ponto Simples')."""
        return self._selecionar_modelo_relatorio(
            codigo="001",
            descricao="Cartão Ponto Simples",
            tpl_opcao_nome="opcao_001_oficial.png",
            tpl_nome_modelo="nome_001_oficial.png",
            timeout_janela=timeout_janela,
            direcao_scroll="up",
        )

    def calcular_periodo_pdd(self, dia_simulado: Optional[int] = None) -> tuple[str, str]:
        """Calcula o período fixo de apuração: dia 20 do mês anterior até dia 19 do mês atual."""
        agora = datetime.now()
        data_ini = (agora - relativedelta(months=1)).replace(day=20)
        data_fim = agora.replace(day=19)
        return data_ini.strftime("%d/%m/%Y"), data_fim.strftime("%d/%m/%Y")

    def fechar_janela_pesquisa_registro_se_aberta(self, timeout: int = 10) -> bool:
        """Fecha a janela 'Pesquisa de registro' com ESC caso ela abra acidentalmente."""
        template_pesquisa = self._obter_template("titulo_pesquisa_registro.png")
        if not template_pesquisa:
            return False

        inicio = time.time()
        while time.time() - inicio < timeout:
            posicao = self._localizar_com_confiancas(template_pesquisa, (0.82, 0.75, 0.70))
            if posicao:
                gui.click(posicao[0], posicao[1])
                time.sleep(0.3)
                gui.press("esc")
                time.sleep(0.8)
                return True
            time.sleep(0.5)
        return False

    def _aguardar_modal_valores_entrada(self, timeout_janela: int) -> Optional[Tuple[int, int]]:
        """Aguarda a abertura do modal Valores de Entrada usando múltiplos marcadores visuais."""
        marcadores = (
            (self._obter_template("titulo_valores_entrada.png"), (0.85, 0.75, 0.65)),
            (self._obter_template("aba_entrada.png"), (0.85, 0.72)),
            (self._obter_template("botao_ok_entrada.png"), (0.85, 0.72)),
            (self._obter_template("label_data_inicial_texto.png"), (0.85, 0.72)),
            (self._obter_template("label_data_inicial.png"), (0.85, 0.70)),
        )
        inicio_espera = time.time()
        while time.time() - inicio_espera < timeout_janela:
            for template, confiancas in marcadores:
                posicao = self._localizar_com_confiancas(template, confiancas)
                if posicao:
                    return posicao
            time.sleep(1.0)
        return None

    def _localizar_campo_data_inicial(
        self,
        posicao_referencia: Tuple[int, int],
    ) -> Tuple[int, int]:
        """Localiza a coordenada de clique no início dos dígitos do campo Data Inicial."""
        posicao = self._localizar_com_confiancas(
            self._obter_template("label_data_inicial_texto.png"),
            (0.88, 0.78, 0.68),
        )
        if posicao:
            return posicao[0] + 45, posicao[1]

        posicao = self._localizar_com_confiancas(
            self._obter_template("campo_data_inicial_box.png"),
            (0.85, 0.70),
        )
        if posicao:
            return posicao[0] - 15, posicao[1]

        posicao = self._localizar_com_confiancas(
            self._obter_template("label_data_inicial.png"),
            (0.65,),
        )
        if posicao:
            return posicao[0] + 80, posicao[1]

        posicao = self._localizar_com_confiancas(
            self._obter_template("botao_ok_entrada.png"),
            (0.65,),
        )
        if posicao:
            return posicao[0] - 635, posicao[1] + 20

        return posicao_referencia[0] - 15, posicao_referencia[1] + 50

    def _localizar_campo_data_final(self, campo_inicial: Tuple[int, int]) -> Tuple[int, int]:
        """Localiza a coordenada de clique no início dos dígitos do campo Data Final."""
        posicao = self._localizar_com_confiancas(
            self._obter_template("label_data_final_texto.png"),
            (0.88, 0.78, 0.68),
        )
        if posicao:
            return posicao[0] + 45, posicao[1]
        return campo_inicial[0], campo_inicial[1] + 27

    def preencher_datas_e_gerar(
        self,
        data_inicial: Optional[str] = None,
        data_final: Optional[str] = None,
        timeout_janela: int = 30,
    ) -> bool:
        """Preenche Data Inicial e Final no modal Valores de Entrada com digitação cadenciada e aciona Ok."""
        if not data_inicial or not data_final:
            data_inicial, data_final = self.calcular_periodo_pdd()

        print(f"\n  [>] Valores de Entrada: Data Inicial [{data_inicial}] | Data Final [{data_final}]")
        print("  [..] Aguardando tela 'Valores de Entrada'...")

        posicao_tela = self._aguardar_modal_valores_entrada(timeout_janela)
        if not posicao_tela:
            print("  [X] Tela 'Valores de Entrada' não identificada após timeout.")
            logger.error("Tela 'Valores de Entrada' não identificada.")
            return False

        # Pausa solicitada pelo usuário após detectar a tela antes de iniciar a digitação
        print("  [OK] Tela 'Valores de Entrada' confirmada. Aguardando 5s para digitar...")
        time.sleep(5.0)

        x_ini, y_ini = self._localizar_campo_data_inicial(posicao_tela)
        gui.click(x_ini, y_ini)
        time.sleep(0.5)
        gui.type_text(data_inicial.replace("/", ""), interval=0.5)
        print(f"  [OK] Data Inicial preenchida: {data_inicial}")
        time.sleep(0.5)

        x_fim, y_fim = self._localizar_campo_data_final((x_ini, y_ini))
        gui.click(x_fim, y_fim)
        time.sleep(0.5)
        gui.type_text(data_final.replace("/", ""), interval=0.5)
        print(f"  [OK] Data Final preenchida:   {data_final}")
        time.sleep(0.5)

        # Pausa para conferência visual antes de confirmar o modal
        print("  [..] Aguardando 5s antes de clicar em Ok...")
        time.sleep(5.0)

        posicao_ok = self._localizar_com_confiancas(
            self._obter_template("botao_ok_entrada.png"),
            (0.85, 0.70, 0.55),
        ) or self._localizar_com_confiancas(
            self._obter_template("botao_ok_real_limpo.png"),
            (0.85, 0.70, 0.55),
        )

        if posicao_ok:
            gui.click(posicao_ok[0], posicao_ok[1])
            print("  [OK] Botão 'Ok' clicado com sucesso!")
        else:
            gui.hotkey("alt", "o")
            print("  [OK] Botão 'Ok' acionado via atalho Alt+O!")

        time.sleep(2.5)
        return True

    def aguardar_arquivo_pdf_estabilizado(
        self,
        pasta: Path,
        nome_esperado: str,
        timeout_segundos: int = 600,
    ) -> Optional[Path]:
        """Aguarda o PDF consolidado ser gravado, estabilizar em tamanho e validar páginas."""
        arquivo_alvo = pasta / nome_esperado
        inicio = time.time()
        ultimo_tamanho = -1

        while time.time() - inicio < timeout_segundos:
            candidato = None
            if arquivo_alvo.exists() and arquivo_alvo.stat().st_size > 0:
                candidato = arquivo_alvo
            else:
                candidatos_pdf = [arq for arq in pasta.glob("HRCP*.pdf") if arq.is_file() and arq.stat().st_size > 0]
                if candidatos_pdf:
                    candidatos_pdf.sort(key=lambda arq: arq.stat().st_mtime, reverse=True)
                    mais_recente = candidatos_pdf[0]
                    if mais_recente != arquivo_alvo:
                        try:
                            if arquivo_alvo.exists():
                                arquivo_alvo.unlink()
                            mais_recente.rename(arquivo_alvo)
                            candidato = arquivo_alvo
                        except Exception:
                            candidato = mais_recente
                    else:
                        candidato = mais_recente

            if candidato and candidato.exists():
                tamanho_atual = candidato.stat().st_size
                if tamanho_atual > 0:
                    try:
                        with open(candidato, "rb") as arquivo_binario:
                            cabecalho = arquivo_binario.read(8)
                        if not cabecalho.startswith(b"%PDF"):
                            time.sleep(3)
                            continue
                    except Exception:
                        time.sleep(3)
                        continue

                    if tamanho_atual == ultimo_tamanho:
                        try:
                            with open(candidato, "rb") as arquivo_teste:
                                leitor = PdfReader(arquivo_teste)
                                if len(leitor.pages) > 0:
                                    return candidato
                        except Exception:
                            pass
                    else:
                        ultimo_tamanho = tamanho_atual

            time.sleep(3)

        logger.error(f"Timeout de {timeout_segundos}s aguardando PDF em '{pasta}'.")
        return None

    def selecionar_tipo_arquivo_pdf(self) -> bool:
        """Altera o campo Tipo de 'Arquivos Impressos (*.imp)' para 'Arquivo PDF (*.pdf)'."""
        template_combo_imp = self._obter_template("combo_tipo_imp.png")
        template_label_tipo = self._obter_template("label_tipo.png")
        template_item_pdf = self._obter_template("item_dropdown_pdf_real.png")

        for tentativa in range(1, 4):
            if template_item_pdf:
                posicao_item = gui.locate_center_on_screen(str(template_item_pdf), confidence=0.72)
                if posicao_item:
                    gui.click(posicao_item[0], posicao_item[1])
                    time.sleep(0.5)
                    if not (template_combo_imp and gui.is_visible(str(template_combo_imp), confidence=0.75)):
                        return True

            posicao_combo = None
            if template_combo_imp:
                posicao_combo = gui.locate_center_on_screen(str(template_combo_imp), confidence=0.75)
            if not posicao_combo and template_label_tipo:
                posicao_label = gui.locate_center_on_screen(str(template_label_tipo), confidence=0.75)
                if posicao_label:
                    posicao_combo = (posicao_label[0] + 110, posicao_label[1])

            if posicao_combo:
                gui.click(posicao_combo[0], posicao_combo[1])
                time.sleep(0.5)
                posicao_item = (
                    gui.locate_center_on_screen(str(template_item_pdf), confidence=0.70)
                    if template_item_pdf
                    else None
                )
                if posicao_item:
                    gui.click(posicao_item[0], posicao_item[1])
                else:
                    gui.press("down")
                    time.sleep(0.3)
                    gui.press("enter")
                time.sleep(0.5)

            if not template_combo_imp or not gui.is_visible(str(template_combo_imp), confidence=0.75):
                return True
            logger.warning(f"Tentativa {tentativa}: campo Tipo ainda exibe '*.imp'.")

        logger.error("Falha ao alterar o campo Tipo para PDF após 3 tentativas.")
        return False

    def _aguardar_relatorio_pronto(self) -> Optional[Tuple[int, int]]:
        """Monitora o modal 'Aguarde...' sem corte fixo até a janela do relatório abrir."""
        template_disquete = self._obter_template("icone_salvar_disquete.png")
        template_titulo_relatorio = self._obter_template("titulo_visualizacao_relatorio.png")
        template_aguarde = self._obter_template("modal_aguarde_preparando.png")

        print("\n  [..] Monitorando geração do relatório: aguardando modal 'Aguarde...' sumir...")
        modal_detectado = False
        for _ in range(8):
            if template_aguarde and gui.locate_center_on_screen(str(template_aguarde), confidence=0.75):
                modal_detectado = True
                print("  [..] Modal 'Aguarde, preparando a solicitação...' confirmado na tela.")
                break
            time.sleep(1.0)

        inicio = time.time()
        ultimo_log_segundo = -1
        while True:
            modal_visivel = bool(
                template_aguarde and gui.locate_center_on_screen(str(template_aguarde), confidence=0.78)
            )
            if modal_visivel:
                modal_detectado = True

            if modal_detectado and not modal_visivel:
                print("\n  [OK] Processamento do Senior concluído! Localizando botão Salvar...")
                time.sleep(2.0)
                gui.focar_janela("Visualização do Relatório")
                time.sleep(0.5)
                posicao_disquete = self._localizar_com_confiancas(template_disquete, (0.82, 0.70, 0.58))
                if not posicao_disquete and template_titulo_relatorio:
                    posicao_titulo = gui.locate_center_on_screen(str(template_titulo_relatorio), confidence=0.65)
                    if posicao_titulo:
                        return posicao_titulo[0] + 240, posicao_titulo[1] + 25
                return posicao_disquete

            if template_disquete:
                posicao_disquete = gui.locate_center_on_screen(str(template_disquete), confidence=0.75)
                if posicao_disquete:
                    print("  [OK] Ícone do Disquete detectado na tela!")
                    return posicao_disquete

            if template_titulo_relatorio and (not modal_detectado or not modal_visivel):
                posicao_titulo = gui.locate_center_on_screen(str(template_titulo_relatorio), confidence=0.78)
                if posicao_titulo:
                    print("  [OK] Janela de Visualização do Relatório detectada! Localizando disquete...")
                    time.sleep(1.5)
                    gui.focar_janela("Visualização do Relatório")
                    for _ in range(5):
                        posicao_disquete = self._localizar_com_confiancas(template_disquete, (0.85, 0.75, 0.65))
                        if posicao_disquete:
                            return posicao_disquete
                        time.sleep(0.8)
                    return posicao_titulo[0] + 240, posicao_titulo[1] + 25

            tempo_decorrido = int(time.time() - inicio)
            if tempo_decorrido % 15 == 0 and tempo_decorrido != ultimo_log_segundo:
                ultimo_log_segundo = tempo_decorrido
                print(f"  [..] Senior processando... ({tempo_decorrido // 60}m {tempo_decorrido % 60}s)")

            time.sleep(2)

    def aguardar_relatorio_e_salvar(
        self,
        caminho_destino_pdf: Optional[Path] = None,
        timeout_segundos: Optional[int] = None,
        modelo: str = "702",
    ) -> Optional[Path]:
        """Aguarda a geração do relatório no Senior e salva em PDF na subpasta da data."""
        timeout_max = timeout_segundos or settings.SENIOR_TIMEOUT_RELATORIO_SEGUNDOS
        pasta_base = Path(settings.REDE_PASTA_CONSOLIDADO or PASTA_REDE_PADRAO)
        data_hoje = datetime.now().strftime("%d%m%Y")
        pasta_destino = pasta_base / data_hoje

        try:
            pasta_destino.mkdir(parents=True, exist_ok=True)
            (pasta_destino / "individuais").mkdir(parents=True, exist_ok=True)
            (pasta_destino / "relatorios").mkdir(parents=True, exist_ok=True)
        except Exception as erro:
            logger.error(f"Erro ao criar pastas em '{pasta_destino}': {erro}")

        if caminho_destino_pdf:
            arquivo_final = Path(caminho_destino_pdf)
            arquivo_final.parent.mkdir(parents=True, exist_ok=True)
        else:
            arquivo_final = pasta_destino / f"HRCP{modelo}_{data_hoje}.pdf"

        posicao_disquete = self._aguardar_relatorio_pronto()
        if not posicao_disquete:
            logger.error("Não foi possível localizar o ícone de Salvar do relatório.")
            return None

        gui.focar_janela("Visualização do Relatório")
        time.sleep(0.5)
        print(f"  [..] Clicando no ícone de Salvar em {posicao_disquete}...")
        gui.click(posicao_disquete[0], posicao_disquete[1])
        time.sleep(2.0)

        template_btn_salvar = self._obter_template("botao_salvar_dialogo.png")
        template_disquete = self._obter_template("icone_salvar_disquete.png")
        abriu_dialogo = any(
            template_btn_salvar and gui.locate_center_on_screen(str(template_btn_salvar), confidence=0.70)
            for _ in range(4)
            if not time.sleep(0.5)
        )
        if not abriu_dialogo:
            posicao_nova = (
                gui.locate_center_on_screen(str(template_disquete), confidence=0.65)
                if template_disquete
                else None
            )
            if posicao_nova:
                gui.click(posicao_nova[0], posicao_nova[1])
            else:
                gui.hotkey("ctrl", "s")
            time.sleep(2.0)

        print(f"  [..] Salvando PDF '{arquivo_final.name}' em '{pasta_destino}'...")
        gui.hotkey("alt", "n")
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        pyperclip.copy(str(pasta_destino))
        gui.hotkey("ctrl", "v")
        time.sleep(0.3)
        gui.press("enter")
        time.sleep(1.2)

        if not self.selecionar_tipo_arquivo_pdf():
            logger.warning("Validação visual do tipo PDF não confirmou alteração.")

        gui.hotkey("alt", "n")
        time.sleep(0.3)
        gui.hotkey("ctrl", "a")
        gui.press("backspace")
        pyperclip.copy(arquivo_final.name)
        gui.hotkey("ctrl", "v")
        time.sleep(0.5)

        posicao_salvar = (
            gui.locate_center_on_screen(str(template_btn_salvar), confidence=0.75)
            if template_btn_salvar
            else None
        )
        if posicao_salvar:
            gui.click(posicao_salvar[0], posicao_salvar[1])
        else:
            gui.hotkey("alt", "s")
            time.sleep(0.3)
            gui.press("enter")

        time.sleep(1.5)
        # Confirma eventual modal de sobrescrita ('Deseja substituí-lo? Sim')
        gui.hotkey("alt", "s")
        time.sleep(0.3)
        gui.press("enter")
        time.sleep(2)

        print(f"  [..] Aguardando estabilização do PDF '{arquivo_final.name}'...")
        arquivo_validado = self.aguardar_arquivo_pdf_estabilizado(
            pasta=pasta_destino,
            nome_esperado=arquivo_final.name,
            timeout_segundos=timeout_max,
        )

        if arquivo_validado and arquivo_validado.exists():
            return arquivo_validado
        return arquivo_final

    def executar_fluxo_extracao(
        self,
        caminho_saida_pdf: Path,
        modo: ModoExecucao | str = ModoExecucao.AUTO,
    ) -> Tuple[PeriodoCartao, Path]:
        """Executa a sequência completa de extração no Senior Desktop."""
        periodo = self.calcular_periodo_datas(modo=modo)
        self.abrir_sistema_senior()
        self.autenticar_senior()
        self.navegar_para_cartao_ponto()
        self.selecionar_relatorio_702()
        self.preencher_datas_e_gerar(periodo.data_inicial, periodo.data_final)
        caminho_final = self.aguardar_relatorio_e_salvar(caminho_saida_pdf)
        return periodo, caminho_final
