const messagesEl = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const typingEl = document.getElementById("typing");
const stubTemplate = document.getElementById("ticket-stub-template");

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.textContent = text;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function addBotMessage(data) {
  const div = document.createElement("div");
  div.className = "msg bot";
  div.innerHTML = formatText(data.reply);
  messagesEl.appendChild(div);

  if (data.ticket_id) {
    const stub = stubTemplate.content.cloneNode(true);
    stub.querySelector(".ticket-stub-id").textContent = data.ticket_id;
    messagesEl.appendChild(stub);
  }

  if (data.sources && data.sources.length) {
    const wrap = document.createElement("div");
    wrap.className = "sources";
    if (data.mode) {
      const modeChip = document.createElement("span");
      modeChip.className = "source-chip mode-chip";
      modeChip.textContent = data.mode === "llm" ? "✦ Groq (Llama 3.3)" : "Knowledge base match";
      wrap.appendChild(modeChip);
    }
    data.sources.forEach(s => {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = `${s.category} · ${Math.round(s.score * 100)}% match`;
      wrap.appendChild(chip);
    });
    messagesEl.appendChild(wrap);
  }

  if (data.quick_replies && data.quick_replies.length) {
    const wrap = document.createElement("div");
    wrap.className = "quick-replies";
    data.quick_replies.forEach(label => {
      const btn = document.createElement("button");
      btn.className = "qr-btn";
      btn.textContent = label;
      btn.addEventListener("click", () => sendMessage(label));
      wrap.appendChild(btn);
    });
    messagesEl.appendChild(wrap);
  }

  scrollToBottom();
}

function formatText(text) {
  // minimal, safe markdown-ish formatting: **bold** only
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

async function sendMessage(text) {
  addUserMessage(text);
  input.value = "";
  typingEl.hidden = false;
  scrollToBottom();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typingEl.hidden = true;
    addBotMessage(data);
  } catch (err) {
    typingEl.hidden = true;
    addBotMessage({ reply: "Sorry, I couldn't reach the server. Please try again." });
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  sendMessage(text);
});

document.querySelectorAll(".qa-btn").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.msg));
});

// Greet on load
window.addEventListener("DOMContentLoaded", () => {
  addBotMessage({
    reply: "Namaste! I'm the GBU Grievance Assistant. I can help you submit a grievance, track an existing ticket, or answer questions about the process.",
    quick_replies: ["Submit a grievance", "Track my ticket", "What categories can I file?"],
  });
});
