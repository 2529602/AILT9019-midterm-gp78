"""
Retriever — BM25 scoring over indexed pages.

Implements Okapi BM25 from scratch (no external dependency) so the
only pip-install needed for the whole app is pdfplumber.
"""

import re
import math
from collections import Counter, defaultdict


def tokenize(text: str) -> list[str]:
    """Lower-case, split on non-alphanumeric boundaries."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Index:
    """In-memory BM25 index built from a list of documents."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[dict] = []          # [{doc_id, tokens, metadata}]
        self.doc_freq: dict[str, int] = defaultdict(int)  # term -> #docs
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.N: int = 0

    # -- building ---------------------------------------------------

    def add_document(self, doc_id: int, text: str, metadata: dict | None = None):
        tokens = tokenize(text)
        self.docs.append({
            "doc_id": doc_id,
            "tokens": tokens,
            "metadata": metadata or {},
        })
        self.doc_len.append(len(tokens))
        for term in set(tokens):
            self.doc_freq[term] += 1
        self.N += 1

    def finalize(self):
        self.avgdl = sum(self.doc_len) / self.N if self.N > 0 else 0.0

    # -- searching --------------------------------------------------

    def search(self, query: str, top_k: int = 5, min_score: float = 0.01) -> list[dict]:
        """Return top-k passages sorted by BM25 score.

        Each result dict has:
          doc_id, score, doc_name, page_num, version, text (snippet)
        """
        query_tokens = tokenize(query)
        if not query_tokens or self.N == 0:
            return []

        scores = []
        for i, doc in enumerate(self.docs):
            tf = Counter(doc["tokens"])
            dl = self.doc_len[i]
            score = 0.0
            for term in query_tokens:
                df = self.doc_freq.get(term, 0)
                if df == 0:
                    continue
                idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
                tf_val = tf.get(term, 0)
                denom = tf_val + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * (tf_val * (self.k1 + 1)) / denom if denom > 0 else 0
            if score > min_score:
                meta = doc["metadata"]
                scores.append({
                    "doc_id": doc["doc_id"],
                    "score": round(score, 4),
                    "doc_name": meta.get("doc_name", ""),
                    "page_num": meta.get("page_num", 0),
                    "version": meta.get("version", ""),
                    "text": meta.get("text", ""),
                })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    @property
    def page_count(self) -> int:
        return self.N
