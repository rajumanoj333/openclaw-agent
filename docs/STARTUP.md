# Daily startup — copy-paste cheat sheet

> Open this file every morning. Follow each block in its own PowerShell window. Total time: ~30 seconds.

For the full theory, see [`GUIDE.md`](GUIDE.md).

---

## 0. Prerequisites (assumes one-time setup is done)

- Code in `C:\Users\Manoj Kasula\Desktop\twilo\openclaw-agent`
- venv built, deps installed, `.env` filled, GCP key in `secrets/`
- Twilio webhooks pointing at `PUBLIC_BASE_URL` already
- VM proxy `vm_agent_proxy.py` already running on Azure VM
- ffmpeg in PATH

---

## Window 1 — SSH tunnel to the VM

```powershell
ssh -L 127.0.0.1:9000:127.0.0.1:9000 -o ServerAliveInterval=10 manoj@74.225.254.19X -N
```

After typing the password, the window goes silent. **That is success.** Don't close it.

---

## Window 2 — Postgres + Redis (Docker, runs in background)

```powershell
cd "$HOME\Desktop\twilo\openclaw-agent"
docker compose up -d
docker ps
```

Both containers should show `(healthy)`.

You only run this once per laptop boot. Skip if already running.

---

## Window 3 — uvicorn (the FastAPI gateway)

```powershell
cd "$HOME\Desktop\twilo\openclaw-agent"
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
```

Wait for:

```
INFO:     Uvicorn running on http://127.0.0.1:8080
```

Live log will keep printing here as messages arrive.

---

## Window 4 — ngrok (public HTTPS tunnel)

```powershell
ngrok http 8080
```

Copy the line that starts with `Forwarding https://...`.

If the URL changed since yesterday:
1. Update `PUBLIC_BASE_URL=...` in `.env` (uvicorn auto-reloads, but `.env` reload needs a restart — Ctrl+C + relaunch Window 3)
2. Update Twilio sandbox webhook (`/twilio/whatsapp`) to the new URL
3. Update Twilio voice number webhook (`/twilio/voice`) to the new URL

---

## Window 5 — health checks (run anytime)

```powershell
# tunnel + VM proxy
curl.exe -s http://127.0.0.1:9000/health

# uvicorn
curl.exe -s http://127.0.0.1:8080/health

# ngrok (replace with your URL)
curl.exe -s "https://radia-henotheistic-xxxxxxxx.ngrok-free.dev/health"
```

All three should return `{"status":"ok"}`. If any is wrong, jump to the [troubleshooting](GUIDE.md#12-troubleshooting-cookbook) section.

---

## How to stop everything

| What | How |
|------|-----|
| ngrok | Ctrl+C in Window 4 |
| uvicorn | Ctrl+C in Window 3 |
| Docker containers | `docker compose down` |
| SSH tunnel | Ctrl+C in Window 1 |
| Everything | close all windows; `docker compose down` |

---

## Common interaction patterns

### Made a code change → see it live

uvicorn `--reload` watches `.py` files. Save → restart is automatic. Watch Window 3 for `WatchFiles detected changes` then `Application startup complete`.

### Made an `.env` change → must restart uvicorn

`.env` is loaded once on startup. Ctrl+C uvicorn, relaunch.

### Want to test agent directly without WhatsApp

```powershell
$payload = @{ message = "What is 5+7?"; to = "+91xxxxxxxxx"; timeout = 60 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9000/agent -ContentType "application/json" -Body $payload -TimeoutSec 90
```

### See live ngrok request log

Open browser to `http://127.0.0.1:4040`. Inspector shows every webhook Twilio sent.
