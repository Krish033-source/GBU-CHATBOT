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
        return False
