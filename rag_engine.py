"""
RAG Mechanism:
The Retrieval-Augmented Generation core for the GBU Grievance Assistant.

RETRIEVAL:
    Knowledge base entries (question + answer + keywords) are vectorized with
    TF-IDF. A user query is vectorized with the same fitted vectorizer and
    compared against every KB entry using cosine similarity. The top-k most
    relevant entries are returned as "retrieved context".

    TF-IDF is used instead of a hosted embeddings API because it runs fully
    offline, is deterministic, and is easy to explain/defend in a screening
    interview -- important qualities for a transparent grievance system.
    The retriever is written as its own class (`Retriever`) so it can be
    swapped for a sentence-embedding model (e.g. `all-MiniLM-L6-v2` via
    sentence-transformers) later without touching the rest of the app.

GENERATION:
    `generate_answer()` implements the "G" in RAG: it takes the retrieved
    KB entries and synthesizes a single grounded response, citing which
    KB category it drew from. This keeps answers verifiable -- the bot
    never invents policy that isn't in the knowledge base.

    A `USE_LLM` flag shows where this would be swapped for a call to an LLM
    (e.g. the Anthropic API) that receives the retrieved passages as context
    and produces a more natural free-form answer. That path is documented in
    README.md; the offline template-based generator below is the default so
    the prototype runs without any API key or internet access.
"""
import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
KB_PATH = os.path.join(os.path.dirname(__file__), "data", "knowledge_base.json")

SIMILARITY_THRESHOLD = 0.12

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are the GBU Grievance Assistant, a helpful, concise assistant for
Gautam Buddha University's Grievance Management System. Prefer the CONTEXT
provided below for anything related to grievance policy, categories, timelines,
or procedures -- never invent policy, timelines, or procedures that are not in
the context. If the CONTEXT is empty or doesn't cover the question, you may
answer general questions about Gautam Buddha University (GBU), Greater Noida
using your own knowledge, but stay factual and say you're not sure rather than
guessing. For anything unrelated to GBU or grievances, say it's outside what
you can help with and suggest contacting the IT Cell / Grievance Redressal
Committee. Keep answers under 4 sentences unless the user asks for detail.
Do not repeat the user's question back to them."""

def _groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        return None

def call_llm(query: str, retrieved: list):
    client = _groq_client()
    if client is None:
        return None

    context = "\n\n".join(
        f"[{i+1}] ({r['category']}) {r['answer']}" for i, r in enumerate(retrieved)
    )

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER QUESTION:\n{query}"},
            ],
            temperature=0.3,
            max_tokens=250,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None

USE_LLM = os.environ.get("GROQ_API_KEY") is not None

class Retriever:
    def __init__(self, kb_path: str = KB_PATH):
        with open(kb_path, "r", encoding="utf-8") as f:
            self.kb = json.load(f)

        self.corpus = [
            (entry["question"] + " ") * 3
            + " ".join(entry["keywords"]) * 2
            + " " + entry["answer"]
            for entry in self.kb
        ]

        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.doc_matrix = self.vectorizer.fit_transform(self.corpus)

    def retrieve(self, query: str, top_k: int = 3):
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.doc_matrix).flatten()

        ranked = sorted(
            zip(range(len(self.kb)), scores), key=lambda x: x[1], reverse=True
        )

        results = []
        for idx, score in ranked[:top_k]:
            if score >= SIMILARITY_THRESHOLD:
                entry = dict(self.kb[idx])
                entry["score"] = round(float(score), 3)
                results.append(entry)
        return results

def generate_answer(query: str, retrieved: list) -> dict:
    llm_answer = call_llm(query, retrieved) if USE_LLM else None

    if llm_answer:
        answer = llm_answer
    elif retrieved:
        best = retrieved[0]
        answer = best["answer"]
        if len(retrieved) > 1 and retrieved[1]["score"] >= SIMILARITY_THRESHOLD:
            answer += f"\n\nRelated: {retrieved[1]['answer']}"
    else:
        answer = (
            "I couldn't find a confident answer to that in the grievance "
            "knowledge base. You can rephrase your question, or contact "
            "the IT Cell / Grievance Redressal Committee directly for help."
        )

    return {
        "answer": answer,
        "sources": [{"category": r["category"], "question": r["question"], "score": r["score"]} for r in retrieved],
        "mode": "llm" if llm_answer else "template",
    }

TICKET_ID_PATTERN = re.compile(r"GBU-\d{4}-\d{4,6}", re.IGNORECASE)

def extract_ticket_id(text: str):
    match = TICKET_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None
