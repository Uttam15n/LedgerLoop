# AuditAgent — AI Finance Controller

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic-orange)
![LangChain](https://img.shields.io/badge/LangChain-Tool_Calling-green)
![Groq](https://img.shields.io/badge/LLM-Groq-black)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b)
![SQLAlchemy](https://img.shields.io/badge/Database-SQLite-4169E1)
![Pandas](https://img.shields.io/badge/Data-Pandas-150458)

</p>

---

# 1. Overview

AuditAgent is a multi-source finance reconciliation system that closes a real finance-ops loop: matching **invoices**, **UPI payments**, and **bank transactions** against each other to verify which ones genuinely settle — and honestly reporting which ones don't.

Unlike a single LLM pass over every record, this application uses a **two-phase hybrid design**: a fast, deterministic matcher (pure pandas, zero LLM cost) resolves the easy majority instantly, and an **Agentic workflow powered by LangGraph** only picks up the records that are genuinely ambiguous — deciding what to search for, querying the database through locked-down read-only tools, and reasoning about whether it found a real match.

The project integrates **LangGraph**, **LangChain**, **Groq**, **SQLAlchemy + SQLite**, and **Streamlit** to deliver bulk reconciliation, single-record verification, and a conversational Settlement Q&A assistant — all grounded in the same real, staged data.

> Verification capacity, not generation speed, is the actual bottleneck in finance ops. This project is built around that idea.

---

# 2. Features

- 📥 Generate synthetic test data, or upload your own invoice / payment / bank transaction data (CSV, XLSX, or a single multi-sheet Excel workbook)
- ⚡ Deterministic matching engine — reference, amount, date, and text scoring with proper one-to-one assignment (correctly catches duplicate candidates)
- 🤖 LangGraph agent chain — router → search → reasoning, only for records the deterministic pass couldn't resolve
- 🔒 Read-only, parameterized search tools — no open-ended SQL, no injection surface, tested against adversarial data
- 📊 Categorized exception reporting — every unresolved record has a plain-English reason, not a silent failure
- 🔍 Verify any single invoice on demand, with full transparency into the agent's reasoning
- 💬 Settlement Q&A chat assistant, grounded in the real staged data
- 🖥️ Dark-mode, multi-page Streamlit interface
- 📄 Downloadable CSV report

---

# 3. System Architecture

```mermaid
flowchart TD

A[Data Sources: Invoice, Payment, Bank Transaction]
B[Ingestion and Validation]
C[Deterministic Matcher]
D[Router Agent]
E[Search Agent - Read-only, Parameterized SQL]
F[Reasoning Agent - Groq]
G[Aggregator and Report]
H[Auto-Approved]
I[Human Review]
J[Exception]

A --> B
B --> C
C -->|auto-matched| G
C -->|ambiguous or no match| D
D --> E
E --> F
F --> G
G --> H
G --> I
G --> J
```

The reconciliation relationship itself is two hops:

```mermaid
flowchart LR
    INV[Invoice] -->|Hop 1| PAY[Payment]
    PAY -->|Hop 2| BANK[Bank Transaction]
```

An invoice only counts as **fully reconciled** once both hops are confidently linked.

---

# 4. Workflow

```mermaid
sequenceDiagram
    participant User
    participant Streamlit
    participant Matcher as Deterministic Matcher
    participant DB as SQLite Database
    participant Router as Router Agent
    participant Search as Search Agent
    participant Reasoning as Reasoning Agent (Groq)

    User->>Streamlit: Upload / generate data
    Streamlit->>DB: Validate and load

    User->>Streamlit: Click "Run Reconciliation"
    Streamlit->>Matcher: Run deterministic matching
    Matcher->>DB: Read invoice, payment, bank records
    Matcher-->>Streamlit: Auto-matched + escalated records

    loop For each escalated record
        Streamlit->>Router: Decide search target
        Router->>Search: Route to payment / bank_transaction
        Search->>DB: Parameterized, read-only query
        DB-->>Search: Candidate records
        Search->>Reasoning: Candidates + Phase 2 context
        Reasoning->>Groq: Reasoning prompt
        Groq-->>Reasoning: Confidence + justification
        Reasoning-->>Streamlit: Final status
    end

    Streamlit-->>User: Report + downloadable CSV
```

---

# 5. Tech Stack

| Category | Technologies |
|----------|--------------|
| Language | Python |
| Agent Framework | LangGraph |
| Tool Calling | LangChain |
| LLM | Groq (`openai/gpt-oss-120b`) |
| Database | SQLite + SQLAlchemy |
| Data Handling | pandas |
| File I/O | openpyxl |
| UI | Streamlit |
| Environment | Python Virtual Environment |

---

# 6. Installation

Clone the repository

```bash
git clone https://github.com/Uttam15n/AuditAgent.git

cd AuditAgent
```

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Linux / Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -e ".[agents]"
```

---

# 7. Environment Variables

Create a `.env` in the project root

```text
GROQ_API_KEY=
```

Get a free key at [console.groq.com](https://console.groq.com).

---

# 5. Run Application

```bash
streamlit run app/streamlit_app.py
```

Or run the full pipeline standalone, no UI, straight to console:

```bash
python run_full_pipeline.py
```

---

## 6. How It Works

The system follows a **deterministic-first, agent-assisted reconciliation pipeline**:

```text
┌─────────────────────────────────────────────────────────────┐
│  1. UPLOAD / GENERATE DATA                                  │
│                                                             │
│  Upload invoices, payments, or bank transactions —          │
│  or generate a synthetic test batch.                        │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  2. VALIDATE & STAGE                                        │
│                                                             │
│  Input data is schema-validated and staged into SQLite      │
│  for consistent and reliable processing.                    │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  3. DETERMINISTIC MATCHING                                  │
│                                                             │
│  Every possible pair is scored using:                       │
│    • Reference / ID match                                   │
│    • Amount match                                           │
│    • Date proximity                                         │
│    • Text similarity                                        │
│                                                             │
│  A global one-to-one assignment resolves the batch          │
│  instead of making independent record-level decisions.      │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │ Confidently resolved?│
                    └──────────┬───────────┘
                         YES ↙     ↘ NO
                            ↓       ↓
                 ┌──────────────┐   ┌─────────────────────────┐
                 │ AUTO-APPROVED│   │ 4. AGENT ESCALATION     │
                 └──────────────┘   │                         │
                                    │ Unresolved records are  │
                                    │ passed to the LangGraph │
                                    │ agent chain.            │
                                    └────────────┬────────────┘
                                                 ↓
┌─────────────────────────────────────────────────────────────┐
│  5. AGENTIC INVESTIGATION                                   │
│                                                             │
│  Router Agent                                               │
│       ↓                                                     │
│  Identifies what information is missing                     │
│       ↓                                                     │
│  Search Agent                                               │
│       ↓                                                     │
│  Queries SQLite using read-only, parameterized tools        │
│       ↓                                                     │
│  Reasoning Agent (Groq)                                     │
│       ↓                                                     │
│  Determines the final outcome, confidence score,            │
│  and plain-English justification.                           │
└──────────────────────────────┬──────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────┐
│  6. FINAL CLASSIFICATION & REPORTING                        │
│                                                             │
│  Every record is assigned to exactly one outcome:           │
│                                                             │
│     ✓ Auto-Approved     ⚠ Human Review    ✕ Exception      |
│                                                             │
│  Results are compiled into a downloadable reconciliation    │
│  report with the decision, confidence, and reasoning.       │
└─────────────────────────────────────────────────────────────┘
```

### Processing Philosophy

**Deterministic first → Agentic reasoning only when needed**

The system does not send every record to an LLM. Straightforward matches are resolved using deterministic scoring, while only ambiguous or unresolved cases are escalated to the agentic workflow. This keeps the reconciliation process **efficient, explainable, and controlled**.


# 7. Security Design

The agent chain never has open-ended database access:

- **Three fixed, parameterized tools only** — `search_by_reference`, `search_by_amount_range`, `search_by_date_range`. The LLM never writes raw SQL.
- **Whitelisted tables and columns**, checked before any query is built.
- **Parameterized values, always** — SQL injection is structurally impossible, not just discouraged.
- **A genuinely read-only database connection** — opened via `mode=ro` at the SQLite driver level.
- **Prompt-injection tested** — the reasoning agent is instructed to treat any free-text field as untrusted data, never instructions, and this was verified against records deliberately containing injected commands.

---

# 8. Screenshots

> Add your own screenshots here after running the app locally — save them into a `docs/screenshots/` folder and reference them below.

## Dashboard

<img width="1917" height="957" alt="Screenshot 2026-08-30 152424" src="https://github.com/user-attachments/assets/c7d1cc2a-11a1-46c3-855c-8237bb981d1d" />


---

## Reconciliation Dashboard

<img width="1916" height="962" alt="Screenshot 2026-08-30 152910" src="https://github.com/user-attachments/assets/d354a66c-c3db-4b68-9f19-62fb7d0fe7a5" />


---

## Reconciliation Report

<img width="1915" height="953" alt="Screenshot 2026-08-30 152944" src="https://github.com/user-attachments/assets/22079a4b-adf6-4ee8-8a8f-171e640da973" />

---

## Chat Assistant

<img width="1917" height="963" alt="Screenshot 2026-08-30 153410" src="https://github.com/user-attachments/assets/d66602a9-70a0-4bb2-9c04-ddb2b0874932" />

---
# 9. Author

**Uttam N**

Final Year Computer Science (Cyber Security)

Passionate about

- Software Engineering
- Artificial Intelligence
- Generative AI
- Agentic AI Systems
- Large Language Models

---

