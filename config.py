"""
Configuration for the AILT9019 Course Q&A app.
All paths are resolved relative to this file so the app is portable.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "ailt9019_qa.db")

HOST = "127.0.0.1"
PORT = 8765

# ------------------------------------------------------------------
# LLM settings (optional — retrieval + citation works without a key)
#   Set LLM_PROVIDER to "deepseek", "ollama", or "none".
#   For DeepSeek:  export DEEPSEEK_API_KEY="sk-xxxx"
#   For Ollama:    ensure `ollama serve` is running locally
# ------------------------------------------------------------------
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

# ------------------------------------------------------------------
# Retrieval settings
# ------------------------------------------------------------------
TOP_K = 5            # number of passages to retrieve
BM25_K1 = 1.5        # term-frequency saturation
BM25_B = 0.75        # length-normalisation

MIN_SCORE = 0.01     # discard passages below this BM25 score

# Allowed course-material filenames (whitelist for safety)
ALLOWED_EXTENSIONS = (".pdf",)
