# 💰 Money Manager

An AI-powered personal finance dashboard that reads your bank alert emails from Gmail, parses them using Gemini AI, and shows your spending in a beautiful dashboard.

---

## Features
- 📧 Reads bank alert emails from Gmail automatically
- 🤖 AI-powered parsing (Gemini) — extracts amount, merchant, date, category
- 📊 Dashboard with pie chart, trend chart, and transaction table
- 💵 Dedicated **Cash Savings** tab for unbanked/physical cash tracked via `.env`
- 🔍 Search and filter by date, category, type
- 📥 Export transactions to CSV

---

## Quick Setup (First Time)

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Configure AI Model (Google Gemini or Groq)
- **Option A (Google Gemini — Recommended):**
  1. Get an API key from https://aistudio.google.com/apikey
  2. In `.env`, set `AI_PROVIDER="gemini"` and add `GEMINI_API_KEY=...`

- **Option B (Groq Llama — Ultra Fast):**
  1. Get an API key from https://console.groq.com/keys
  2. In `.env`, set `AI_PROVIDER="groq"` and add `GROQ_API_KEY=gsk_...` (optionally `GROQ_MODEL=llama-3.3-70b-versatile`)

### Step 3 — Set up Gmail API
1. Go to https://console.cloud.google.com/
2. Create a new project (e.g., "MoneyManager")
3. Go to **APIs & Services** → **Enable APIs** → search and enable **Gmail API**
4. Go to **APIs & Services** → **Credentials**
5. Click **Create Credentials** → **OAuth 2.0 Client ID** → **Desktop app**
6. Download the JSON file → rename it to `credentials.json` → place it in the project root (`D:\Money_manager\`)
7. Go to **OAuth consent screen** → add your Gmail address as a **Test user**

### Step 4 — Run the dashboard
```bash
python -m streamlit run app/dashboard.py
```

On first launch, your browser will open for Gmail authorization. After that, it runs offline.

---

## Project Structure
```
D:\Money_manager\
├── app/
│   ├── dashboard.py       ← Main Streamlit UI
│   ├── sync.py            ← Fetch + parse + store emails
│   ├── email_reader.py    ← Gmail API connection
│   ├── ai_parser.py       ← Gemini AI email parser
│   ├── database.py        ← SQLite storage
│   └── categories.py      ← Category definitions
├── data/
│   └── transactions.db    ← Your local database (auto-created)
├── credentials.json       ← Gmail OAuth (you download this)
├── .env                   ← Your API keys
├── requirements.txt
└── README.md
```

---

## Manual Sync (without UI)
```bash
python app/sync.py
```

---

## Updating your bank sender email
Open `.env` and change:
```
BANK_EMAIL_SENDER=alerts@yourbank.com
```
