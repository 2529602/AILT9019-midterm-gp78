# AILT9019 Course Q&A — RAG System

A retrieval-augmented generation (RAG) app that lets AILT9019 students ask
natural-language questions about course concepts, project requirements,
procedures, and deadlines. Answers are grounded in the course PDFs with
document/page citations.

> **Not an official course authority.** Answers are informational. Always
> verify deadlines and requirements on Moodle or with course staff.

---

## Quick Start

### Option A — Windows (double-click)

1. Put your course PDFs in the `data/` folder.
2. Double-click **`install.bat`** (first time only).
3. Double-click **`start.bat`** — the app opens in your browser.

### Option B — Command line (any OS)

```bash
cd ailt9019-qa
python -m pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:8765> in your browser.

---

## Prerequisites

- Python 3.10+
- One pip package: `pdfplumber` (listed in `requirements.txt`)
- (Optional) A DeepSeek API key for AI-generated answers, or Ollama for
  offline LLM — see [LLM Setup](#llm-setup-optional) below.

---

## Project Structure

```
ailt9019-qa/
├── app.py               # Main entry: HTTP server + route handlers
├── config.py            # All configuration (paths, port, LLM settings)
├── indexer.py            # PDF parsing → SQLite storage + BM25 index builder
├── retriever.py         # BM25 retrieval (implemented from scratch)
├── llm.py               # LLM answer drafting (DeepSeek / Ollama) + citations
├── safety.py            # Safe-failure / refusal logic (4 cases)
├── run_tests.py         # Evaluation runner for test cases
├── static/
│   └── index.html       # Single-page frontend (HTML + JS)
├── data/                # Put course PDFs here
├── evaluation_cases.csv # 8 test cases (4 normal, 4 safe-failure)
├── requirements.txt
├── install.bat          # Windows one-time install
├── start.bat            # Windows launch (opens browser)
└── README.md
```

---

## How It Works

```
Question → BM25 retrieval (top-k passages) → Safety check → LLM answer (optional) → Answer + [S1][S2] citations
```

1. **Indexing**: Course PDFs in `data/` are parsed page-by-page with
   `pdfplumber` and stored in a SQLite database (`ailt9019_qa.db`).
2. **Retrieval**: On each question, the BM25 algorithm (implemented in
   `retriever.py` with no external dependency) scores all pages and returns
   the top-k most relevant.
3. **Safety check**: Before answering, `safety.py` checks for four
   safe-failure cases (see below). If a case is triggered, the app refuses
   and redirects the student appropriately.
4. **Answer drafting**: If an LLM is configured, `llm.py` sends the top
   passages to DeepSeek/Ollama with a prompt instructing it to cite sources
   with `[S1]`, `[S2]` markers. If no LLM is available, the app falls back
   to excerpting the top passages directly.

---

## API Endpoints

| Method | Path           | Description                              |
|--------|----------------|------------------------------------------|
| GET    | `/`            | Serve the frontend page                   |
| GET    | `/api/status`  | Index status (indexed docs, page count)  |
| POST   | `/api/answer`  | `{question}` → answer + cited sources    |
| POST   | `/api/upload`  | Upload a PDF (multipart) → index it      |
| POST   | `/api/save`    | Save a Q&A pair                           |
| GET    | `/api/saved`   | List saved Q&A pairs                      |

---

## Safe-Failure Cases

The app is designed to fail safely in four scenarios:

| # | Scenario                         | Behaviour                                    |
|---|----------------------------------|----------------------------------------------|
| 1 | Question not in indexed materials | Says it cannot verify; directs to Moodle    |
| 2 | Possible stale deadline          | Directs to Moodle rather than presenting date |
| 3 | Extension / grading request     | Declines; refers to course staff             |
| 4 | Off-topic request                | Declines; steers back to course questions    |

---

## Evaluation

Run the test suite (server must be running):

```bash
python run_tests.py            # summary
python run_tests.py --verbose  # full answers
```

**Pass threshold**: at least 7 of 8 cases. Results are saved to
`test_log.json`.

---

## LLM Setup (optional)

Without an LLM, the app still works — it retrieves passages and excerpts
them. To get AI-generated answers:

### DeepSeek (default, needs API key)

1. Get an API key from <https://platform.deepseek.com>
2. Set environment variables:

```bash
# Windows (cmd)
set LLM_PROVIDER=deepseek
set DEEPSEEK_API_KEY=sk-your-key-here

# Linux/macOS
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=sk-your-key-here
```

3. Restart `python app.py`.

### Ollama (offline, no API key)

1. Install Ollama: <https://ollama.com>
2. Pull a model: `ollama pull llama3`
3. Set environment:

```bash
set LLM_PROVIDER=ollama
```

4. Restart `python app.py`.

**Data handling**: The API key is never written to disk. It is read from
the environment at runtime and sent only with the current request. With
an external model (DeepSeek), the question and retrieved excerpts go to
that provider. With a local model (Ollama), requests stay on your
computer.

---

## Sample Questions

- "What sections are required in the project proposal?"
- "When is the proposal deadline?"
- "What are the presentation or demo requirements?"
- "What is the personal data policy?"
- "Can you grant me an extension?" *(safe-failure)*
- "What is the medical diagnosis for my symptoms?" *(safe-failure)*

---

## Known Limits

- Only PDFs placed in `data/` (or uploaded via the UI) are indexed.
- Retrieval is BM25 (keyword-based); semantic understanding depends on the LLM.
- The indexed materials may be stale — always check Moodle for current dates.
- The app does not store questions by default (unless you click "Save").

---

## How to Refresh the Index

1. Add or remove PDFs in the `data/` folder.
2. Upload via the UI (Upload & Index button), **or** restart `python app.py`.
3. The SQLite database is rebuilt on startup.

---

## Moodle Authority Note

This app is a student-built demonstration of RAG concepts. It is **not** an
official course tool. For authoritative information about deadlines,
requirements, and decisions, always refer to the AILT9019 Moodle page or
contact the teaching team directly.
