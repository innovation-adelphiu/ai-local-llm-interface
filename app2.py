# Ollama/LLM & PocketTTS/Audio streaming

# TODO: add a role:system field
# TODO: manage what happens when chat_history gets long
# TODO: add a "stop voice" button

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

# on first run, download models from HuggingFace
tts_model = TTSModel.load_model()
voice_state = tts_model.get_state_for_audio_prompt("fantine")
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
        return [line.split()[0] for line in lines]

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

    # when the buffer hasn't reached an extraction condition yet
    return None, buffer

# main page
@app.route("/")
def index():
    model_list = get_models()
    return render_template("chat2.html", history=chat_history, models=model_list)

# no other routes; everything else handled by Web Sockets

# WebSocket handler (for incoming messages, sent by web page)
@socketio.on("send_message")
def handle_message(data):

    # get fields from sent data object
    model = data["model"]
    user_msg = data["message"]

    # store the user message (all data resent to LLM for context)
    chat_history.append({"role": "user", "content": user_msg})

    # call the Ollama Chat API (in streaming mode)
    # returns an iterator object
    response = requests.post(
        # ollama typically runs as a background process on startup
        #   _API server_ listens here (11434); runs specific model if not active
        "http://localhost:11434/api/chat",
        json={"model": model, "messages": chat_history, "stream": True},
        # also need to tell python requests to stream tokens as they are streamed to it
        #   otherwise code execution pauses here until all tokens received
        stream=True
    )

    # accumulate LLM response to store in chat_history
    reply = ""
    # store text not-yet sent to TTS system
    buffer = ""

    # process streaming tokens (received as JSON)
    #   objects: { "message":{"role":String, "content":String}, "done":boolean}
    # note: looping over an iterator continues until Stop single is sent (which triggers break condition)
    for line in response.iter_lines():

        # in case of empty JSON line
        if not line:
            continue

        data = json.loads(line.decode())

        chunk = data["message"]["content"]

        # Send text chunk to browser
        emit("text_chunk", chunk)

        reply += chunk
        buffer += chunk

        # predictive TTS buffering
        tts_chunk, buffer = extract_tts_chunk(buffer)

        # if enough text has been received to generate a chunk
        if tts_chunk:

            # text to be processed by TTS
            print("TTS:", tts_chunk)
            # generate audio speech
            audio = tts_model.generate_audio(voice_state, tts_chunk)
            # send audio to browser
            emit("audio_chunk", audio.numpy().tobytes(), binary=True)

    # speak any text remaining in the buffer
    if buffer.strip():

        # text to be processed by TTS
        print("TTS:", buffer)
        # generate audio speech
        audio = tts_model.generate_audio(voice_state, buffer)
        # send audio to browser
        emit("audio_chunk", audio.numpy().tobytes(), binary=True)

    # save LLM response message
    chat_history.append({"role": "assistant", "content": reply})

    # send done signal to client
    emit("done")

# launch application/server
if __name__ == "__main__":

    # prevent double browser launch
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:5000")

    socketio.run(app, debug=True)
