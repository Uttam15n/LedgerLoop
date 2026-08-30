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

# 6. How It Works

### Step 1

Upload your own invoice / payment / bank transaction files, or generate a synthetic test batch.

↓

### Step 2

Data is schema-validated and staged into a SQLite database.

↓

### Step 3

The deterministic matcher scores every possible pair on reference match, amount match, date proximity, and text similarity — then resolves a one-to-one assignment across the whole batch at once.

↓

### Step 4

Records the deterministic pass couldn't confidently resolve are escalated to the LangGraph agent chain.

↓

### Step 5

A router agent decides what's missing; a search agent queries the database through read-only, parameterized tools; a reasoning agent (Groq) decides the final outcome with a confidence score and a plain-English justification.

↓

### Step 6

Every record lands in exactly one bucket — auto-approved, human review, or a categorized exception — compiled into a downloadable report.

---

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

<!-- <img width="1588" alt="Dashboard" src="docs/screenshots/dashboard.png" /> -->

---

## Reconciliation Report

<!-- <img width="1588" alt="Reconciliation report" src="docs/screenshots/reconciliation-report.png" /> -->

---

## Verify a Single Invoice

<!-- <img width="1588" alt="Verify single invoice" src="docs/screenshots/verify-single-invoice.png" /> -->

---

## Chat Assistant

<!-- <img width="1588" alt="Chat assistant" src="docs/screenshots/chat-assistant.png" /> -->

---

---

# 📈 Learning Outcomes

This project strengthened my understanding of:

- Deterministic vs. agentic system design, and when to use which
- LangGraph stateful agent workflows
- Secure tool-calling design (parameterized queries, whitelisting, prompt-injection defense)
- One-to-one bipartite assignment for record matching
- Confidence scoring and honest exception reporting
- LLM orchestration with Groq
- Building a real multi-page Streamlit product, not just a script

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

