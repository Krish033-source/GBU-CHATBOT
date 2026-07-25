# GBU Grievance Assistant — AI Chatbot (RAG-based)

**Role:** AI Chatbot Development & Deployment
**Screening Challenge:** GBU IT Cell Intern Recruitment
**Stack:** Python (Flask), scikit-learn (TF-IDF retrieval), SQLite, HTML/CSS/JS

---

🔗** Live Link:** https://gbu-chatbot.onrender.com/

## 1. Objective

An AI-powered assistant embedded in the GBU Grievance Management & Ticket Tracking
System that can:

- Assist students in **submitting a grievance** through natural conversation
- Let students **track grievance status** using their Ticket ID
- **Answer grievance-related FAQs**, grounded in an actual knowledge base (not hallucinated)
- **Guide users** through the overall grievance process

The design goal was a bot that a real Grievance Cell could trust: every FAQ answer is
traceable back to a specific knowledge-base entry, and every "submit" or "track"
action is backed by a real, queryable ticket record — not a scripted demo.

---

## 2. Chatbot Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER (HTML/CSS/JS)                   │
│   Chat UI  ── quick replies ── ticket-stub card ── source chips │
└───────────────────────────────┬───────────────────────────────┘
                                 │ POST /api/chat  { message }
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FLASK APPLICATION (app.py)                │
│   session_id (per browser) ─────────────────────────────────┐   │
└───────────────────────────────┬─────────────────────────────┼──┘
                                 ▼                              │
┌─────────────────────────────────────────────────────────────┼──┐
│               chatbot.py — Conversation Manager               │  │
│                                                                 │  │
│   1. Intent Detection (rules over the message + session state) │  │
│        greeting | goodbye | submit_grievance | track_status    │  │
│        | continue_flow | faq                                   │  │
│                                                                 │  │
│   2. Slot-filling state machine (for submit_grievance)         │  │
│        category → description → name → email → create ticket  │  │
│                                                                 │  │
│   3. Delegates to:                                              │  │
└───────────┬───────────────────────────────┬───────────────────┘  │
            ▼                               ▼                       │
┌────────────────────────┐    ┌──────────────────────────────┐      │
│   rag_engine.py         │    │   database.py (SQLite)       │      │
│   ┌───────────────────┐ │    │  tickets(ticket_id, name,    │      │
│   │ Retriever          │ │    │   email, category,          │◄─────┘
│   │  TF-IDF vectorizer │ │    │   description, status,      │
│   │  cosine similarity │ │    │   created_at, updated_at)    │
│   │  top-k + threshold  │ │    │  notifications(ticket_id,    │
│   └─────────┬───────────┘ │    │   email, event, sent_at)     │
│             ▼               │    └──────────────────────────────┘
│   generate_answer()        │
│    synthesizes grounded     │
│    reply + cites KB source  │
└──────────────┬─────────────┘
               ▼
   data/knowledge_base.json
   (15 curated grievance-policy entries)
