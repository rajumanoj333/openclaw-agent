# Roadmap — multi-channel marketing agent

> Demo target. Phase 1 (poster designer) is live in `main`. Remaining phases are
> sequenced for fastest visible progress.

## Where we are now

```
   ✅ Phase 0   WhatsApp text + voice notes + voice calls (bilingual)
   ✅ Phase A   Business URL onboarding (scrape → brand kit → JSON profile)
   ✅ Phase 1   Poster designer (Gemini Nano Banana, brand-aware)
   ⏳ Phase 2   Frontend chat UI (Next.js + WebSocket)
   ⏳ Phase 3   Multi-channel sync (UI + WhatsApp + voice = one thread)
   ⏳ Phase 4   Composio Instagram (post + analytics)
   ⏳ Phase 5   Marketing-campaign agent (multi-step plans, scheduler)
```

---

## Phase 1 — Poster designer ✅

**What it does**
Whenever a WhatsApp text matches the poster intent ("make me a poster for X",
"design a creative", "create flyer for Y"), we look up the user's saved
business profile, build a brand-aware prompt, and call Gemini's Nano Banana
image model. The result is saved to `data/audio/<uuid>.png` and sent back as
WhatsApp media.

**Files**
- `app/services/poster.py` — Gemini call + prompt builder
- `app/services/intent.py` — rule-based intent classifier
- `app/routes/whatsapp.py` — wiring, `_process_poster()` background task
- `app/routes/audio.py` — serves PNG/JPG along with audio

**Demo command**
After running onboarding once, send:
```
make a poster for Diwali 50% off
```
Expect ack message + poster image arriving 15-25 sec later.

---

## Phase 2 — Frontend chat UI

**Goal:** A web app where the user can:
- See the same WhatsApp conversation live
- See voice-call transcripts as they happen
- Send messages (forwarded to OpenClaw same as WhatsApp)
- Watch task status (scraping…, designing…, posting…)
- View a sidebar of recent posters

**Stack**
- Next.js 15 (App Router) + Tailwind + shadcn/ui
- Auth: Twilio Verify (phone OTP) → JWT
- Real-time: native WebSockets to FastAPI
- Deploy: Vercel (free, instant)

**Backend additions**
```
app/routes/auth.py        # POST /auth/start, POST /auth/verify (phone OTP)
app/routes/ws.py          # GET /ws/{phone}  WebSocket endpoint
app/services/ws_hub.py    # in-process pub/sub (later: Redis)
app/services/auth.py      # JWT issue/verify
```

**Frontend folder layout**
```
ui/
├── app/
│   ├── (auth)/login/page.tsx
│   ├── (app)/chat/page.tsx
│   └── api/...
├── components/
│   ├── chat-thread.tsx
│   ├── message-bubble.tsx       (channel-tagged: WA / Voice / UI)
│   ├── status-pill.tsx           (Scraping... / Designing... / Posting...)
│   ├── poster-gallery.tsx
│   └── brand-kit-card.tsx
├── lib/
│   ├── api.ts                    (fetch wrapper)
│   └── ws.ts                     (WebSocket client)
└── package.json
```

**Time:** 5-7 days for solid version, 2 days for ugly demo.

---

## Phase 3 — Multi-channel sync

**Goal:** every inbound/outbound message — regardless of source — appears in
all connected views in the right order.

**Mechanism**
1. New `messages` table in Postgres:
   ```sql
   id, user_phone, channel(wa|voice|ui), direction(in|out),
   body, media_url, lang, created_at
   ```
2. Every send_whatsapp / send_whatsapp_media / TTS playback writes a row.
3. After insert, publish to Redis: `user:<phone>:msg`.
4. WebSocket handler subscribes per user, forwards to UI.

**Files**
```
app/db/                   # SQLAlchemy + Alembic
   models.py
   migrations/
app/services/messages.py  # save() + publish()
app/services/redis_pubsub.py
```

**Replace** the in-memory `voice_session.py` with the same Redis store
(survives restart).

**Time:** 4-5 days.

---

## Phase 4 — Composio Instagram

**Goal:** Bot can post images + captions to user's Instagram on their behalf,
read back analytics, and schedule posts.

**Composio quickstart**
```python
from composio_core import ComposioToolSet, App

toolset = ComposioToolSet(api_key=settings.composio_api_key)
toolset.initiate_connection(app=App.INSTAGRAM)   # OAuth URL → user clicks
```

