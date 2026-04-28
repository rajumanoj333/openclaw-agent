# OpenClaw Twilio Agent — Complete Guide

> A WhatsApp + voice-call chatbot that turns user requests into tasks for the OpenClaw AI agent and replies back through the same channel. Written for English **and** Indian languages.

This is the full handbook. Read top to bottom on day one. Skim later as a reference.

---

## Table of contents

1. [What this thing actually does](#1-what-this-thing-actually-does)
2. [The big picture (architecture)](#2-the-big-picture-architecture)
3. [Meet the components](#3-meet-the-components)
4. [What you need before you start](#4-what-you-need-before-you-start)
5. [One-time setup — laptop](#5-one-time-setup--laptop)
6. [One-time setup — Azure VM](#6-one-time-setup--azure-vm)
7. [Daily startup — the 3 windows](#7-daily-startup--the-3-windows)
8. [How a WhatsApp text becomes a reply](#8-how-a-whatsapp-text-becomes-a-reply)
9. [How a voice note becomes a reply](#9-how-a-voice-note-becomes-a-reply)
10. [How a phone call becomes a callback](#10-how-a-phone-call-becomes-a-callback)
11. [The code — file by file](#11-the-code--file-by-file)
12. [Troubleshooting cookbook](#12-troubleshooting-cookbook)
13. [FAQ](#13-faq)

---

## 1. What this thing actually does

You send a message — or speak — and a smart AI agent (OpenClaw, powered by Azure GPT-5.1-chat) does the work and replies back.

Three ways to talk to it:

```
┌──────────────────────────────────────────────────────────┐
│  1. WhatsApp text                                        │
│     You: "What is the capital of France?"                │
│     Bot: "Paris."                                        │
│                                                           │
│  2. WhatsApp voice note (English or Telugu/Hindi/etc.)   │
│     You: 🎙️ "నేను ఎలా ఉన్నాను చెప్పు"                  │
│     Bot: text reply + 🔊 spoken reply                    │
│                                                           │
│  3. Phone call                                           │
│     You dial +1 (947) 837-8039                           │
│     Bot: "Hello, this is Morpheus. What can I do?"       │
│     You speak → bot hangs up → you get WhatsApp confirm  │
│     30s later bot calls you back with the spoken answer  │
└──────────────────────────────────────────────────────────┘
```

---

## 2. The big picture (architecture)

```
                                     ┌─────────────────────┐
                                     │  Your Phone (📱)     │
                                     │  WhatsApp + Voice   │
                                     └──────────┬──────────┘
                                                │
                                                │ message / call
                                                ▼
                                     ┌─────────────────────┐
                                     │  Twilio Cloud (☁️)   │
                                     │  WhatsApp Sandbox + │
                                     │  Voice Number       │
                                     └──────────┬──────────┘
                                                │
                                                │ webhook (HTTPS POST)
                                                ▼
                                     ┌─────────────────────┐
                                     │  ngrok tunnel       │  ← public URL
                                     │  (free dev tunnel)  │     points to
                                     └──────────┬──────────┘     your laptop
                                                │
                                                │
            ┌───────────────────────────────────┴───────────────────┐
            │                                                        │
            │             YOUR LAPTOP (Windows)                      │
            │                                                        │
            │   ┌──────────────────────────────────────────────┐    │
            │   │  FastAPI gateway (uvicorn) :8080             │    │
            │   │                                               │    │
            │   │  • /twilio/whatsapp   text + voice-note webhook│   │
            │   │  • /twilio/voice      voice-call webhook      │    │
            │   │  • /audio/<name>      serve TTS audio files  │    │
            │   │                                               │    │
            │   │  Services:                                    │    │
            │   │  • Sarvam STT/TTS  (Telugu, Hindi, etc.)     │    │
            │   │  • Google STT/TTS  (English fallback)        │    │
            │   │  • Twilio REST     (send replies)            │    │
            │   │  • OpenClaw HTTP   (talks to VM)             │    │
            │   └──────────────────────┬───────────────────────┘    │
            │                          │                            │
            │   ┌──────────────────────▼───────────────────────┐    │
            │   │  SSH tunnel  (laptop:9000 → VM:9000)          │   │
            │   └──────────────────────┬───────────────────────┘    │
            │                          │                            │
            │   ┌──────────────────────────────────────────────┐    │
            │   │  Postgres + Redis (Docker, localhost only)   │    │
            │   │  (persistence — used in Phase 3)             │    │
            │   └──────────────────────────────────────────────┘    │
            └──────────────────────────┬───────────────────────────┘
                                       │
                                       │ HTTP via SSH tunnel
                                       ▼
            ┌─────────────────────────────────────────────────────┐
            │                                                      │
            │             AZURE VM   (74.225.254.197)              │
            │                                                      │
            │   ┌──────────────────────────────────────────────┐  │
            │   │  Proxy wrapper (FastAPI) :9000                │  │
            │   │  /agent  → spawns subprocess                  │  │
            │   └──────────────────────┬───────────────────────┘  │
            │                          │                          │
            │   ┌──────────────────────▼───────────────────────┐  │
            │   │  openclaw agent CLI subprocess                │  │
            │   │  → talks via WebSocket to gateway             │  │
            │   └──────────────────────┬───────────────────────┘  │
            │                          │                          │
            │   ┌──────────────────────▼───────────────────────┐  │
            │   │  OpenClaw Gateway (loopback) :18789           │  │
            │   │  (the brain — agent runtime)                  │  │
            │   └──────────────────────┬───────────────────────┘  │
            │                          │                          │
            └──────────────────────────┼──────────────────────────┘
                                       │
                                       │ HTTPS
                                       ▼
                            ┌─────────────────────┐
                            │ Azure AI Foundry    │
                            │ (gpt-5.1-chat)      │
                            └─────────────────────┘
```

**Why two machines?** OpenClaw was already installed on the Azure VM. We keep it there and host the rest on the laptop for fast iteration. When ready for production, everything moves to the VM.

---

## 3. Meet the components

| Layer | Tool | What it does | Where it runs |
|-------|------|--------------|---------------|
| **User** | WhatsApp / phone | You | Your phone |
| **Telco** | Twilio | Sends webhooks to us when you message/call | Twilio cloud |
| **Tunnel** | ngrok | Gives us a public HTTPS URL pointing at the laptop | Laptop ↔ ngrok cloud |
| **Gateway** | FastAPI app (`app/`) | Receives webhooks, orchestrates STT/LLM/TTS, sends replies | Laptop |
| **STT (Indic)** | Sarvam saaras-v3 | Converts voice → text in Indian languages | Sarvam cloud API |
| **STT (fallback)** | Google Cloud Speech | Converts voice → text in English | Google cloud API |
| **TTS (Indic)** | Sarvam | Converts text → spoken audio for Indian languages | Sarvam cloud API |
| **TTS (English)** | Google Cloud TTS | Converts text → spoken audio for English | Google cloud API |
| **Audio cleanup** | ffmpeg + pydub | WhatsApp doesn't accept WAV → convert to MP3 | Laptop |
| **DB / queue** | Postgres + Redis | Future analytics & state (phase 3) | Docker on laptop |
| **SSH tunnel** | OpenSSH | Forwards laptop:9000 → VM:9000 | Laptop |
| **Proxy wrapper** | `vm_agent_proxy.py` | Tiny FastAPI that runs `openclaw agent` as subprocess | Azure VM |
| **OpenClaw gateway** | `openclaw-gateway.service` | The actual AI agent runtime (WebSocket RPC) | Azure VM (loopback) |
| **LLM** | Azure AI Foundry | The brain — gpt-5.1-chat | Azure cloud |

---

## 4. What you need before you start

### Accounts (free or trial)

| Account | What you need from it |
|---------|----------------------|
| Twilio | Account SID, Auth Token, WhatsApp sandbox joined, voice number |
| ngrok | An authtoken (free) |
| Sarvam AI | API subscription key |
| Google Cloud | Project + Speech-to-Text API + Text-to-Speech API enabled + service-account JSON key |
| GitHub | Repo to push code (already created: `rajumanoj333/openclaw-agent`) |
| Azure | An Ubuntu VM running OpenClaw (already done) |

### Software on laptop (Windows)

| Tool | Why | Install command |
|------|-----|-----------------|
| Python 3.12 | The app | `winget install Python.Python.3.12` |
| Git | Version control | `winget install Git.Git` |
| Docker Desktop | Postgres + Redis | `winget install Docker.DockerDesktop` |
| ngrok | Public tunnel | `winget install ngrok.ngrok` |
| ffmpeg | Audio conversion | `winget install Gyan.FFmpeg` |
| OpenSSH client | SSH tunnel to VM | already in Windows |
| gcloud CLI | Manage GCP keys | `winget install Google.CloudSDK` |

After ffmpeg install you must **close every PowerShell window** so the new PATH takes effect.

---

## 5. One-time setup — laptop

You only do this once, on a new machine.

```
                    ┌─────────────────────────────┐
                    │   Step 1.  Clone repo       │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 2.  Make venv        │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 3.  Install deps     │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 4.  Fill .env        │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 5.  Drop GCP key     │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 6.  Start Docker     │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 7.  Configure ngrok  │
                    └──────────────┬──────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │   Step 8.  Set Twilio       │
                    │            webhooks         │
                    └─────────────────────────────┘
```

### Step 1 — Clone the repo

```powershell
cd "$HOME\Desktop"
mkdir twilo -Force
cd twilo
git clone https://github.com/rajumanoj333/openclaw-agent.git
cd openclaw-agent
```

### Step 2 — Create a Python virtual environment

A venv is an isolated Python install just for this project, so its packages don't pollute your system.

```powershell
py -3.12 -m venv venv
```

### Step 3 — Install Python dependencies

```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs FastAPI, Twilio SDK, Google Cloud SDKs, pydub, etc.

### Step 4 — Create your `.env` file

`.env` holds secrets. **Never commit it** (`.gitignore` already excludes it).

```powershell
copy .env.example .env
```

Open `.env` in Notepad and fill in real values. The fields that matter:

```
TWILIO_ACCOUNT_SID=...        # from console.twilio.com
TWILIO_AUTH_TOKEN=...         # from console.twilio.com
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886    # sandbox default
TWILIO_VOICE_FROM=+1XXXXXXXXXX                 # your Twilio voice number
WHATSAPP_NOTIFY_TO=whatsapp:+91XXXXXXXXXX     # the phone joined to sandbox

OPENCLAW_URL=http://127.0.0.1:9000   # SSH tunnel target — leave as-is
OPENCLAW_TOKEN=...                   # from VM ~/.openclaw/openclaw.json

GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-key.json
GCP_PROJECT_ID=hack-494411

SARVAM_API_KEY=...                   # from dashboard.sarvam.ai

PUBLIC_BASE_URL=https://your-ngrok-URL-here.ngrok-free.dev
```

### Step 5 — Drop the GCP service-account key

```powershell
gcloud iam service-accounts keys create "secrets\gcp-key.json" --iam-account=ser-601@hack-494411.iam.gserviceaccount.com
```

(Replace `ser-601@…` with your actual service account email.)

### Step 6 — Start Postgres + Redis (Docker)

These run in the background. Future features (logging, sessions) will use them.

```powershell
docker compose up -d
docker ps     # both containers should be "healthy"
```

### Step 7 — Configure ngrok auth (one-time)

1. Sign up at https://dashboard.ngrok.com
2. Copy your authtoken
3. Run:
   ```powershell
   ngrok config add-authtoken YOUR_TOKEN
   ```

### Step 8 — Set Twilio webhooks

You'll do this **after** you start ngrok and know the public URL (next section). For reference:

| Webhook | Where to set | URL |
|---------|--------------|-----|
| WhatsApp incoming | Twilio Console → Messaging → Try WhatsApp → Sandbox settings | `https://YOUR-NGROK.ngrok-free.dev/twilio/whatsapp` |
| Voice incoming | Twilio Console → Phone Numbers → click your number → Voice Configuration → "A call comes in" | `https://YOUR-NGROK.ngrok-free.dev/twilio/voice` |

---

## 6. One-time setup — Azure VM

The VM was built earlier. The only thing you do here is run the proxy wrapper.

```bash
# SSH in
ssh manoj@74.225.254.197

# clone repo (or pull if already cloned)
cd ~
[ -d openclaw-agent ] && (cd openclaw-agent && git pull) \
  || git clone https://github.com/rajumanoj333/openclaw-agent.git
cd ~/openclaw-agent

# install python deps
sudo apt install -y python3-venv python3-pip
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn pydantic
```

`scripts/vm_agent_proxy.py` is the wrapper that exposes `/agent` on `127.0.0.1:9000` and shells out to `openclaw agent`.

OpenClaw itself is already installed and running as a systemd user service (`openclaw-gateway.service`).

---

## 7. Daily startup — the 3 windows

Every day, you open **3 terminal windows**. Don't close them while developing.

```
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│   Window 1                Window 2                Window 3  │
│   ─────────               ─────────               ────────  │
│   SSH tunnel              uvicorn                 ngrok      │
│   to VM:9000              FastAPI app             public URL │
│                                                              │
│   keep open               keep open               keep open │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Window 1 — SSH tunnel

```powershell
ssh -L 127.0.0.1:9000:127.0.0.1:9000 -o ServerAliveInterval=10 manoj@74.225.254.197 -N
```

What this does:
- Connects to the VM
- Says "anything I send to **my** port 9000 should go to **the VM's** port 9000"
- `-N` = don't start a shell, just hold the tunnel
- `ServerAliveInterval=10` = ping every 10 sec so the tunnel doesn't go stale

The window will look frozen — that's normal. Don't type anything. Don't close it.

### Window 2 — uvicorn (the FastAPI app)

```powershell
cd "$HOME\Desktop\twilo\openclaw-agent"
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
```

What this does:
- Starts the web server on port 8080
- `--reload` watches your `.py` files and restarts when you edit code
- All log lines (incoming requests, STT calls, OpenClaw replies, TTS) print here

You'll spend most of your time watching this window.

### Window 3 — ngrok

```powershell
ngrok http 8080
```

What this does:
- Creates a free public HTTPS URL (e.g. `https://radia-xxxx.ngrok-free.dev`)
- Forwards every request that hits the URL to your laptop's port 8080
- Shows live request log

The URL might change between restarts on free tier. If it does:
1. Copy the new URL
2. Update `PUBLIC_BASE_URL=...` in `.env` (uvicorn auto-reloads)
3. Update Twilio sandbox + voice webhook URLs to match

### Window 4 (optional) — VM proxy

The proxy on the VM should already be running from earlier setup. To check or restart:

```bash
# on VM
ps aux | grep vm_agent_proxy.py
# if missing:
cd ~/openclaw-agent
nohup venv/bin/python scripts/vm_agent_proxy.py > /tmp/proxy.log 2>&1 &
```

### Health checks

In a 4th terminal, run:

```powershell
curl.exe -s http://127.0.0.1:9000/health   # tunnel + VM proxy
curl.exe -s http://127.0.0.1:8080/health   # uvicorn
curl.exe -s https://radia-xxxx.ngrok-free.dev/health  # ngrok
```

All three: `{"status":"ok"}` = ready.

---

## 8. How a WhatsApp text becomes a reply

```
   📱 Phone                        ☁️ Twilio                  💻 Laptop                        ☁️ Azure VM                   ☁️ Azure
                                                                                                                              Foundry
   "What is 2+2?"
       │
       ▼
   ┌─────────┐  HTTPS POST  ┌──────────┐  HTTPS POST  ┌────────────────────┐
   │WhatsApp │─────────────▶│ Sandbox  │─────────────▶│ ngrok →            │
   │         │              │ Webhook  │              │ /twilio/whatsapp   │
   └─────────┘              └──────────┘              └─────────┬──────────┘
                                                                │
                                                                │ background task
                                                                ▼
                                                      ┌────────────────────┐  HTTP /agent  ┌──────────────────┐
                                                      │ ask_openclaw()     │──────────────▶│ vm_agent_proxy   │
                                                      └────────────────────┘               │ subprocess:      │
                                                                ▲                          │ openclaw agent   │
                                                                │                          └────────┬─────────┘
                                                                │                                   │ WebSocket RPC
                                                                │                                   ▼
                                                                │                          ┌──────────────────┐
                                                                │                          │ openclaw         │
                                                                │                          │ gateway :18789   │
                                                                │                          └────────┬─────────┘
                                                                │                                   │ HTTPS
                                                                │                                   ▼
                                                                │                          ┌──────────────────┐
                                                                │                          │ gpt-5.1-chat     │
                                                                │                          │ "4"              │
                                                                │                          └────────┬─────────┘
                                                                │                                   │
                                                                │     ◀─────────────────────────────┘
                                                                │
                                                                ▼
                                                      ┌────────────────────┐  Twilio REST  ┌──────────┐
                                                      │ send_whatsapp()    │──────────────▶│ Twilio   │──▶ 📱 "4"
                                                      └────────────────────┘               └──────────┘
```

**Step by step:**

1. You type "What is 2+2?" → Twilio receives → Twilio POSTs `/twilio/whatsapp` (via ngrok)
2. `app/routes/whatsapp.py` reads the form, sees `Body="What is 2+2?"`, schedules a background task, replies with TwiML "Working on it…"
3. Background task calls `ask_openclaw()` which POSTs to `http://127.0.0.1:9000/agent` (SSH-forwarded to VM)
4. VM proxy spawns `openclaw agent --to <phone> --message "What is 2+2?" --json`
5. The CLI talks to the local OpenClaw gateway (WebSocket RPC), which talks to Azure Foundry
6. Reply text comes back through the chain
7. `send_whatsapp()` calls Twilio REST API to send "4" back to your number

End-to-end latency: 13–25 seconds.

---

## 9. How a voice note becomes a reply

```
📱 You record voice note
          │
          ▼
   Twilio gets media URL + audio/ogg
          │
          │  webhook → ngrok → laptop
          ▼
   ┌────────────────────────────┐
   │ /twilio/whatsapp           │
   │  num_media=1               │
   │  → background voice handler│
   └────────────┬───────────────┘
                │ "Got your voice note. Transcribing…"  ← TwiML
                │
                ▼
   ┌────────────────────────────┐
   │ download_media()            │  ← Twilio basic auth
   │ → audio bytes (audio/ogg)   │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ Sarvam STT (saaras:v3)      │
   │ → text + lang code          │  fallback: Google STT
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ detect_lang(text)           │  ← Unicode block check
   │ → "te-IN" / "en-IN" / etc.  │     (overrides bad Sarvam tag)
   └────────────┬───────────────┘
                │
                │ send_whatsapp("🎙️ I heard: ...")  ← preview
                │
                ▼
   ┌────────────────────────────┐
   │ ask_openclaw(text)          │  ← same as text path
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ send_whatsapp(reply text)   │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ synthesize(reply, lang)     │
   │  Sarvam TTS for Indic       │
   │  Google TTS for English     │
   │  → MP3 bytes                │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ audio_store.save()          │
   │ → uuid.mp3 in data/audio/   │
   └────────────┬───────────────┘
                ▼
   ┌────────────────────────────┐
   │ send_whatsapp_media(URL)    │
   │  url = https://ngrok/audio/ │
   │  body = "🔊 voice: sarvam"  │
   └────────────┬───────────────┘
                ▼
         Twilio fetches MP3,
         delivers as voice note
                │
                ▼
            📱 You hear it
```

You'll get **4 WhatsApp messages** back:

1. "Got your voice note. Transcribing…"
2. "🎙️ I heard: '<transcript>' (te-IN)\nWorking on it…"
3. The text reply
4. The audio reply with caption "🔊 voice: sarvam (te-IN)"

---

## 10. How a phone call becomes a callback

This is **Flow A (async callback)**. Latency makes a real-time conversation infeasible without lower-latency models.

```
                        ┌─────────────────────────────────────┐
                        │   1. INBOUND CALL                   │
                        └─────────────────────────────────────┘

📱 Dial +1 (947) 837-8039
         │
         ▼
   Twilio webhook → /twilio/voice
         │
         ▼
   TwiML response:
     <Say>Hello, this is Morpheus. What can I do for you?
          Please speak after the beep, then stay silent.</Say>
     <Record action="/twilio/voice/recorded" maxLength="60"
             timeout="3" finishOnKey="#"/>
     <Say>Sorry, I didn't catch that. Goodbye.</Say>

         │
         │  caller speaks
         ▼
   3 sec silence  → Twilio stops recording
         │
         ▼
   Twilio POSTs /twilio/voice/recorded with RecordingUrl
         │
         ▼
   TwiML response:
     <Say>Thanks. I will work on it and call you back when it is done.</Say>
     <Hangup/>


                        ┌─────────────────────────────────────┐
                        │   2. BACKGROUND PROCESSING          │
                        └─────────────────────────────────────┘

   download_media(RecordingUrl + ".mp3")
         │
         ▼
   Sarvam STT → transcript + lang
         │
         ▼
   send_whatsapp(WHATSAPP_NOTIFY_TO,
                 "📞 Got your call. I heard: '...' (te-IN)")
         │
         ▼
   ask_openclaw(transcript) → reply text
         │
         ▼
   synthesize(reply, lang) → MP3
         │
         ▼
   audio_store.save() → uuid.mp3
         │
         ▼
   voice_session.put(call_id, audio_name, fallback_text)
         │
         ▼
   make_call(caller, "https://ngrok/twilio/voice/say/<call_id>")


                        ┌─────────────────────────────────────┐
                        │   3. OUTBOUND CALLBACK              │
                        └─────────────────────────────────────┘

   Twilio dials your phone
         │
         ▼
   📱 You answer
         │
         ▼
   Twilio fetches the TwiML URL we passed
         │
         ▼
   /twilio/voice/say/<call_id>
   looks up cached reply →
     <Play>https://ngrok/audio/uuid.mp3</Play>
     <Hangup/>

         │
         ▼
   📱 You hear the spoken answer
         │
         ▼
   send_whatsapp(WHATSAPP_NOTIFY_TO, "📞 Result:\n<text>")
```

**The trick:** when we make the outbound call, Twilio doesn't yet know what to say. We give it a URL it'll fetch *during* the call, and we serve the reply audio at that URL. The `voice_session` in-memory dict holds the lookup from `call_id → audio_name`.

---

## 11. The code — file by file

```
openclaw-agent/
├── app/
│   ├── main.py                     ◀ FastAPI entry; mounts routes
│   ├── config.py                   ◀ reads .env via pydantic-settings
│   ├── lib/
│   │   └── verify.py               ◀ Twilio signature check (prod only)
│   ├── routes/
│   │   ├── whatsapp.py             ◀ /twilio/whatsapp text + voice notes
│   │   ├── voice.py                ◀ /twilio/voice* call flow
│   │   └── audio.py                ◀ /audio/<name> serves TTS files
│   └── services/
│       ├── twilio_client.py        ◀ send_whatsapp / send_whatsapp_media / make_call
│       ├── twilio_media.py         ◀ download_media (Twilio basic auth)
│       ├── openclaw.py             ◀ ask_openclaw (HTTP to VM proxy)
│       ├── stt.py                  ◀ transcribe — Sarvam + Google fallback
│       ├── tts.py                  ◀ synthesize — Sarvam + Google + MP3 convert
│       ├── lang_detect.py          ◀ Unicode-block language detection
│       ├── audio_store.py          ◀ disk cache for TTS files (30-min TTL)
│       └── voice_session.py        ◀ in-memory map: call_id → audio_name
├── scripts/
│   └── vm_agent_proxy.py           ◀ runs on VM; wraps `openclaw agent` CLI
├── data/                           ◀ Postgres/Redis volumes + audio cache (gitignored)
├── secrets/                        ◀ GCP service-account key (gitignored)
├── docker-compose.yml              ◀ Postgres + Redis (localhost-bound)
├── requirements.txt                ◀ Python deps
├── .env.example                    ◀ template — copy to .env
└── README.md
```

### What each file does

#### `app/main.py`
The FastAPI application object. Mounts the three routers (whatsapp, voice, audio) and exposes `/health`. Nothing fancy.

#### `app/config.py`
Reads `.env` and exposes typed settings (`settings.twilio_auth_token`, etc.). Using `pydantic-settings` so wrong types fail fast.

#### `app/routes/whatsapp.py`
Twilio sends every WhatsApp message here. We:
1. Look at `NumMedia` to decide text vs voice note.
2. Reply with TwiML "Working on it…" so Twilio doesn't time out (Twilio gives webhooks 15 seconds).
3. Schedule a `BackgroundTask` to do the slow work and send the real reply via REST.

#### `app/routes/voice.py`
Three endpoints:
- `POST /twilio/voice` — greets the caller and starts recording.
- `POST /twilio/voice/recorded` — Twilio hits this when the caller stops. We return a "thanks, calling back" TwiML and schedule the background processor.
- `GET|POST /twilio/voice/say/<call_id>` — Twilio fetches this on the outbound call and we return TwiML that plays the cached reply.

#### `app/routes/audio.py`
Serves files from `data/audio/`. Used by Twilio for both WhatsApp media and the outbound TwiML `<Play>` URL.

#### `app/services/openclaw.py`
One function: `ask_openclaw(message, to=phone, timeout=120)`. POSTs to `http://127.0.0.1:9000/agent` (the SSH-tunneled VM proxy). Returns the reply text.

#### `app/services/stt.py`
`transcribe(audio_bytes, mime)` — tries Sarvam first (best for Indian languages, auto-detect across en-IN/te-IN/hi-IN/etc.). Falls back to Google if Sarvam errors or returns empty.

#### `app/services/tts.py`
`synthesize(text, lang_code)` — for Indic languages → Sarvam (returns base64 WAV which we decode and convert to MP3 with pydub+ffmpeg). For English → Google TTS (returns MP3 directly). WhatsApp doesn't accept WAV, hence the conversion.

#### `app/services/lang_detect.py`
Sarvam sometimes mislabels English audio as `te-IN` in codemix mode. We re-check the transcript by counting Unicode characters in each Indic block; if the text is mostly ASCII letters, return `en-IN`.

#### `app/services/twilio_client.py`
Three helpers: `send_whatsapp`, `send_whatsapp_media`, `make_call`. Use the official `twilio` SDK.

#### `app/services/twilio_media.py`
Downloads an audio file from a Twilio MediaUrl. The first hop needs basic auth (Account SID + Auth Token); after the redirect to S3, the auth header is stripped — exactly what we want.

#### `app/services/audio_store.py`
Saves TTS bytes under `data/audio/<uuid>.<ext>` and exposes `path_for(name)` for the audio router. GCs files older than 30 minutes whenever a new one is saved.

#### `app/services/voice_session.py`
A small in-memory `dict` with TTL. When we make an outbound call, we cache `(audio_filename, fallback_text)` keyed by a random `call_id`. Twilio fetches `/twilio/voice/say/<call_id>` during the call and we return TwiML that plays that audio.

#### `scripts/vm_agent_proxy.py`
Lives on the VM. Tiny FastAPI on `127.0.0.1:9000` with one endpoint: `POST /agent`. Reads `{message, to, timeout}`, spawns `openclaw agent ... --json`, parses stdout (or stderr — the CLI sometimes writes the JSON there when the gateway falls back to embedded mode), extracts `payloads[0].text`, returns it.

Why this proxy instead of calling OpenClaw directly? Because OpenClaw's only real API is a **WebSocket RPC** with a complex challenge-response handshake. Reverse-engineering it would take weeks. The CLI already speaks that protocol — we just shell out to it.

---

## 12. Troubleshooting cookbook

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl http://127.0.0.1:9000/health` times out | SSH tunnel dropped | Restart Window 1 |
| `Connection reset by peer` from OpenClaw | Gateway zombied | On VM: `openclaw gateway restart` |
| Voice reply audio doesn't play in WhatsApp | We sent WAV (WhatsApp rejects) | Confirm ffmpeg in PATH; `mp3=NNN` should appear in log |
| `Couldn't find ffmpeg or avconv` | uvicorn started before installing ffmpeg | Close PowerShell, reopen, restart uvicorn |
| `Twilio Error 21210 …source phone… not verified` | `TWILIO_VOICE_FROM` mismatches your owned number | Update `.env`, restart uvicorn |
| WhatsApp says "Working on it…" but no real reply comes | Background task crashed | Check uvicorn log for traceback |
| ngrok URL changes every day | Free plan rotates | Update `.env` `PUBLIC_BASE_URL` and Twilio webhook URLs every restart, or upgrade ngrok |
| Agent always replies "BOOTSTRAP pending…" | OpenClaw wants identity setup | On VM: write IDENTITY.md, delete BOOTSTRAP.md, clear sessions, restart gateway |
| Outbound call uses wrong number | uvicorn cached old `.env` | Restart uvicorn (Ctrl+C + relaunch) |
| WhatsApp confirms during voice call go to wrong number | Caller phone isn't joined to sandbox | Set `WHATSAPP_NOTIFY_TO=whatsapp:+91...` in `.env` |
| `pydub.utils.RuntimeWarning: Couldn't find ffmpeg` | New PATH didn't propagate to running process | Close ALL PowerShells, reopen fresh, restart uvicorn |

---

## 13. FAQ

**Q. Why three windows? Can't this be one command?**
For now it's three because each piece needs its own log and you'll Ctrl+C them independently when iterating. Phase 3 (move to VM) collapses all of them behind a single `docker compose up`.

**Q. Why ngrok? Why not just open a port on my router?**
Because Twilio needs HTTPS with a valid TLS certificate. ngrok gives that for free. Also, you don't want to expose your laptop directly to the internet.

**Q. Why does the agent reply take 15+ seconds?**
Most of that is the LLM (Azure gpt-5.1-chat with `thinking=medium`). Sarvam STT is ~1 sec, Twilio download ~2 sec, our code is negligible. Switching to a faster model trims it to ~5 sec.

**Q. Why do voice calls sound robotic on the bot's *greeting* but natural on the reply?**
The greeting uses Twilio's built-in `<Say voice="alice">` (free, robotic). The reply uses our Sarvam/Google TTS audio (much better). Replacing the greeting is one line — generate TTS for "Hello, this is Morpheus…" once and `<Play>` it.

**Q. Why do voice notes come back as 4 separate WhatsApp messages?**
For visibility while debugging. We send: ack → preview transcript → text answer → audio answer. In production we'd merge to two: preview (instant) and answer-with-audio (final).

**Q. Can the agent actually do tasks, or just answer questions?**
Both. OpenClaw has tools registered (`exec`, `web_search`, `web_fetch`, `cron`, `sessions_*`, `memory_*`). Anything you'd type in a Claude/GPT chat with shell tools, you can ask the bot to do.

**Q. What's the next milestone?**
Choose:
- **D**: move the whole stack onto the Azure VM behind Caddy + the free Azure subdomain. Drop ngrok and the SSH tunnel.
- **E**: persist users + sessions + messages in Postgres for analytics and history.
- Other: turn on Twilio signature verification, add lang-routed greetings, add multi-turn confirmation, etc.

---

*Last updated: 2026-04-28. Repo: https://github.com/rajumanoj333/openclaw-agent*