```

**Why TF-IDF instead of a hosted embeddings API for retrieval?** It runs fully
offline and deterministically, needs no API key, and is trivial to audit — every
retrieval score is explainable. The retriever is isolated in its own `Retriever`
class specifically so it can be swapped for sentence-embeddings (e.g.
`sentence-transformers/all-MiniLM-L6-v2`) in production without touching the
conversation manager.

**Generation now uses a real LLM: Groq (Llama 3.3 70B).** `rag_engine.py::call_llm()`
sends the top retrieved KB passages plus the user's question to Groq's chat
completions endpoint. This is a genuine RAG generation step, not a mock — the
model is instructed (via the system prompt in §4) to answer *only* from the
provided context, which is what keeps it grounded instead of free-hallucinating
grievance policy. If `GROQ_API_KEY` isn't set, or the API call fails for any
reason (rate limit, network, bad key), the app automatically falls back to the
deterministic template generator — the chatbot never goes down because of the
LLM provider, it just gets slightly less fluent. Set the key with:

```bash
export GROQ_API_KEY="your-key-here"    # get one free at console.groq.com
pip install -r requirements.txt         # now includes the groq SDK
python app.py
```

**Email notifications now send real mail via SMTP.** `emailer.py` sends the
"Grievance Submitted" and "Status Updated" emails using `smtplib`, configured
via environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`). For Gmail, generate an **App Password** (Google Account →
Security → 2-Step Verification → App Passwords) rather than using your normal
password. Example:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your.address@gmail.com"
export SMTP_PASSWORD="16-char app password"
```

If these aren't set, `database.py` still records every notification attempt in
the `notifications` table (with `delivered=0`) so the requirement is visibly
wired end-to-end, it just won't leave the server — this keeps the demo
runnable with zero setup while making the production path a 4-line `.env`
away.

---

## 3. Conversation Flow

```
                         ┌───────────┐
                         │   Start    │
                         └─────┬─────┘
                               ▼
                     ┌───────────────────┐
                     │  Detect intent      │
                     └─────────┬───────────┘
        ┌───────────┬──────────┼───────────────┬───────────────┐
        ▼           ▼          ▼               ▼               ▼
   [greeting]   [goodbye]  [track_status]  [submit_grievance]  [faq / other]
        │           │          │               │               │
        ▼           ▼          ▼               ▼               ▼
   Show menu    Close out   Has Ticket ID?   Ask category   RAG retrieve
   + quick                  ┌─────┴─────┐        │          top-k KB
   replies                  yes         no        ▼          entries
                             │           │    Ask description     │
                             ▼           ▼        │               ▼
                        Look up DB   Ask for ID    ▼         score ≥
                             │           │     Ask name      threshold?
                             ▼           │        │          ┌───┴───┐
                       Reply status      │        ▼         yes     no
                                         │    Ask email       │       │
                                         │        │           ▼       ▼
                                         │        ▼      Grounded   "I don't know,
                                         │   Create ticket  answer   contact IT Cell"
                                         │   (DB + email      +
                                         │    notification)  source
                                         │        │          chips
                                         │        ▼
                                         │   Show Ticket ID
                                         │   (ticket-stub UI)
                                         └────────┴──────────────► back to
                                                                    "Detect intent"
                                                                    for next message
```

Every branch loops back to intent detection, so a user can interrupt a submission
flow at any time by typing "cancel", or ask an unrelated FAQ mid-flow and the bot
resumes gracefully (handled by the `flow`/`step` fields in the per-session state
dict — see `chatbot.py::_sessions`).

---

## 4. Prompt Design

Generation is handled by Groq (Llama 3.3 70B) when `GROQ_API_KEY` is set — this
is the exact system prompt sent in `rag_engine.py::SYSTEM_PROMPT`, with the
retrieved KB passages injected as context per-request:

```
SYSTEM:
You are the GBU Grievance Assistant, a helpful, concise assistant for
Gautam Buddha University's Grievance Management System. Answer only using
the CONTEXT provided below. If the context does not contain the answer,
say you don't know and suggest contacting the IT Cell / Grievance
Redressal Committee. Never invent policy, timelines, or procedures that
are not in the context. Keep answers under 4 sentences unless the user
asks for detail. Do not repeat the user's question back to them.

CONTEXT:
[1] (Timelines) Most grievances are acknowledged within 24-48 hours and
    resolved within 7 working days...
[2] (Notifications) The system sends a mandatory email notification...

