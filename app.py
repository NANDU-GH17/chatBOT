from __future__ import annotations

import json
import os
import uuid
from typing import Dict, List

import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)

BOT_NAME = "Nova"
BOT_PERSONALITY = "friendly, helpful, and beginner-friendly"
DEFAULT_SYSTEM_PROMPT = (
    f"You are {BOT_NAME}, a {BOT_PERSONALITY} AI assistant. "
    "Explain ideas clearly, answer simply, and keep the response focused. "
    "If the user is learning, teach in an easy way and use examples when helpful."
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MAX_MESSAGE_LENGTH = 2000

chat_sessions: Dict[str, Dict[str, List[Dict[str, str]]]] = {}


def get_or_create_session(session_id: str | None = None):
    session_key = session_id or str(uuid.uuid4())
    if session_key not in chat_sessions:
        chat_sessions[session_key] = {
            "messages": [],
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
        }
    return session_key, chat_sessions[session_key]


def list_available_models() -> List[str]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "Could not connect to Ollama. Please make sure Ollama is installed and running on your computer."
        ) from exc

    models = []
    for item in payload.get("models", []):
        name = item.get("name")
        if name:
            models.append(name)
    return models


def build_ollama_messages(session: Dict[str, List[Dict[str, str]]]):
    messages = [{"role": "system", "content": session["system_prompt"]}]
    for entry in session["messages"]:
        if entry["role"] in {"user", "assistant"}:
            messages.append({"role": entry["role"], "content": entry["content"]})
    return messages


def normalize_error_message(message: str) -> str:
    if "Connection aborted" in message or "Connection refused" in message:
        return "The local Ollama service is not responding. Please check that Ollama is running."
    if "timed out" in message.lower():
        return "The model took too long to respond. Try again or use a smaller model."
    return message


@app.route("/")
def index():
    return render_template("index.html", bot_name=BOT_NAME)


@app.route("/api/config")
def config():
    return jsonify({
        "bot_name": BOT_NAME,
        "personality": BOT_PERSONALITY,
        "model": OLLAMA_MODEL,
    })


@app.route("/api/new-session", methods=["POST"])
def new_session():
    session_id, _ = get_or_create_session()
    return jsonify({"session_id": session_id})


@app.route("/api/clear-session", methods=["POST"])
def clear_session():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")

    if not session_id:
        return jsonify({"error": "Missing session_id."}), 400

    if session_id in chat_sessions:
        chat_sessions[session_id]["messages"] = []

    return jsonify({"status": "cleared", "session_id": session_id})


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    user_message = (payload.get("message") or "").strip()

    if not session_id:
        return jsonify({"error": "Missing session_id."}), 400

    if not user_message:
        return jsonify({"error": "Empty messages are not allowed."}), 400

    if len(user_message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"Message is too long. Keep it under {MAX_MESSAGE_LENGTH} characters."}), 400

    session_id, session = get_or_create_session(session_id)
    session["messages"].append({"role": "user", "content": user_message})

    try:
        available_models = list_available_models()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    if OLLAMA_MODEL not in available_models:
        return jsonify({
            "error": (
                f"Model '{OLLAMA_MODEL}' is not installed. "
                f"Run: ollama pull {OLLAMA_MODEL}"
            )
        }), 503

    request_data = {
        "model": OLLAMA_MODEL,
        "messages": build_ollama_messages(session),
        "stream": True,
    }

    def generate_response():
        partial_text = []

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=request_data,
                stream=True,
                timeout=60,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = data.get("message", {}).get("content")
                if content:
                    partial_text.append(content)
                    yield f"data: {json.dumps({'delta': content})}\n\n"

                if data.get("done"):
                    final_text = "".join(partial_text)
                    session["messages"].append({"role": "assistant", "content": final_text})
                    yield f"data: {json.dumps({'done': True, 'full_text': final_text, 'session_id': session_id})}\n\n"
                    return

        except requests.exceptions.RequestException as exc:
            error_message = normalize_error_message(str(exc))
            yield f"data: {json.dumps({'error': error_message})}\n\n"
            return
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return

        if not partial_text:
            yield f"data: {json.dumps({'error': 'The model produced no output. Please try again.'})}\n\n"

    return Response(generate_response(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
