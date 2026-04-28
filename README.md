# OpenClaw Twilio Agent

WhatsApp + voice-call agent. Send a message or call a number, the OpenClaw AI agent (Azure GPT-5.1-chat) does the work, replies back through the same channel. English plus Indian languages (Telugu, Hindi, etc.).

## Read these first

- **[`docs/GUIDE.md`](docs/GUIDE.md)** — the complete handbook (architecture, components, setup, code walkthrough, troubleshooting, FAQ). For first-time readers and non-technical reviewers.
- **[`docs/STARTUP.md`](docs/STARTUP.md)** — copy-paste daily startup commands. For when you just want to start working.

## What you can do today

| Channel | Direction | Status |
|---------|-----------|--------|
| WhatsApp text | in/out | working |
| WhatsApp voice note (English + Telugu/Hindi/etc.) | in/out | working |
| Phone call (inbound greet → record → callback with TTS reply) | in/out | working |

## Stack at a glance

```
Twilio  ──▶  ngrok  ──▶  FastAPI (laptop)  ──▶  SSH tunnel  ──▶  vm_agent_proxy
                                                                       │
                                                                       ▼
                                                              openclaw agent CLI
                                                                       │
                                                                       ▼
                                                            OpenClaw gateway WS
                                                                       │
                                                                       ▼
                                                          Azure AI Foundry (gpt-5.1)
```

- **STT (Indic + English):** Sarvam saaras-v3, fallback Google Cloud Speech
- **TTS (Indic):** Sarvam, **(English):** Google Cloud TTS
- **Storage:** Postgres + Redis (Docker, localhost-only)
- **Tunnel:** ngrok (dev), SSH `-L` for VM access

## Project layout

```
app/                 FastAPI app (routes + services)
scripts/             vm_agent_proxy.py (runs on Azure VM)
docs/                GUIDE.md, STARTUP.md
data/                Postgres/Redis volumes + audio cache (gitignored)
secrets/             GCP key (gitignored)
```

## Quick health check

```powershell
curl.exe -s http://127.0.0.1:9000/health    # SSH tunnel + VM proxy
curl.exe -s http://127.0.0.1:8080/health    # FastAPI
```

Both must return `{"status":"ok"}`.

For everything else, open [`docs/GUIDE.md`](docs/GUIDE.md).
