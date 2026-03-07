# ai-local-llm-interface

## app.py

A front-end system for interacting with a locally installed LLM (via Ollama).

Assumes that a local LLM (such as llama3.1) has been installed on your computer via Ollama.

Start the application from the terminal using ```python app.py```; it will start a local server and open a web browser.

<img src="app.png">

## app2.py

This version adds text-to-speech (TTS) capabilities using Pocket-TTS.

See https://github.com/kyutai-labs/pocket-tts
and https://kyutai.org/blog/2026-01-13-pocket-tts
for more information.

To run this code, you will need to

```pip install pocket-tts```

and 

```pip install sounddevice``` (for local audio playback)

The first time this program runs, it downloads voice models from HuggingFace into your default cache. On Windows, this is typically in the directory ```C:\Users\<your-username>\.cache\huggingface\hub\```

