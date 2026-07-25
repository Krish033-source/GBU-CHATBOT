import re
from rag_engine import Retriever, generate_answer, extract_ticket_id
import database

CATEGORIES = ["Academic", "Examination", "Hostel", "Fee", "Infrastructure", "IT/Portal"]
_sessions = {}

_retriever = Retriever()

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[a-zA-Z]+")

def _new_state():
    return {"flow": None, "step": None, "slots": {}}

def get_state(session_id):
    return _sessions.setdefault(session_id, _new_state())

def reset_state(session_id):
    _sessions[session_id] = _new_state()

GREETINGS = {"hi", "hello", "hey", "namaste", "hii", "helo", "good morning", "good evening"}
GOODBYES = {"bye", "goodbye", "thanks", "thank you", "ok thanks", "see you"}
SUBMIT_TRIGGERS = ["submit", "file a grievance", "raise a", "i have a complaint",
                    "i want to complain", "register a grievance", "new grievance", "lodge"]
TRACK_TRIGGERS = ["track", "status", "where is my", "check my ticket", "check ticket"]
IDENTITY_TRIGGERS = [
    "who are you", "what are you", "are you a bot", "are you a human",
    "are you ai", "are you an ai", "what is this", "what is this bot",
    "tell me about yourself", "what can you do", "who made you",
    "who created you", "who built you", "your name",
]
CANCEL_TRIGGERS = ["cancel", "stop", "never mind", "nevermind", "restart"]

QUESTION_PATTERN = re.compile(
    r"^\s*(what|which|how|why|when|where|who|is|are|do|does|will|can)\b", re.I
)

def detect_intent(message: str, state: dict) -> str:
    text = message.lower().strip()

    if text in CANCEL_TRIGGERS or "cancel" in text:
        return "cancel"
    if state["flow"] is not None:
        return "continue_flow"
    if text in GREETINGS or any(text.startswith(g) for g in GREETINGS):
        return "greeting"
    if text in GOODBYES:
        return "goodbye"

    has_ticket_id = bool(extract_ticket_id(message))
    is_question = bool(QUESTION_PATTERN.match(text))

    if has_ticket_id or (not is_question and any(t in text for t in TRACK_TRIGGERS)):
        return "track_status"
    if not is_question and any(t in text for t in SUBMIT_TRIGGERS):
        return "submit_grievance"
    return "faq"

def handle_message(session_id: str, message: str) -> dict:
    state = get_state(session_id)
    intent = detect_intent(message, state)

    if intent == "cancel":
        reset_state(session_id)
        return _reply("No problem, I've cancelled that. How else can I help — "
                       "submit a grievance, track a ticket, or ask a question?")

    if intent == "greeting":
        return _reply("Namaste! I'm the GBU Grievance Assistant. I can help you "
                       "submit a grievance, track an existing ticket by ID, or "
                       "answer questions about the process. What would you like to do?",
                       quick_replies=["Submit a grievance", "Track my ticket", "How does this work?"])

    if intent == "goodbye":
        reset_state(session_id)
        return _reply("You're welcome! Feel free to come back anytime you need help "
                       "with a grievance. Take care.")

    if intent == "track_status":
        return _handle_track(message)

    if intent == "submit_grievance":
        state["flow"] = "submit"
        state["step"] = "category"
        state["slots"] = {}
        return _reply(
            "Sure, let's get your grievance logged. First, which category does it fall under?",
            quick_replies=CATEGORIES,
        )

    if intent == "continue_flow" and state["flow"] == "submit":
        return _handle_submit_flow(session_id, state, message)

    retrieved = _retriever.retrieve(message)
    result = generate_answer(message, retrieved)
    return _reply(result["answer"], sources=result["sources"], mode=result.get("mode"))

def _handle_track(message: str) -> dict:
    ticket_id = extract_ticket_id(message)
    if not ticket_id:
        return _reply("Sure — what's your Ticket ID? It looks like GBU-2026-00123.")
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return _reply(f"I couldn't find a ticket with ID {ticket_id}. "
                       "Please double check the ID, or contact the IT Cell if you believe this is an error.")
    return _reply(
        f"Ticket {ticket['ticket_id']} — Status: **{ticket['status']}**\n"
        f"Category: {ticket['category']}\n"
        f"Submitted: {ticket['created_at']}\n"
        f"Last updated: {ticket['updated_at']}"
    )


def _handle_submit_flow(session_id: str, state: dict, message: str) -> dict:
    step = state["step"]
    text = message.strip()

    if step == "category":
        matched = next((c for c in CATEGORIES if c.lower() in text.lower()), None)
        if not matched:
            return _reply("Please pick one of the listed categories.", quick_replies=CATEGORIES)
        state["slots"]["category"] = matched
        state["step"] = "description"
        return _reply(f"Got it — {matched}. Now, briefly describe the issue.")

    if step == "description":
        if len(text) < 5:
            return _reply("Could you add a little more detail about the issue?")
        state["slots"]["description"] = text
        state["step"] = "name"
        return _reply("Thanks. What's your full name?")

    if step == "name":
        state["slots"]["name"] = text
        state["step"] = "email"
        return _reply("And your GBU registered email address?")

    if step == "email":
        if not EMAIL_RE.match(text):
            return _reply("That doesn't look like a valid email. Please enter your GBU email address.")
        state["slots"]["email"] = text
        ticket_id = database.create_ticket(
            name=state["slots"]["name"],
            email=state["slots"]["email"],
            category=state["slots"]["category"],
            description=state["slots"]["description"],
        )
        reset_state(session_id)
        return _reply(
            f"Your grievance has been submitted successfully.\n\n"
            f"**Ticket ID: {ticket_id}**\n\n"
            f"A confirmation email has been sent to your registered address. "
            f"Save this Ticket ID to track status anytime — just paste it here.",
            ticket_id=ticket_id,
        )

    reset_state(session_id)
    return _reply("Something went off track — let's start over. How can I help?")

def _reply(text, quick_replies=None, sources=None, ticket_id=None, mode=None):
    payload = {"reply": text}
    if quick_replies:
        payload["quick_replies"] = quick_replies
    if sources:
        payload["sources"] = sources
    if ticket_id:
        payload["ticket_id"] = ticket_id
    if mode:
        payload["mode"] = mode
    return payload
