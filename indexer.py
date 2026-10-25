"""
Indexer — parses course PDFs into pages and stores them in SQLite.

Responsibilities:
  • Extract text from every page of each PDF (via pdfplumber).
  • Persist (doc_name, page_num, text) in an SQLite database.
  • Build an in-memory BM25 index for fast retrieval at query time.

The BM25 index is rebuilt from the database on startup so the SQLite
store is the single source of truth.
"""

import os
import sqlite3
import re
import math
import hashlib
from collections import Counter, defaultdict
from datetime import datetime

import config
from retriever import BM25Index


# -- helpers ----------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lower-case, split on non-alphanumeric, keep tokens of length >= 1."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _file_version(path: str) -> str:
    """Short md5 prefix as a 'version' stamp for staleness tracking."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:8]


# -- database ---------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_name    TEXT    NOT NULL,
    page_num    INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    version     TEXT,
    indexed_at  TEXT    NOT NULL,
    UNIQUE(doc_name, page_num)
);

CREATE TABLE IF NOT EXISTS saved_qa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT    NOT NULL,
    answer      TEXT    NOT NULL,
    sources     TEXT,
    saved_at    TEXT    NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# -- indexing ---------------------------------------------------------

def index_pdf(path: str, conn: sqlite3.Connection) -> int:
    """Parse a single PDF, store its pages in SQLite. Returns page count."""
    import pdfplumber

    doc_name = os.path.basename(path)
    version = _file_version(path)
    now = datetime.now().isoformat(timespec="seconds")
    page_count = 0

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue
            conn.execute(
                "INSERT INTO pages (doc_name, page_num, text, version, indexed_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(doc_name, page_num) DO UPDATE SET "
                "  text=excluded.text, version=excluded.version, indexed_at=excluded.indexed_at",
                (doc_name, i + 1, text, version, now),
            )
            page_count += 1
    conn.commit()
    return page_count


def index_all() -> dict:
    """Index every PDF in the data/ directory. Safe to call repeatedly."""
    conn = get_db()
    results = {}
    if not os.path.isdir(config.DATA_DIR):
        os.makedirs(config.DATA_DIR, exist_ok=True)

    for fname in sorted(os.listdir(config.DATA_DIR)):
        if not fname.lower().endswith(".pdf"):
            continue
        path = os.path.join(config.DATA_DIR, fname)
        try:
            n = index_pdf(path, conn)
            results[fname] = f"{n} pages"
        except Exception as e:
            results[fname] = f"ERROR: {e}"
    conn.close()
    return results


def get_index_status() -> list[dict]:
    """Return a list of {doc_name, pages, version} for display."""
    conn = get_db()
    rows = conn.execute(
        "SELECT doc_name, COUNT(*) as pages, MAX(version) as version "
        "FROM pages GROUP BY doc_name ORDER BY doc_name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_bm25_index() -> BM25Index:
    """Load all pages from SQLite and build an in-memory BM25 index."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, doc_name, page_num, text, version FROM pages ORDER BY id"
    ).fetchall()
    conn.close()

    index = BM25Index(k1=config.BM25_K1, b=config.BM25_B)
    for r in rows:
        index.add_document(
            doc_id=r["id"],
            text=r["text"],
            metadata={
                "doc_name": r["doc_name"],
                "page_num": r["page_num"],
                "version": r["version"],
                "text": r["text"],
            },
        )
    index.finalize()
    return index


# -- saved Q&A -------------------------------------------------------

def save_qa(question: str, answer: str, sources_json: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO saved_qa (question, answer, sources, saved_at) VALUES (?, ?, ?, ?)",
        (question, answer, sources_json, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_saved_qa() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM saved_qa ORDER BY saved_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
