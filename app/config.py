import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set")

REMOTE_VACANCY_FETCH_ENABLED = os.getenv("REMOTE_VACANCY_FETCH_ENABLED", "false").lower() == "true"
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434").rstrip("/")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
OPENAI_WEB_RESEARCH_ENABLED = os.getenv("OPENAI_WEB_RESEARCH_ENABLED", "false").lower() == "true"
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

if AI_PROVIDER not in {"ollama", "openai"}:
    raise RuntimeError("AI_PROVIDER must be either ollama or openai")
