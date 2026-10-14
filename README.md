# Local AI Chatbot with Ollama

A beginner-friendly chatbot app that runs completely on your local Windows computer using Flask and Ollama.

## Features
- Local AI model via Ollama
- Simple modern web interface
- Recent conversation memory
- Streaming responses
- Clear chat and new conversation buttons
- Error messages for model and server issues

## Requirements
- Windows 10 or 11
- Python 3.10+
- Ollama installed and running

## Install Ollama
1. Download from https://ollama.com/download/windows
2. Install and restart PowerShell
3. Verify:

```powershell
ollama --version
ollama list
```

If the model is missing:

```powershell
ollama pull qwen2.5:3b
```

## Setup project

```powershell
cd C:\chatBOT\ai_chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the app

```powershell
python app.py
```

Open in browser:

```text
http://localhost:5000
```

## Project structure
```text
ai_chatbot/
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── script.js
│   └── style.css
└── templates/
    └── index.html
```
