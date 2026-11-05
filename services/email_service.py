import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def obter_conteudo_email(nome_colaborador: str, modo: str) -> tuple[str, str]:
        """
        Gera o assunto e corpo do e-mail estritamente de acordo com as regras do PDD.
        - Dias 20 e 04: Conferência das marcações
        - Dia 30: Fechamento do período
        """
        # Se o modo for "30"
        if modo == "30":
            assunto = "Espelho de Ponto – Fechamento do Período"
            corpo = f"""Prezado(a) {nome_colaborador},

Segue o espelho de ponto finalizado.

Atenciosamente,

Departamento Pessoal"""
        else:
            # Modo "20" ou "04"
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
        Envia o e-mail com o cartão ponto anexado para o colaborador.
        """
        arquivo_anexo = Path(caminho_pdf_anexo)
        if not arquivo_anexo.exists():
            raise FileNotFoundError(f"Arquivo anexo não encontrado: {arquivo_anexo}")

        assunto, corpo = cls.obter_conteudo_email(nome_colaborador, modo)

        # Destinatário real ou teste
        email_to = destinatario_email
        if settings.EMAIL_TESTE_MODO and settings.EMAIL_TESTE_DESTINO:
            logger.info(f"[MODO TESTE] Redirecionando e-mail de {email_to} para {settings.EMAIL_TESTE_DESTINO}")
            email_to = settings.EMAIL_TESTE_DESTINO

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

        # Envio real via SMTP
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"E-mail enviado com sucesso para {email_to} com anexo {arquivo_anexo.name}")
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar e-mail para {email_to}: {e}")
            raise

