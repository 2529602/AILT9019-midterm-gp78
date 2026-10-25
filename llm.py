"""
LLM module — optionally drafts an answer from retrieved passages.

Uses urllib (stdlib) for HTTP so no `requests` dependency is needed.
If no API key is configured the answer falls back to a passage-excerpt
mode that simply quotes the top retrieved passages with [S1][S2] markers.
"""

import json
import urllib.request

import config


def _build_prompt(question: str, passages: list[dict]) -> str:
    """Compose the system + user prompt with cited passages."""
    context_blocks = []
    for i, p in enumerate(passages):
        snippet = p["text"][:800]
        context_blocks.append(
            f"[S{i+1}] Document: {p['doc_name']}, Page {p['page_num']}\n"
            f"{snippet}"
        )
    context = "\n\n".join(context_blocks)

    system_msg = (
        "You are a course Q&A assistant for AILT9019 students. "
        "Answer ONLY using the provided source passages. "
        "Cite each claim with [S1], [S2], etc. matching the passage labels. "
        "If the sources do not contain the answer, say you cannot verify "
        "and direct the student to Moodle or course staff. "
        "Keep answers concise (3-5 sentences)."
    )
    user_msg = (
        f"Source passages:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer (cite sources with [S1] [S2] markers):"
    )
    return system_msg, user_msg


def _call_deepseek(question: str, passages: list[dict]) -> str | None:
    """Call DeepSeek's OpenAI-compatible chat endpoint."""
    if not config.DEEPSEEK_API_KEY:
        return None
    system_msg, user_msg = _build_prompt(question, passages)
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.DEEPSEEK_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] DeepSeek call failed: {e}")
        return None


def _call_ollama(question: str, passages: list[dict]) -> str | None:
    """Call a local Ollama instance."""
    system_msg, user_msg = _build_prompt(question, passages)
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] Ollama call failed: {e}")
        return None


def draft_answer(question: str, passages: list[dict]) -> dict:
    """
    Produce an answer dict: {answer, used_llm, sources}.

    If an LLM provider is configured and reachable, the answer is
    LLM-generated from the passages. Otherwise we fall back to
    excerpting the top passages with citation markers.
    """
    if not passages:
        return {
            "answer": (
                "I could not find relevant information in the indexed "
                "course materials for this question. Please check Moodle "
                "or contact course staff."
            ),
            "used_llm": False,
            "sources": [],
        }

    llm_answer = None
    used_llm = False

    if config.LLM_PROVIDER == "deepseek":
        llm_answer = _call_deepseek(question, passages)
        used_llm = llm_answer is not None
    elif config.LLM_PROVIDER == "ollama":
        llm_answer = _call_ollama(question, passages)
        used_llm = llm_answer is not None

    if llm_answer:
        answer_text = llm_answer
    else:
        # Fallback: excerpt top passages with [S1][S2] markers
        excerpts = []
        for i, p in enumerate(passages[:3]):
            snippet = p["text"][:300].replace("\n", " ").strip()
            excerpts.append(f"[S{i+1}] {snippet}")
        answer_text = (
            "Here are the most relevant passages from the course materials:\n\n"
            + "\n\n".join(excerpts)
            + "\n\n(Note: Set DEEPSEEK_API_KEY or run Ollama for AI-generated answers.)"
        )

    sources = [
        {
            "label": f"S{i+1}",
            "doc_name": p["doc_name"],
            "page_num": p["page_num"],
            "version": p["version"],
            "score": p["score"],
        }
        for i, p in enumerate(passages)
    ]

    return {"answer": answer_text, "used_llm": used_llm, "sources": sources}
