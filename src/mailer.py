"""Envio do e-mail diário via SMTP (Gmail + senha de app).

Variáveis de ambiente esperadas (ver .env.example):
  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 465)
  SMTP_USER, SMTP_PASSWORD (senha de app, não a senha normal da conta)
  EMAIL_TO (default = SMTP_USER)
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def send_daily_summary(
    subject: str, html_body: str, csv_attachment: str | None = None, csv_filename: str | None = None
) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("EMAIL_TO", user)

    if not user or not password:
        raise RuntimeError(
            "SMTP_USER/SMTP_PASSWORD não configurados. Veja o SETUP.md para gerar uma "
            "senha de app do Gmail e preencher o .env."
        )

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if csv_attachment:
        attachment = MIMEApplication(csv_attachment.encode("utf-8"), _subtype="csv")
        attachment.add_header("Content-Disposition", "attachment", filename=csv_filename or "vagas.csv")
        msg.attach(attachment)

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())

    log.info("E-mail enviado para %s.", to_addr)
