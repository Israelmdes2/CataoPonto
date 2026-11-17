import logging
import re
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

PADRAO_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
CODIGOS_THROTTLING_TEMPORARIO = {421, 432, 451, 452}
MAX_TENTATIVAS_SMTP = 3


class EmailService:
    """Serviço responsável pelo envio de cartões de ponto via SMTP Microsoft 365."""

    _ultimo_envio_ts: float = 0.0

    @staticmethod
    def validar_formato_email(email: str) -> bool:
        """Valida o formato do e-mail antes do SMTP para evitar error throttling na Microsoft."""
        return bool(email and PADRAO_EMAIL.match(email.strip()))

    @classmethod
    def _aguardar_cadencia_microsoft(cls) -> None:
        """Aplica o intervalo configurado para permanecer abaixo do limite de 30 msg/min do Exchange Online."""
        intervalo = float(getattr(settings, "EMAIL_INTERVALO_SEGUNDOS", 10.0) or 0.0)
        if intervalo <= 0 or cls._ultimo_envio_ts <= 0:
            return

        decorrido = time.monotonic() - cls._ultimo_envio_ts
        restante = intervalo - decorrido
        if restante > 0:
            logger.info(f"Aguardando {restante:.1f}s antes do próximo envio (cadência Microsoft 365).")
            time.sleep(restante)

    @staticmethod
    def obter_conteudo_email(nome_colaborador: str, modo: str) -> tuple[str, str]:
        """Retorna assunto e corpo do e-mail conforme o modo do PDD (conferência ou fechamento)."""
        if modo == "30":
            assunto = "Espelho de Ponto – Fechamento do Período"
            corpo = f"""Prezado(a) {nome_colaborador},

Segue o espelho de ponto finalizado.

Atenciosamente,

Departamento Pessoal"""
            return assunto, corpo

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
    def _montar_mensagem(
        cls,
        destinatario: str,
        assunto: str,
        corpo: str,
        arquivo_anexo: Path,
    ) -> MIMEMultipart:
        """Constrói a mensagem MIME com o PDF individual anexado."""
        mensagem = MIMEMultipart()
        mensagem["From"] = settings.EMAIL_REMETENTE or settings.SMTP_USERNAME
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.attach(MIMEText(corpo, "plain", "utf-8"))

        with open(arquivo_anexo, "rb") as arquivo:
            anexo = MIMEApplication(arquivo.read(), Name=arquivo_anexo.name)
            anexo["Content-Disposition"] = f'attachment; filename="{arquivo_anexo.name}"'
            mensagem.attach(anexo)

        return mensagem

    @classmethod
    def enviar_cartao_ponto(
        cls,
        destinatario_email: str,
        nome_colaborador: str,
        caminho_pdf_anexo: str | Path,
        modo: str,
    ) -> bool:
        """Envia o cartão de ponto em PDF para o colaborador com cadência e retry seguro."""
        arquivo_anexo = Path(caminho_pdf_anexo)
        if not arquivo_anexo.exists():
            raise FileNotFoundError(f"Arquivo anexo não encontrado: {arquivo_anexo}")

        destinatario = (destinatario_email or "").strip()
        if settings.EMAIL_TESTE_MODO and settings.EMAIL_TESTE_DESTINO:
            logger.info(f"[MODO TESTE] Redirecionando e-mail de {destinatario} para {settings.EMAIL_TESTE_DESTINO}")
            destinatario = settings.EMAIL_TESTE_DESTINO.strip()

        if not cls.validar_formato_email(destinatario):
            raise ValueError(f"Endereço de e-mail inválido na planilha: '{destinatario}'")

        assunto, corpo = cls.obter_conteudo_email(nome_colaborador, modo)
        mensagem = cls._montar_mensagem(destinatario, assunto, corpo, arquivo_anexo)

        if not settings.SMTP_PASSWORD:
            logger.warning(
                f"[SIMULAÇÃO] SMTP_PASSWORD ausente. Envio para {destinatario} simulado ({arquivo_anexo.name})."
            )
            return True

        cls._aguardar_cadencia_microsoft()

        for tentativa in range(1, MAX_TENTATIVAS_SMTP + 1):
            try:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as servidor:
                    servidor.starttls()
                    servidor.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    servidor.send_message(mensagem)
                cls._ultimo_envio_ts = time.monotonic()
                logger.info(f"E-mail enviado para {destinatario} com anexo {arquivo_anexo.name}")
                return True
            except smtplib.SMTPResponseException as erro_smtp:
                cls._ultimo_envio_ts = time.monotonic()
                # Apenas códigos 4xx transitórios justificam nova tentativa; 5xx falham imediatamente
                if erro_smtp.smtp_code in CODIGOS_THROTTLING_TEMPORARIO and tentativa < MAX_TENTATIVAS_SMTP:
                    espera = 30 * tentativa
                    logger.warning(
                        f"Throttling Microsoft ({erro_smtp.smtp_code}) para {destinatario}. "
                        f"Aguardando {espera}s para tentativa {tentativa + 1}/{MAX_TENTATIVAS_SMTP}."
                    )
                    time.sleep(espera)
                    continue
                logger.error(f"Erro SMTP ({erro_smtp.smtp_code}) para {destinatario}: {erro_smtp}")
                raise
            except smtplib.SMTPServerDisconnected as erro_desconexao:
                cls._ultimo_envio_ts = time.monotonic()
                if tentativa < MAX_TENTATIVAS_SMTP:
                    espera = 15 * tentativa
                    logger.warning(
                        f"Desconexão SMTP para {destinatario}. Aguardando {espera}s ({tentativa + 1}/{MAX_TENTATIVAS_SMTP})."
                    )
                    time.sleep(espera)
                    continue
                logger.error(f"Desconexão SMTP persistente para {destinatario}: {erro_desconexao}")
                raise
            except Exception as erro:
                cls._ultimo_envio_ts = time.monotonic()
                logger.error(f"Falha ao enviar e-mail para {destinatario}: {erro}")
                raise

        return False
