import os

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

MAX_ITER = int(os.getenv("MAX_ITER", "3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "1"))
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "16"))
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "10"))
