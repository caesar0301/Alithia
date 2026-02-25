"""
Email construction and delivery utilities.
"""

import smtplib
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr

from noesium.core.utils import get_logger

logger = get_logger(__name__)


def send_email(
    sender: str, receiver: str, password: str, smtp_server: str, smtp_port: int, html_content: str, subject: str = None
) -> bool:
    """
    Send email via SMTP.

    Args:
        sender: Sender email address
        receiver: Receiver email address
        password: Sender email password
        smtp_server: SMTP server address
        smtp_port: SMTP server port
        html_content: HTML content to send
        subject: Email subject (optional, defaults to "Alithia Digest {date}")

    Returns:
        True if email sent successfully, False otherwise
    """
    if sender == "" or receiver == "" or password == "" or smtp_server == "" or smtp_port == 0:
        logger.error("Email configuration is incomplete or invalid")
        return False

    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, "utf-8").encode(), addr))

    msg = MIMEText(html_content, "html", "utf-8")
    msg["From"] = _format_addr(f"Github Action <{sender}>")
    msg["To"] = _format_addr(f"You <{receiver}>")

    if subject is None:
        today = datetime.now().strftime("%Y/%m/%d")
        subject = f"Alithia Digest {today}"

    msg["Subject"] = Header(subject, "utf-8").encode()

    server = None
    try:
        logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port} (TLS)...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
        logger.info("Connected successfully with TLS")
    except Exception as e:
        logger.warning(f"TLS connection failed: {e}, trying SSL...")
        if server:
            try:
                server.quit()
            except:
                pass
        try:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
            server.ehlo()
            logger.info("Connected successfully with SSL")
        except Exception as ssl_error:
            logger.error(f"Failed to connect to SMTP server: TLS error: {e}, SSL error: {ssl_error}")
            return False

    try:
        logger.info(f"Logging in as {sender}...")
        server.login(sender, password)
        logger.info("Login successful")

        logger.info(f"Sending email to {receiver} with subject: {subject}")
        server.sendmail(sender, [receiver], msg.as_string())
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False
    finally:
        if server:
            try:
                server.quit()
            except:
                pass
