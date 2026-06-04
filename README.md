# SupportPilot 🎯

An AI-powered customer support automation system built with a multi-agent architecture. Tickets come in, AI handles them — classifies, searches a knowledge base, drafts a reply, and either sends it automatically or escalates to a human based on confidence.

---

## 🎥 Demo Video

https://github.com/user-attachments/assets/37ff747c-14e6-479f-bef9-af3f625d63c9

---

## 📑 Table of Contents

- [What it does](#what-it-does)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Screenshots](#screenshots)
- [Agent Flow](#agent-flow)
- [Setup](#setup)
- [Usage](#usage)
- [Test Queries](#test-queries)
- [Logging](#logging)
- [Exception Handling](#exception-handling)
- [Cost](#cost)
- [Potential Improvements](#potential-improvements)
- [Author](#author)

---

## What it does

A customer submits a support ticket → the system automatically:

1. **Classifies** it (category, priority, sentiment) using Groq
2. **Searches** a FAQ knowledge base using ChromaDB (RAG)
3. **Looks up order status** if an order ID is mentioned
4. **Drafts a reply** using NVIDIA Nemotron via OpenRouter
5. **Routes** it — confidence ≥ 0.80 → auto-reply, else retry up to 2 times → escalate to human

Human agents only see the hard cases. The easy 80% is handled automatically.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph (StateGraph) |
| Classifier | Groq — `llama-3.3-70b-versatile` |
| Reply drafting | OpenRouter — `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| RAG / Vector DB | ChromaDB (local) |
| API | FastAPI |
| Database | SQLite |
| Frontend | Vanilla HTML/JS dashboard |

---

## Project Structure

```
supportpilot/
├── orchestrator/
│   ├── agent.py          # LangGraph StateGraph — 8 nodes, retry loop, routing
│   └── state.py          # TicketState TypedDict — shared memory across all nodes
│
├── tools/
│   ├── classify_ticket.py    # Tool 1 — Groq classifier (category, priority, sentiment)
│   ├── search_kb.py          # Tool 2 — ChromaDB RAG retrieval
│   ├── get_order_status.py   # Tool 3 — Mock order lookup (ORD-XXXX pattern)
│   ├── draft_reply.py        # Tool 4 — OpenRouter reply drafter + confidence score
│   └── send_reply.py         # Tool 5 — SQLite persistence + simulated email
│
├── knowledge_base/
│   ├── faqs.json         # 50 FAQ entries across 10 categories
│   └── ingest.py         # One-time script to load FAQs into ChromaDB
│
├── api/
│   ├── routes.py         # FastAPI endpoints (POST /ticket, GET /tickets, GET /ticket/:id)
│   └── models.py         # Pydantic request/response schemas
│
├── dashboard/
│   └── index.html        # Web UI — ticket submission form + live dashboard
│
├── logs/
│   └── supportpilot.log  # Rotating log file (5MB × 3 backups)
│
├── logger.py             # Centralised logger — colour console + file rotation
├── exceptions.py         # Custom exception hierarchy (12 specific error types)
├── main.py               # FastAPI app entry point
├── .env.example          # Environment variable template
└── requirements.txt      # Python dependencies
```

---

## Architecture

![SupportPilot Architecture](/docs/architecture.png)

---

## Screenshots

### Dashboard

![SupportPilot Dashboard](/docs/dashboard.png)

### Ticket Submission

![Submit a support ticket](/docs/submit_a_support_ticket.png)

### Escalated Ticket

![Escalated ticket view](/docs/Escalated.png)

---

## Agent Flow

```
Ticket (POST /api/ticket)
        ↓
[Node 1] classify      →  Groq: category + priority + sentiment
        ↓
[Node 2] search_kb     →  ChromaDB: top-3 relevant FAQ chunks (RAG)
        ↓
[Node 3] get_order     →  Mock API: order status if ORD-XXXX found in body
        ↓
[Node 4] draft         →  OpenRouter Nemotron: reply text + confidence score
        ↓
   confidence >= 0.80?
   ├── YES → [resolve] → auto-reply sent → [send] → SQLite saved
   ├── NO + retries left → [retry] → back to draft (max 2 retries)
   └── NO + exhausted → [escalate] → human queue + reason logged → [send]
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Inder-26/supportpilot.git
cd supportpilot
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

GROQ_MODEL=llama-3.3-70b-versatile
OPENROUTER_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

CONFIDENCE_THRESHOLD=0.80
MAX_RETRIES=2
LOG_LEVEL=INFO
```

Get your keys:
- Groq: https://console.groq.com
- OpenRouter: https://openrouter.ai

### 5. Ingest the knowledge base

```bash
python knowledge_base/ingest.py
```

This loads `faqs.json` into ChromaDB. Run this once before starting the server, and again any time you update `faqs.json`.

### 6. Start the server

```bash
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

---

## Usage

### Web UI

Open http://localhost:8000 — use the **Submit Ticket** tab to submit tickets and the **Dashboard** tab to view results.

### API (PowerShell)

```powershell
$body = '{"customer_email":"user@example.com","subject":"Where is my order ORD-1002?","body":"I placed order ORD-1002 three days ago and have not received any update.","source":"form"}'
Invoke-WebRequest -Uri "http://localhost:8000/api/ticket" -Method POST -ContentType "application/json" -Body $body
```

### API (curl)

```bash
curl -X POST http://localhost:8000/api/ticket \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "user@example.com",
    "subject": "Where is my order ORD-1002?",
    "body": "I placed order ORD-1002 three days ago and have not received any update.",
    "source": "form"
  }'
```

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ticket` | Submit a new ticket |
| GET | `/api/tickets` | List all tickets (filter by status, priority) |
| GET | `/api/ticket/:id` | Get full detail for one ticket including AI reply |
| GET | `/health` | Health check |

---

## Test Queries

Try these to see different behaviours:

**Resolves with order data (0.90–0.95 confidence):**
- Subject: `Where is my order ORD-1002?` / Body: `I placed order ORD-1002 three days ago and have not received any update.`

**Resolves from KB (0.80–0.90 confidence):**
- Subject: `How do I reset my password?` / Body: `I forgot my password and can't log into my account.`
- Subject: `I was charged twice` / Body: `My bank statement shows two charges for the same order.`
- Subject: `When will my parcel arrive?` / Body: `It has been two weeks since I placed the order.`

**Tests escalation path:**
- Subject: `This is completely unacceptable` / Body: `I am very angry and want to speak to a manager right now.`

---

## Logging

All logs go to:
- **Terminal** — colour-coded by level (green=INFO, yellow=WARNING, red=ERROR)
- **`logs/supportpilot.log`** — rotating file, 5MB per file, 3 backups kept

Filter logs for a specific ticket:

```powershell
# Windows
Select-String -Path "logs\supportpilot.log" -Pattern "TKT-XXXXXXXX"

# Mac/Linux
grep "TKT-XXXXXXXX" logs/supportpilot.log
```

---

## Exception Handling

Custom exception hierarchy in `exceptions.py`:

```
SupportPilotError (base)
├── GroqAPIError
├── GeminiAPIError          (reused for OpenRouter errors)
├── ModelTimeoutError
├── InvalidModelResponseError
├── KnowledgeBaseError
│   ├── KnowledgeBaseNotInitialisedError
│   └── NoRelevantChunksError
├── TicketValidationError
├── ClassificationError
├── ResolutionError
├── EscalationError
├── DatabaseError
└── ConfigurationError
```

Every tool raises specific exceptions. Nodes in `agent.py` catch them, log them to `TicketState.error_log`, and continue gracefully rather than crashing the pipeline.

---

## Cost

| Component | Cost |
|---|---|
| Groq (classifier) | Free tier — 6,000 requests/day |
| OpenRouter Nemotron | Free tier |
| ChromaDB | Free — runs locally |
| **Total for this project** | **$0** |

---

## Potential Improvements

- [ ] Real email sending via SendGrid or Gmail API
- [ ] Human agent close/resolve button on escalated tickets
- [ ] Swap ChromaDB for Qdrant Cloud for production scale
- [ ] Add authentication to the API
- [ ] Replace mock order API with real Shopify/WooCommerce integration
- [ ] Add more FAQ entries or connect to a live CMS

---

## Author

**Inderjeet Singh**  
AI Intern — Experiences Digital  
GitHub: [Inder-26](https://github.com/Inder-26)
