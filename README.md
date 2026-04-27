# OpenClaw Twilio Agent

WhatsApp + voice agent. Twilio webhook → FastAPI → OpenClaw → reply.

## Stack

- FastAPI (Python 3.12)
- Twilio (WhatsApp + Voice)
- OpenClaw (LLM agent runtime, Azure AI Foundry backend)
- Google Cloud Speech (STT/TTS — English)
- Sarvam AI (STT/TTS — Indic languages)
- Postgres + Redis (Docker)

## Local dev

```bash
# 1. clone
git clone https://github.com/rajumanoj333/openclaw-agent.git
cd openclaw-agent

# 2. venv
py -3.12 -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 3. env
copy .env.example .env
# edit .env with real values (never commit)

# 4. run
uvicorn app.main:app --reload --port 8080

# 5. tunnel for Twilio webhook
ngrok http 8080
# paste https URL into Twilio sandbox webhook
```

## Health check

```
curl http://localhost:8080/health
```

## Project layout

```
app/
├── main.py          # FastAPI entry
├── config.py        # env settings
├── routes/          # /twilio/whatsapp, /twilio/voice
├── services/        # twilio, openclaw, stt, tts, db
├── lib/             # signature verify, helpers
└── models/          # SQLAlchemy models
```
