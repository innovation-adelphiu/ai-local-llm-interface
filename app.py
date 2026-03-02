import os
import webbrowser

from flask import Flask, render_template, request, Response
import subprocess
import requests
import json

app = Flask(__name__)

# Now stores structured chat messages
chat_history = []


def get_models():
    """Get installed Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split("\n")[1:]
        return [line.split()[0] for line in lines if line]
    except:
        return ["llama3.1"]


@app.route("/")
def index():
    return render_template(
        "chat.html",
        history=chat_history,
        models=get_models()
    )


@app.route("/stream", methods=["POST"])
def stream():

    model = request.form.get("model")
    user_msg = request.form.get("message")

    # ✅ Add user message (structured)
    chat_history.append({
        "role": "user",
        "content": user_msg
    })

    def generate():

        # Call Ollama chat API with streaming
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": chat_history,
                "stream": True
            },
            stream=True
        )

        reply = ""

        # Stream response chunks
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                chunk = data["message"]["content"]

                reply += chunk
                yield chunk

        # ✅ Save assistant reply to history
        chat_history.append({
            "role": "assistant",
            "content": reply
        })

    return Response(generate(), mimetype="text/plain")


if __name__ == "__main__":
    # prevent web browser from opening twice
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true": 
        webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)