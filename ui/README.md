# Morpheus UI (Next.js)

Web frontend for the OpenClaw Twilio agent. Phone-OTP login (demo: any 6-digit
code printed in uvicorn log), live WebSocket feed of WhatsApp + voice + UI
messages, and inline composer that pipes through the same backend pipeline.

## Local dev

```bash
cd ui
cp .env.example .env.local        # point NEXT_PUBLIC_API_URL at your ngrok URL
npm install
npm run dev                       # http://localhost:3000
```

The FastAPI backend must be running and reachable at `NEXT_PUBLIC_API_URL`.
For dev:

- Backend on laptop:8080
- ngrok tunnel published as `NEXT_PUBLIC_API_URL`
- This UI on `http://localhost:3000`

## Deploy to Vercel

1. Push the repo (already done).
2. Vercel → New Project → import `rajumanoj333/openclaw-agent` → Root Directory `ui/`.
3. Set env vars:
   - `NEXT_PUBLIC_API_URL` = your stable ngrok URL or VM domain.
4. Deploy.

## Demo flow

1. Open `/login`, enter your WhatsApp number, click *Send code*.
2. Watch uvicorn log for the OTP (demo only — real Twilio Verify in prod).
3. Enter the code, click *Sign in*.
4. Land on `/chat`.
5. Now:
   - Send a WhatsApp text to your bot — it shows up in the web feed.
   - Make a phone call — voice transcript shows up.
   - Type in the composer — message goes through OpenClaw and reply lands in
     all three views.
