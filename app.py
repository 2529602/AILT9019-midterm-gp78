"""
AILT9019 Course Q&A — main application server.

Uses Python's standard-library http.server so the only pip
dependency is pdfplumber (for PDF parsing in the indexer).

Endpoints:
  GET  /              → serve the single-page frontend
  GET  /api/status    → index status (which docs are indexed)
  POST /api/answer    → {question} → answer + cited sources
  POST /api/upload    → multipart PDF upload → index it
  GET  /api/saved     → list saved Q&A pairs
  POST /api/save      → save a Q&A pair
"""

import os
import re
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import config
import indexer
import retriever
import llm
import safety

# Build the BM25 index once at startup (rebuilt on demand)
_BM25_INDEX = None


def get_index() -> retriever.BM25Index:
    global _BM25_INDEX
    if _BM25_INDEX is None or _BM25_INDEX.page_count == 0:
        _BM25_INDEX = indexer.build_bm25_index()
    return _BM25_INDEX


def refresh_index():
    """Rebuild the in-memory index from SQLite (call after indexing new PDFs)."""
    global _BM25_INDEX
    _BM25_INDEX = indexer.build_bm25_index()
    return _BM25_INDEX


# -- request handler -------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # quieter logging
        pass

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._send_json(404, {"error": "index.html not found"})

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._send_html(os.path.join(config.STATIC_DIR, "index.html"))

        elif path == "/api/status":
            status = indexer.get_index_status()
            idx = get_index()
            self._send_json(200, {
                "indexed_docs": status,
                "total_pages": idx.page_count,
                "llm_provider": config.LLM_PROVIDER,
            })

        elif path == "/api/saved":
            saved = indexer.get_saved_qa()
            self._send_json(200, {"saved": saved})

        else:
            self._send_json(404, {"error": f"Unknown route: {path}"})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/answer":
            self._handle_answer()
        elif path == "/api/upload":
            self._handle_upload()
        elif path == "/api/save":
            self._handle_save()
        else:
            self._send_json(404, {"error": f"Unknown route: {path}"})

    # -- /api/answer -------------------------------------------------

    def _handle_answer(self):
        data = self._read_json_body()
        question = (data or {}).get("question", "").strip()
        if not question:
            self._send_json(400, {"error": "Missing 'question' field"})
            return

        idx = get_index()
        passages = idx.search(question, top_k=config.TOP_K, min_score=config.MIN_SCORE)

        # Run safety checks
        check = safety.check_safety(question, has_results=len(passages) > 0)
        if check["refused"]:
            self._send_json(200, {
                "question": question,
                "answer": check["redirect"],
                "sources": [],
                "used_llm": False,
                "safety": check,
            })
            return

        # Draft answer from passages
        result = llm.draft_answer(question, passages)
        self._send_json(200, {
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "used_llm": result["used_llm"],
            "safety": {"refused": False, "reason": "", "redirect": ""},
        })

    # -- /api/upload -------------------------------------------------

    def _handle_upload(self):
        ct = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ct:
            self._send_json(400, {"error": "Expected multipart/form-data"})
            return

        try:
            # Parse multipart body manually (cgi module removed in Python 3.13)
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            file_data, filename = self._parse_multipart(ct, raw_body)

            if not file_data:
                self._send_json(400, {"error": "No file uploaded"})
                return

            if not filename.lower().endswith(".pdf"):
                self._send_json(400, {"error": "Only PDF files are accepted"})
                return

            # Save to data/ directory
            save_path = os.path.join(config.DATA_DIR, filename)
            os.makedirs(config.DATA_DIR, exist_ok=True)
            with open(save_path, "wb") as out:
                out.write(file_data)

            # Index the uploaded PDF
            conn = indexer.get_db()
            n = indexer.index_pdf(save_path, conn)
            conn.close()

            # Refresh in-memory index
            refresh_index()

            self._send_json(200, {
                "message": f"Indexed '{filename}' ({n} pages)",
                "filename": filename,
                "pages": n,
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    @staticmethod
    def _parse_multipart(content_type: str, body: bytes) -> tuple[bytes, str]:
        """Parse multipart/form-data without the deprecated cgi module."""
        # Extract boundary
        m = re.search(r"boundary=(.+)", content_type)
        if not m:
            return b"", ""
        boundary = m.group(1).strip().strip('"')
        boundary_bytes = ("--" + boundary).encode()

        parts = body.split(boundary_bytes)
        for part in parts:
            if b"filename=" not in part:
                continue
            # Split headers and body
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            header_section = part[:header_end].decode("utf-8", errors="replace")
            file_body = part[header_end + 4:]
            # Strip trailing \r\n
            if file_body.endswith(b"\r\n"):
                file_body = file_body[:-2]
            # Extract filename
            fn_match = re.search(r'filename="([^"]+)"', header_section)
            filename = fn_match.group(1) if fn_match else "upload.pdf"
            return file_body, filename
        return b"", ""

    # -- /api/save ---------------------------------------------------

    def _handle_save(self):
        data = self._read_json_body()
        question = (data or {}).get("question", "")
        answer = (data or {}).get("answer", "")
        sources = json.dumps((data or {}).get("sources", []), ensure_ascii=False)
        if not question or not answer:
            self._send_json(400, {"error": "Missing question or answer"})
            return
        row_id = indexer.save_qa(question, answer, sources)
        self._send_json(200, {"message": "Saved", "id": row_id})

    # -- helpers -----------------------------------------------------

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}


# -- entry point -----------------------------------------------------

def main():
    # Ensure data directory exists
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Index PDFs on first run if any exist in data/
    print("Initialising AILT9019 Q&A app...")
    results = indexer.index_all()
    if results:
        for fname, msg in results.items():
            print(f"  Indexed {fname}: {msg}")
    else:
        print("  No PDFs found in data/ — upload via /api/upload or copy course PDFs there.")

    idx = get_index()
    print(f"  BM25 index ready: {idx.page_count} pages")
    print(f"  LLM provider: {config.LLM_PROVIDER}")
    print(f"  Server starting at http://{config.HOST}:{config.PORT}")
    print("  Press Ctrl+C to stop.\n")

    server = HTTPServer((config.HOST, config.PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
