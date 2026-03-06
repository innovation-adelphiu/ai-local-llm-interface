# Ollama/LLM & PocketTTS/Audio streaming

print("Running program...")

import os
import webbrowser
import json
import requests
import subprocess

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from pocket_tts import TTSModel

# initialize Flask
app = Flask(__name__)

# use WebSockets for constant connection,
# instead of repeated GET/POST requests
socketio = SocketIO(app, cors_allowed_origins="*")

# store conversation history from Ollama
chat_history = []

# load TTS model 
print("Loading PocketTTS model...")
tts_model = TTSModel.load_model()
voice_state = tts_model.get_state_for_audio_prompt("alba")
print("PocketTTS ready...")

# detect installed models; use in a dropdown list in website

def get_models():
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )
        lines = result.stdout.strip().split("\n")[1:]
        return [line.split()[0] for line in lines if line]

    except:
        # fallback model
        return ["llama3.1"]

# determine when enough text exists to send to TTS
# returns (text_to_speak, remaining_buffer)
def extract_tts_chunk(buffer):

    # punctuation triggers
    punctuation = [".", "?", "!", ","]

    for p in punctuation:
        idx = buffer.rfind(p)
        # ensure chunk is long enough
        if idx > 40:
            chunk = buffer[:idx+1]
            remainder = buffer[idx+1:]
            return chunk, remainder

    # length trigger
    if len(buffer) > 120:
        split = buffer.rfind(" ")
        if split != -1:
            chunk = buffer[:split]
            remainder = buffer[split:]
            return chunk, remainder

    return None, buffer

# main page
@app.route("/")
def index():
    return render_template(
        "chat2.html",
        history=chat_history,
        models=get_models()
    )

# WebSocket handler (incoming messages)
@socketio.on("send_message")
def handle_message(data):
    model = data["model"]
    user_msg = data["message"]

    ###########################################
    # Save user message
    ###########################################

    chat_history.append({
        "role": "user",
        "content": user_msg
    })

    ###########################################
    # Call Ollama Chat API (Streaming)
    ###########################################

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
    buffer = ""

    ###########################################
    # Process streaming tokens
    ###########################################

    for line in response.iter_lines():

        if not line:
            continue

        data = json.loads(line.decode())

        chunk = data["message"]["content"]

        #######################################
        # Send text chunk to browser
        #######################################

        emit("text_chunk", chunk)

        reply += chunk
        buffer += chunk

        #######################################
        # Predictive TTS buffering
        #######################################

        tts_chunk, buffer = extract_tts_chunk(buffer)

        if tts_chunk:

            print("TTS:", tts_chunk)

            ###################################
            # Generate speech
            ###################################

            audio = tts_model.generate_audio(
                voice_state,
                tts_chunk
            )

            ###################################
            # Send audio to browser
            ###################################

            emit(
                "audio_chunk",
                audio.numpy().tobytes(),
                binary=True
            )

    ###########################################
    # Speak remaining buffer
    ###########################################

    if buffer.strip():

        audio = tts_model.generate_audio(
            voice_state,
            buffer
        )

        emit(
            "audio_chunk",
            audio.numpy().tobytes(),
            binary=True
        )

    ###########################################
    # Save assistant message
    ###########################################

    chat_history.append({
        "role": "assistant",
        "content": reply
    })

    ###########################################
    # Signal completion
    ###########################################

    emit("done")

###############################################
# Launch Server
###############################################

if __name__ == "__main__":

    # Prevent double browser launch
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:5000")

    socketio.run(app, debug=True)