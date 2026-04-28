# pdf-autofillr-chatbot

Conversational investor onboarding chatbot. Collects investor data through natural language and fills PDF subscription forms automatically.

## Install

```bash
pip install pdf-autofillr-chatbot          # core + CLI
pip install "pdf-autofillr-chatbot[server]" # + API server
```

## Quickstart (3 steps, do once)

```bash
# 1. Copy sample configs into your working directory to edit
python -c "import chatbot; chatbot.copy_sample_configs('.')"

# 2. Create your .env file
cp .env.example .env
# Open .env and set:  OPENAI_API_KEY=sk-...

# 3. Run
chatbot-cli     # interactive terminal
chatbot-server  # REST API on http://localhost:8001
```

## Entry points

| Command | What it does |
|---|---|
| `chatbot-cli` | Interactive terminal session |
| `chatbot-server` | FastAPI server on :8001 — docs at /docs |

## CLI options

```bash
chatbot-cli --pdf-path /path/to/blank.pdf   # fill a PDF
chatbot-cli --output filled.json            # save collected data
chatbot-cli --report                        # print fill stats
chatbot-cli --user-id u1 --session-id s1   # tag the session
```

## API

```bash
# Start server
chatbot-server

# Send a message
curl -X POST http://localhost:8001/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s1","message":"my name is John Smith"}'
```

Full API docs: http://localhost:8001/docs

| Endpoint | Method | Description |
|---|---|---|
| `/chatbot/chat` | POST | Send a message |
| `/chatbot/session/{uid}/{sid}` | GET | Get filled data |
| `/chatbot/session/{uid}/{sid}/fill-report` | GET | Fill statistics |
| `/chatbot/session/{uid}/{sid}` | DELETE | Delete session |
| `/health` | GET | Health check |

## Python library

```python
from chatbot import chatbotClient, LocalStorage, FormConfig

client = chatbotClient(
    openai_api_key="sk-...",
    storage=LocalStorage("./data/chatbot", "./configs"),
    form_config=FormConfig.from_directory("./configs"),
)

response, complete, data = client.send_message("user1", "session1", "")
print(response)  # greeting

while not complete:
    user_input = input("You: ")
    response, complete, data = client.send_message("user1", "session1", user_input)
    print(f"Bot: {response}")

print("Done:", data)
```

## AWS Lambda

```python
from chatbot.entrypoints.aws_lambda import handler  # drop-in Lambda handler
```

## Mount in existing FastAPI app

```python
from fastapi import FastAPI
from chatbot.entrypoints.fastapi_app import app as chatbot_app

main_app = FastAPI()
main_app.mount("/onboarding", chatbot_app)
```

## Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required** |
| `chatbot_STORAGE` | `local` | `local` or `s3` |
| `chatbot_DATA_PATH` | `./data/chatbot` | Where sessions are saved |
| `chatbot_CONFIG_PATH` | `./configs` | Your configs folder |
| `chatbot_PDF_FILLER` | `none` | `none`, `mapper`, or `managed` |
| `chatbot_PDF_PATH` | — | Path to blank PDF |
| `chatbot_BOT_NAME` | `Bot` | Bot display name |
| `PORT` | `8001` | API server port |

Full reference: `.env.example`

## Editing configs

After running `copy_sample_configs`, you'll have a `configs/` folder. Edit these JSON files to customise what the bot asks:

| File | Controls |
|---|---|
| `field_questions.json` | What question is asked for each field |
| `mandatory.json` | Which fields cannot be skipped |
| `form_keys.json` | All field IDs |
| `form_keys_label.json` | Human-readable field labels |
| `global_investor_type_keys/` | Fields per investor type |

## Adding new functionality

The chatbot is fully modular — each conversation state is a separate file:

**New conversation state:**
1. Add state to `src/chatbot/core/states.py`
2. Create `src/chatbot/handlers/your_handler.py` extending `BaseHandler`
3. Register in `src/chatbot/core/router.py`

**New API route:** edit `src/chatbot/entrypoints/fastapi_app.py` — standard FastAPI.

**Change questions:** edit JSON files in `configs/` — no code changes needed.

## Publish a new version

```bash
# 1. Bump version in pyproject.toml
# 2. Build
python -m build
# 3. Upload
twine upload dist/*
```

## Run tests

```bash
pip install "pdf-autofillr-chatbot[dev]"
pytest tests/unit/ -v
```