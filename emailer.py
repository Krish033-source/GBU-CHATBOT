"""
emailer.py
-----------
Sends the mandatory "Grievance Submitted" / "Status Updated" email
notifications over real SMTP.

Configured entirely via environment variables so no credentials ever need to
be committed to source control:

    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       e.g. 587
    SMTP_USER       the sending mailbox address
    SMTP_PASSWORD   an app password (NOT your normal account password --
                     Gmail/Outlook require a generated "app password" for
                     SMTP login when 2FA is on)
    FROM_NAME       display name, defaults to "GBU Grievance Cell"

If these aren't set, `send_email()` returns False and the caller (database.py)
simply logs the notification instead of sending it -- so the whole app keeps
working out of the box for local demoing/screening, and starts sending real
mail the moment credentials are added.
"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_NAME = os.environ.get("FROM_NAME", "GBU Grievance Cell")

IS_CONFIGURED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


TEMPLATES = {
    "Grievance Submitted": {
        "subject": "Your GBU grievance has been received — {ticket_id}",
        "body": (
            "Hi {name},\n\n"
            "Your grievance has been submitted successfully.\n\n"
            "Ticket ID: {ticket_id}\n"
            "Category: {category}\n"
            "Status: Pending\n\n"
            "You can track progress anytime by giving this Ticket ID to the "
            "GBU Grievance Assistant chatbot.\n\n"
            "— GBU IT Cell / Grievance Redressal Committee"
        ),
    },
    "Status Updated": {
        "subject": "Update on your GBU grievance — {ticket_id}",
        "body": (
            "Hi {name},\n\n"
            "The status of your grievance has changed.\n\n"
            "Ticket ID: {ticket_id}\n"
            "New Status: {status}\n\n"
            "— GBU IT Cell / Grievance Redressal Committee"
        ),
    },
}


def send_email(event: str, to_email: str, **fields) -> bool:
    """
    Sends a notification email for `event` ("Grievance Submitted" or a
    "Status Updated: <status>" style event). Returns True if actually sent,
    False if SMTP isn't configured or the send failed (caller should treat
    False as "logged only, not delivered" rather than raise -- a missing
    mail server should never break the grievance flow itself).
    """
    base_event = "Status Updated" if event.startswith("Status Updated") else event
    template = TEMPLATES.get(base_event)
    if not template or not IS_CONFIGURED:
        return False

    try:
        subject = template["subject"].format(**fields)
        body = template["body"].format(**fields)

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except Exception:
        # Bad credentials, network issue, etc. -- don't let email failures
        # block ticket creation/status updates.
        return False
