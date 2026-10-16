import os
from langchain_groq import ChatGroq

# --- API-ключи ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
XFINLINK_API_KEY = os.environ.get("XFINLINK_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("Установите переменную окружения GROQ_API_KEY")

# --- LLM ---
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0.1,
)