import os
import uuid
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template, session

import chatbot
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gbu-it-cell-screening-prototype")

database.init_db()

@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    session_id = session.get("session_id") or data.get("session_id") or "anon"

    if not message:
        return jsonify({"reply": "Please type a message."}), 400

    result = chatbot.handle_message(session_id, message)
    return jsonify(result)

@app.route("/api/ticket/<ticket_id>")
def api_ticket(ticket_id):
    ticket = database.get_ticket(ticket_id)
    if not ticket:
        return jsonify({"error": "not_found"}), 404
    return jsonify(ticket)

@app.route("/admin")
def admin():
    conn = database.get_connection()
    tickets = [dict(r) for r in conn.execute(
        "SELECT * FROM tickets ORDER BY created_at DESC"
    ).fetchall()]
    conn.close()

    stats = {"Pending": 0, "In Progress": 0, "Resolved": 0}
    for t in tickets:
        if t["status"] in stats:
            stats[t["status"]] += 1

    return render_template("admin.html", tickets=tickets, stats=stats, total=len(tickets))

@app.route("/admin/status", methods=["POST"])
def admin_status():
    ticket_id = request.form.get("ticket_id")
    status = request.form.get("status")
    if ticket_id and status:
        database.update_status(ticket_id, status)
    return admin()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", debug=debug, port=port)
