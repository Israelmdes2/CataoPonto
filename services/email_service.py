import logging
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

_EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_CODIGOS_THROTTLING_TEMP = {421, 432, 451, 452}


class EmailService:
    _ultimo_envio_ts: float = 0.0

    @staticmethod
    def validar_formato_email(email: str) -> bool:
        """Valida formato básico de e-mail antes de acionar o SMTP (evita error throttling na Microsoft)."""
        return bool(email and _EMAIL_REGEX.match(email.strip()))

    @classmethod
    def _aguardar_cadencia_microsoft(cls) -> None:
        """
        Garante o intervalo mínimo configurado (padrão 10s = máx 6 e-mails/min)
        para permanecer bem abaixo do limite de 30 msg/min do Microsoft 365.
        """
        intervalo = float(getattr(settings, "EMAIL_INTERVALO_SEGUNDOS", 10.0) or 0.0)
        if intervalo <= 0 or cls._ultimo_envio_ts <= 0:
            return

        decorrido = time.monotonic() - cls._ultimo_envio_ts
        restante = intervalo - decorrido
        if restante > 0:
            logger.info(f"Aguardando {restante:.1f}s antes do próximo envio (cadência anti-bloqueio Microsoft 365)...")
            time.sleep(restante)

    @staticmethod
    def obter_conteudo_email(nome_colaborador: str, modo: str) -> tuple[str, str]:
        """
        Gera o assunto e corpo do e-mail estritamente de acordo com as regras do PDD.
        - Dias 20 e 04: Conferência das marcações
        - Dia 30: Fechamento do período
        """
        if modo == "30":
            assunto = "Espelho de Ponto – Fechamento do Período"
            corpo = f"""Prezado(a) {nome_colaborador},

Segue o espelho de ponto finalizado.

Atenciosamente,

Departamento Pessoal"""
        else:
            assunto = "Espelho de Ponto – Conferência das Marcações"
            corpo = f"""Prezado(a) {nome_colaborador},

Você está recebendo o espelho de ponto para conferência das marcações realizadas no período.
Pedimos que confira os registros e, caso identifique alguma divergência ou necessidade de ajuste, solicite imediatamente a correção ao seu gestor, para que os ajustes sejam realizados dentro do prazo e não haja impacto no processamento da folha de pagamento.

Atenção: este espelho de ponto ainda não está finalizado e é destinado exclusivamente à conferência das marcações.

Contamos com sua colaboração!

Atenciosamente,

Departamento Pessoal"""

        return assunto, corpo

    @classmethod
    def enviar_cartao_ponto(
        cls,
        destinatario_email: str,
        nome_colaborador: str,
        caminho_pdf_anexo: str | Path,
        modo: str,
    ) -> bool:
        """
        Envia o e-mail com o cartão ponto anexado para o colaborador,
        respeitando cadência anti-bloqueio (10s) e retry seguro para throttling 4xx do Exchange Online.
        """
        arquivo_anexo = Path(caminho_pdf_anexo)
        if not arquivo_anexo.exists():
            raise FileNotFoundError(f"Arquivo anexo não encontrado: {arquivo_anexo}")

        # Destinatário real ou teste
        email_to = (destinatario_email or "").strip()
        if settings.EMAIL_TESTE_MODO and settings.EMAIL_TESTE_DESTINO:
            logger.info(f"[MODO TESTE] Redirecionando e-mail de {email_to} para {settings.EMAIL_TESTE_DESTINO}")
            email_to = settings.EMAIL_TESTE_DESTINO.strip()

        if not cls.validar_formato_email(email_to):
            raise ValueError(f"Endereço de e-mail inválido na planilha (bloqueado antes do SMTP): '{email_to}'")

        assunto, corpo = cls.obter_conteudo_email(nome_colaborador, modo)

        # Montagem da mensagem MIME
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_REMETENTE or settings.SMTP_USERNAME
        msg["To"] = email_to
        msg["Subject"] = assunto

        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with open(arquivo_anexo, "rb") as f:
            part = MIMEApplication(f.read(), Name=arquivo_anexo.name)
            part["Content-Disposition"] = f'attachment; filename="{arquivo_anexo.name}"'
            msg.attach(part)

        # Se não houver senha SMTP configurada (ambiente de dev/mock), apenas simula com sucesso
        if not settings.SMTP_PASSWORD:
            logger.warning(
                f"[SIMULAÇÃO] SMTP_PASSWORD não definido. E-mail para {email_to} simulado com sucesso. Anexo: {arquivo_anexo.name}"
            )
            return True

        # Aplica cadência configurada (ex: 10s entre envios) antes de conectar ao SMTP
        cls._aguardar_cadencia_microsoft()

        # Envio real via SMTP com retry controlado apenas para throttling transitório (4xx)
        max_tentativas = 3
        for tentativa in range(1, max_tentativas + 1):
            try:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                    server.starttls()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)
                cls._ultimo_envio_ts = time.monotonic()
                logger.info(f"E-mail enviado com sucesso para {email_to} com anexo {arquivo_anexo.name}")
                return True
            except smtplib.SMTPResponseException as smtp_ex:
                cls._ultimo_envio_ts = time.monotonic()
                if smtp_ex.smtp_code in _CODIGOS_THROTTLING_TEMP and tentativa < max_tentativas:
                    espera = 30 * tentativa
                    logger.warning(
                        f"Throttling temporário Microsoft (código {smtp_ex.smtp_code}) ao enviar para {email_to}. "
                        f"Aguardando {espera}s para tentativa {tentativa + 1}/{max_tentativas}..."
                    )
                    time.sleep(espera)
                    continue
                logger.error(f"Erro SMTP ({smtp_ex.smtp_code}) ao enviar e-mail para {email_to}: {smtp_ex}")
                raise
            except smtplib.SMTPServerDisconnected as disc_ex:
                cls._ultimo_envio_ts = time.monotonic()
                if tentativa < max_tentativas:
                    espera = 15 * tentativa
                    logger.warning(
                        f"Conexão SMTP encerrada pelo servidor ao enviar para {email_to}. "
                        f"Aguardando {espera}s para tentativa {tentativa + 1}/{max_tentativas}..."
                    )
                    time.sleep(espera)
                    continue
                logger.error(f"Desconexão SMTP persistente ao enviar para {email_to}: {disc_ex}")
                raise
            except Exception as e:
                cls._ultimo_envio_ts = time.monotonic()
                logger.error(f"Falha ao enviar e-mail para {email_to}: {e}")
                raise

        return False