After OAuth: token is stored on Composio side.

**Tools we register with the agent**
- `instagram.create_post(image_url, caption)`
- `instagram.schedule_post(image_url, caption, when_iso)`
- `instagram.recent_posts_analytics(limit=10)`

**Permission flow on WhatsApp**
```
Bot: I'm about to post this poster to Instagram with caption:
       "Diwali sale — 50% off all sweets! 🪔"
     Reply YES to publish, NO to edit, EDIT <new caption> to change.
You: yes
Bot: Posted ✅  → https://instagram.com/p/xxx
     Analytics will arrive in 24h.
```

**Files**
```
app/services/composio_client.py
app/services/intent.py            # add 'post_now' / 'edit_caption' / 'schedule'
app/routes/whatsapp.py            # add pending-action state machine
```

**Files added on UI:**
- "Connect Instagram" button → starts OAuth → returns to /chat with success toast
- Pending-action confirm card

**Time:** 7-10 days. Most of it is OAuth UX + edge cases.

---

## Phase 5 — Marketing campaign agent

**Goal:** multi-step plans that run for days.

**Example user flow**
```
You: Run a 1-week Diwali campaign on Instagram. Post one creative per day.
Bot: Plan:
       Day 1 — gold/red lamp poster, "Light up your home"
       Day 2 — sweets close-up, "Mithai box at 50% off"
       Day 3 — family scene, "Festive moments"
       ...
     Tap CONFIRM to run. Edit plan? Reply with day numbers + changes.
You: confirm
Bot: 🟢 Running. Day 1 posts at 9am tomorrow. Updates here.

(next day, 9am)
Bot: Day 1 posted ✅ → https://instagram.com/p/abc
     Day 2 designed (preview attached). Auto-posting at 9am unless you reply STOP.
```

**Architecture**
- New table `campaigns(id, user_phone, status, plan_json, created_at)`
- New table `campaign_tasks(id, campaign_id, day, status, scheduled_for, payload, result)`
- APScheduler runs in-process (or separate worker)
- Each task = call to `_process_poster()` + `composio.create_post()` + log

**Files**
```
app/services/campaigns.py
app/services/scheduler.py   # APScheduler wired with FastAPI
app/db/models.py            # add campaigns + campaign_tasks
```

**Time:** 10-14 days.

---

## What you provide

| Item | Status | When |
|------|--------|------|
| Twilio account + verified numbers | ✅ done | now |
| Sarvam API key | ✅ in .env | now |
| Google Cloud STT/TTS key | ✅ in secrets/ | now |
| Gemini API key | ⏳ pending | Phase 1 testing |
| Composio API key | ⏳ pending | Phase 4 |
| Composio Instagram OAuth completed | ⏳ pending | Phase 4 |
| Vercel account | ⏳ Phase 2 | Phase 2 deploy |
| Domain for production (optional) | ⏳ later | post-demo |

---

## Order of work — recommended sprint

```
  Day 1-2   Phase 1 demo: drop Gemini key, test poster end-to-end on WhatsApp
  Day 3-4   Phase 2 scaffold: Next.js app + login screen + chat UI (mock data)
  Day 5-7   Phase 2 wire: WebSocket from FastAPI → live messages
  Day 8-10  Phase 3: messages table + Redis pub/sub + voice_session migration
  Day 11    Phase 1 polish: input image (use logo as ref), retry/edit flow
  Day 12-15 Phase 4: Composio Instagram OAuth + post tool + permission UX
  Day 16+   Phase 5 if time permits, else demo prep
```

**Realistic demo-ready in 2 weeks** with one person focused.

---

## What you can demo at each milestone

| After phase | Demo story |
|-------------|------------|
| 1 (today) | "User shares URL → I extract their brand → I generate posters in their colors" |
| 2 | "Same conversation visible in browser AND WhatsApp at the same time" |
| 3 | "Voice call in, transcript appears in browser live, agent reply pushed to both" |
| 4 | "Bot publishes to Instagram on user's behalf — full caption + image + analytics back" |
| 5 | "Hands-off campaigns — set it and forget it, daily posts auto-publish" |

Each phase = standalone demo. You can stop at any phase and still have something
impressive to show.
