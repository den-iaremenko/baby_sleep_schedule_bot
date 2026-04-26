# Baby Sleep Schedule Bot

An intelligent baby sleep tracking and scheduling system that grows from a simple Telegram bot into a fully automated sleep monitoring platform.

## Overview

Healthy sleep is critical for infant development, but calculating optimal nap times throughout the day is tedious and easy to get wrong. This project solves that by providing parents with an accurate, age-appropriate daily sleep schedule — and over time, learns from the baby's actual sleep patterns to make it even more precise.

---

## Roadmap

### Phase 1 — Telegram Bot: Daily Schedule Generator

**Goal:** Give parents an instant, science-based sleep schedule for the day with a single message.

**How it works:**
- Parent sends the baby's morning wake-up time to the Telegram bot
- The bot builds a full day plan using a fixed two-nap schedule structure:

```
Wake → 2h 10m → Nap 1 (1h) → 2h 50m → Nap 2 (1h) → 2h 50m → Night sleep
```

- Each awake window is split into two phases:
  - **70% active time** — play, stimulation, feeding
  - **30% wind-down time** — calm activities to prepare for sleep

**Example output for 07:00 wake-up:**
```
🌅 Wake up: 07:00

⚡ Active:     07:00 – 08:31 (1h 31m)
😌 Wind down:  08:31 – 09:10 (39m)
😴 Nap 1:      09:10 – 10:10 (1h)

⚡ Active:     10:10 – 12:09 (1h 59m)
😌 Wind down:  12:09 – 13:00 (51m)
😴 Nap 2:      13:00 – 14:00 (1h)

⚡ Active:     14:00 – 15:59 (1h 59m)
😌 Wind down:  15:59 – 16:50 (51m)
🌙 Night sleep: 16:50
```

**Key features:**
- Single-input UX: just send the wake-up time
- Structured 70/30 active/wind-down split per awake window
- Clean, readable schedule output

**Stack:** Python, python-telegram-bot, Docker, Docker Compose

---

### Phase 2 — Sleep Records & Historical Analysis

**Goal:** Track the baby's actual sleep against the schedule and surface trends over time.

**How it works:**
- Parents log actual sleep and wake events via the Telegram bot (e.g., `/slept 14:05`, `/woke 15:40`)
- Records are persisted to a database
- Parents can query summaries and trends via bot commands (e.g., `/summary today`, `/weekly`)

**Key features:**
- Store timestamped sleep/wake events per baby
- Daily and weekly summaries: total sleep, number of naps, average nap duration
- Deviation tracking: how much actual sleep differed from the generated schedule
- Foundation for future ML-based schedule refinement

**Stack:** Python, python-telegram-bot, PostgreSQL (via SQLAlchemy), Docker, Docker Compose

---

### Phase 3 — Automated Camera Monitoring & Adaptive Scheduling

**Goal:** Remove manual logging entirely — the system watches the baby and updates the schedule automatically.

**How it works:**
- A camera monitors the baby's room (crib camera or standard webcam)
- A local server runs a computer vision model that detects sleep state changes (awake vs. asleep) from the video feed
- Sleep/wake events are written to the database automatically, eliminating manual bot input
- The scheduler analyzes accumulated real sleep data to adjust future schedule recommendations to the baby's actual patterns
- Parents receive Telegram notifications when the baby falls asleep or wakes up

**Key features:**
- Real-time sleep state detection (computer vision, pose/motion analysis)
- Automatic DB record creation on state change
- Adaptive scheduling: wake windows and nap durations tuned per baby using historical data
- Wake-up alerts pushed via Telegram
- Privacy-first: all video processing runs locally, no footage leaves the home network

**Stack:** Python, OpenCV / MediaPipe (or lightweight CNN), FastAPI (local server), PostgreSQL, python-telegram-bot, Docker, Docker Compose

---

## Infrastructure

All components run as Docker containers orchestrated with Docker Compose. Each phase adds new services to the same `docker-compose.yml`:

| Phase | Services added |
|-------|---------------|
| 1 | `bot` |
| 2 | `bot`, `db` (PostgreSQL) |
| 3 | `bot`, `db`, `monitor`, `server` |

Each service has its own `Dockerfile`. A single `docker compose up` starts everything.

---

## Project Structure (planned)

```
baby_sleep_schedule_bot/
├── bot/                  # Telegram bot
│   ├── Dockerfile
│   ├── handlers/         # Command and message handlers
│   └── scheduler.py      # Wake window & schedule calculation
├── db/                   # Database models and migrations
├── monitor/              # Phase 3: camera + CV sleep detection
│   └── Dockerfile
├── server/               # Phase 3: local API server
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Getting Started

```bash
cp .env.example .env   # fill in your Telegram bot token and other secrets
docker compose up
```

_Full setup instructions will be added as each phase is implemented._

---

## License

MIT © Denys Iaremenko