USER QUESTION:
{{ user_message }}
```

When no key is configured (or the call fails), `generate_answer()` falls back
to returning the best-matching KB answer verbatim plus a related follow-up —
the same context-only, no-hallucination guarantee, just without LLM phrasing.
The response payload includes a `mode` field (`"llm"` or `"template"`) so this
is visible/debuggable rather than silent.

Key design choices:
- **Context-only answering** ("answer only using CONTEXT") is the anti-hallucination
  guardrail — the same principle the offline generator enforces via the similarity
  threshold and the "I don't know" fallback.
- **Explicit escalation instruction** so the bot never leaves a student stuck.
- **Short-answer default** keeps the chat usable on mobile.

For the structured sub-flows (submit / track), the "prompt" is really the slot list
itself: `category → description → name → email`, each with its own validation
(e.g. email regex) before advancing — this is deliberately a deterministic state
machine rather than an LLM free-for-all, because ticket data needs to be reliable,
not just plausible-sounding.

---

## 5. Knowledge Base Structure

`data/knowledge_base.json` — an array of entries:

```json
{
  "id": "kb006",
  "category": "Timelines",
  "question": "How long does it take to resolve a grievance?",
  "answer": "Most grievances are acknowledged within 24-48 hours...",
  "keywords": ["how long", "resolution time", "turnaround", "sla"]
}
```

15 entries across 8 categories: Getting Started, Ticket ID, Tracking, Timelines,
Notifications, Categories, Escalation, Editing, Privacy, Account, Support,
Technical, Fee. `question` and `keywords` are weighted 3x/2x over `answer` in the
TF-IDF corpus (see `Retriever.__init__`) since real user queries resemble questions
and keywords far more than they resemble finished answers. Adding a new FAQ is a
one-entry JSON edit — no retraining or redeployment logic needed.

---

## 6. Project Structure

```
gbu-chatbot/
├── app.py                  Flask routes (chat API, admin demo view)
├── chatbot.py               Conversation manager: intents, slot-filling
├── rag_engine.py             Retriever (TF-IDF) + generate_answer() + Groq call
├── emailer.py                  Real SMTP email sending (Grievance/Status mails)
├── database.py                   SQLite: tickets + notifications
├── data/
│   └── knowledge_base.json      RAG knowledge base (15 entries)
├── templates/
│   ├── index.html                 Chat UI
│   └── admin.html                  Demo admin view (status updates)
├── static/
│   ├── style.css                    GBU-branded styling
│   └── script.js                     Chat interactivity
└── requirements.txt
```

---

## 7. Running the Prototype

```bash
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** for the chat assistant, and
**http://127.0.0.1:5000/admin** to see submitted tickets and simulate an admin
updating status (this is what triggers the "Status Updated" notification the bot
reports when a student tracks their ticket afterward).

No API keys or internet access are required to run this prototype end-to-end —
Groq and SMTP are both optional, auto-detected via environment variables (see
§2 for exact `export` commands), and the bot degrades gracefully to offline
templates / log-only notifications when they're absent.

---

## 8. What Would Change for Production

- Swap `Retriever` for sentence embeddings + a vector index (FAISS/pgvector) once
  the KB grows beyond a few hundred entries.
- Replace the in-memory `_sessions` dict with Redis so the bot works across
  multiple server workers.
- Move SMTP credentials and `GROQ_API_KEY` into a proper secrets manager rather
  than plain environment variables once this leaves local/demo use.
- Add authentication so `session_id` maps to a verified GBU student identity
  instead of an anonymous browser session.
- Add retry/backoff around the Groq call and basic per-session rate limiting.

---

## 9. Evaluation Criteria Self-Check

| Criteria | How this prototype addresses it |
|---|---|
| Problem Understanding | Bot covers all 4 required capabilities: submit, track, FAQ, guidance |
| Creativity & Innovation | Ticket-stub UI motif, source-citation chips for RAG transparency, graceful mid-flow interruption |
| Technical Approach | Real RAG pipeline (retrieval + grounded generation), real DB-backed tickets, clean separation of concerns |
| Documentation Quality | This document — architecture, flow, prompt design, KB structure |
| Practical Feasibility | Runs with zero external dependencies/API keys; clear upgrade path to production |
