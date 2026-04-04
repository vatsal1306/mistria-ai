# Mistria AI

An adaptive AI companion chatbot powered by Ollama, with a dynamic pulse system that adjusts conversation intensity based on user interaction.

## Prerequisites

- **Python 3.12+**
- **Ollama** — download from [ollama.com/download](https://ollama.com/download)

## Setup

```bash
# Clone and enter the project
git clone https://github.com/vatsal1306/mistria-ai.git
cd mistria-ai

# Install Python dependencies
pip install -r requirements.txt

# Pull the required model via Ollama
ollama pull dolphin-llama3
```

## Running

There are three ways to interact with Mistria:

### 1. Browser Chat (FastAPI + WebSocket)

```bash
python main.py
```

Open **http://127.0.0.1:8000** — features real-time streaming, pulse display, reset, and set-pulse controls.

### 2. Streamlit Chat

```bash
python -m streamlit run app.py
```

Open **http://localhost:8501** — features streaming chat, pulse slider, reset, and logout in the sidebar.

### 3. Terminal Chat (CLI)

```bash
# Start the API server first
python main.py

# In another terminal
python chat_cli.py
```

## Project Structure

```
├── main.py              # FastAPI server (REST + WebSocket endpoints)
├── app.py               # Streamlit chat interface
├── chat_cli.py          # Terminal chat client
├── database.json        # User profiles and session data
├── requirements.txt     # Python dependencies
├── static/
│   └── chat.html        # Browser chat UI
└── src/
    ├── config.py         # Model settings, pulse tuning, trigger words
    ├── llm.py            # Ollama integration, system prompt, streaming
    ├── chat.py           # Chat turn orchestration
    ├── pulse.py          # Pulse scoring engine
    ├── sessions.py       # In-memory session management
    └── persistence.py    # JSON-backed user storage
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Browser chat UI |
| GET | `/health` | Health check |
| POST | `/chat` | Send a message (non-streaming) |
| POST | `/reset` | Reset session and pulse to default |
| POST | `/set-pulse` | Set pulse to a specific value (0-100) |
| WebSocket | `/ws/chat` | Real-time streaming chat |

## Configuration

Edit `src/config.py` to adjust:

- **MODEL_NAME** — Ollama model to use (default: `dolphin-llama3`)
- **MODEL_MAX_TOKENS** — max response length (default: 150)
- **PULSE_DEFAULT** — starting pulse value (default: 50)
- **HEAT_TRIGGERS** — words that boost the pulse score

## Adding Users

Add new users to `database.json`:

```json
{
    "user_102": {
        "name": "Jordan",
        "gender": "Male",
        "interests": ["gaming", "hiking"]
    }
}
```
