# pdf-autofillr-chatbot

LLM-powered conversation that collects form data and fills the PDF at the end.

## Install

```bash
pip install "pdf-autofillr[chatbot]"                     # + mapper
pip install "pdf-autofillr[chatbot-rag]"                 # + mapper + RAG
pip install "pdf-autofillr[chatbot,s3]"                  # + mapper + S3
```

## CLI

```bash
chatbot-cli --pdf-path data/input/blank_form.pdf
chatbot-cli --pdf-path data/input/blank_form.pdf --report
chatbot-server       # REST API → http://localhost:8001/docs
```

## Key env vars

```bash
CHATBOT_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...
chatbot_PDF_FILLER=mapper
chatbot_PDF_PATH=./data/input/blank_form.pdf
chatbot_STORAGE=local
chatbot_CONFIG_PATH=./configs
MAPPER_API_URL=                   # leave empty for in-process
```

## Config samples

`packages/chatbot/config_samples/` — copy to `configs/` and customise:
- `form_keys.json` — canonical field keys
- `field_questions.json` — per-field conversation prompts
- `global_investor_type_keys/` — investor-type-specific key sets

## Source layout

```
packages/chatbot/src/chatbot/
├── client.py        chatbotClient — main entry point
├── core/            Engine, router, session, states
├── extraction/      LLM field extraction from conversation
├── handlers/        Per-state handlers (investor type, data collection…)
├── pdf/             Filling + mapper integration
├── storage/         Local, S3, GCS, Azure
├── config/          Settings, form config
├── telemetry/       Session metrics
└── entrypoints/     CLI · FastAPI · Lambda · Azure · GCP
```
