import os
import requests

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
FROM_NAME = os.environ.get("FROM_NAME", "GBU Grievance Cell")

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

IS_CONFIGURED = bool(BREVO_API_KEY and BREVO_SENDER_EMAIL)

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

        payload = {
            "sender": {"name": FROM_NAME, "email": BREVO_SENDER_EMAIL},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body,
        }
        headers = {
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        resp = requests.post(BREVO_ENDPOINT, json=payload, headers=headers, timeout=10)
        return resp.status_code in (200, 201)
    except Exception:
        return False
