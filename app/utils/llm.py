import os
import logging
import threading
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

logger = logging.getLogger(__name__)


class GroqKeyManager:
    """Manages multiple Groq API keys with automatic rotation on rate-limit."""

    def __init__(self):
        self._lock = threading.Lock()

        # Load keys: prefer GROQ_API_KEYS (comma-separated), fallback to GROQ_API_KEY
        keys_str = os.getenv("GROQ_API_KEYS", "")
        if keys_str.strip():
            self.keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        else:
            single = os.getenv("GROQ_API_KEY", "")
            self.keys = [single] if single else []

        if not self.keys:
            raise ValueError(
                "No Groq API keys found. Set GROQ_API_KEYS (comma-separated) "
                "or GROQ_API_KEY in your .env file."
            )

        self._current = 0
        logger.info(f"[LLM] Loaded {len(self.keys)} Groq API key(s)")

    @property
    def current_key(self) -> str:
        with self._lock:
            return self.keys[self._current]

    def rotate(self) -> str:
        """Rotate to the next key. Returns the new key."""
        with self._lock:
            prev = self._current
            self._current = (self._current + 1) % len(self.keys)
            logger.warning(
                f"[LLM] Rotating API key: #{prev + 1} → #{self._current + 1} "
                f"(of {len(self.keys)} total)"
            )
            return self.keys[self._current]

    @property
    def total_keys(self) -> int:
        return len(self.keys)


# Module-level singleton
_manager = GroqKeyManager()


def get_llm():
    """Return a ChatGroq instance using the currently active API key."""
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=_manager.current_key,
    )


def call_llm(prompt):
    """
    Invoke the LLM with automatic key rotation on rate-limit errors.

    Args:
        prompt: The prompt string or LangChain message list to send.

    Returns:
        The LLM response object.

    Raises:
        RuntimeError: If all keys are exhausted.
    """
    tried = 0
    last_error = None

    while tried < _manager.total_keys:
        llm = get_llm()
        key_num = _manager._current + 1
        try:
            logger.info(f"[LLM] Calling Groq with API key #{key_num}")
            response = llm.invoke(prompt)
            return response
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = (
                "rate_limit" in error_str
                or "rate limit" in error_str
                or "429" in error_str
                or "token" in error_str and "limit" in error_str
                or "resource_exhausted" in error_str
                or "quota" in error_str
            )

            if is_rate_limit:
                tried += 1
                last_error = e
                logger.warning(
                    f"[LLM] Rate limit hit on key #{key_num}: {e}"
                )
                if tried < _manager.total_keys:
                    _manager.rotate()
                continue
            else:
                # Non-rate-limit error — don't retry, just raise
                raise

    raise RuntimeError(
        f"All {_manager.total_keys} Groq API key(s) have been rate-limited. "
        f"Please wait or add more keys to GROQ_API_KEYS in your .env file. "
        f"Last error: {last_error}"
    )
