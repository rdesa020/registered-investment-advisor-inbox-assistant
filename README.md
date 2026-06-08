# RIA Inbox Assistant

AI-powered client email triage for boutique wealth advisory (RIA) firms.

**Live demo:** https://ria-inbox-assistant.onrender.com

---

## What it does

Paste or import messy client emails → Claude Haiku analyzes each one in parallel → get back urgency classification, client sentiment, planning areas, suggested advisor action, and a fiduciary-appropriate draft reply. Results stream in live. High-priority actions go into a task queue linked back to the original email.

## Stack

- **Backend:** FastAPI + Python, deployed on Render
- **AI:** Claude Haiku (`claude-haiku-4-5-20251001`) via Anthropic API
- **Frontend:** Vanilla HTML/CSS/JS, served from FastAPI
- **Processing:** Async parallel batching with `asyncio.gather`

## Run locally

**1. Clone the repo**
```bash
git clone https://github.com/rdesa020/registered-investment-advisor-inbox-assistant.git
cd registered-investment-advisor-inbox-assistant
```

**2. Set up backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Add your API key**
```bash
cp .env.example .env
# add your Anthropic API key to .env
```

**4. Run**
```bash
uvicorn main:app --reload
```

Open `http://localhost:8000` — the frontend loads automatically.

## Sample data

The `sample-data/` folder contains the Xylo AI Studios provided dataset — 14 messy client emails and a CRM-style export. Import the emails directly into the tool to see it in action.