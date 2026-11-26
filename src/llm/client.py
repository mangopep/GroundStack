"""Centralized LLM client wrapper for RAG Platform.

Wraps Ollama API with:
- generate(): text generation
- generate_structured(): Pydantic model output using instructor
- stream(): async streaming generation

Auto-traces to LangFuse and handles retries with exponential backoff.
Reads model from config/settings.py.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator

import ollama
from pydantic import BaseModel

from src.config import get_settings

logger = logging.getLogger(__name__)

# Try to import LangFuse, but gracefully handle if unavailable
# (e.g., Python 3.14 compatibility issues with Pydantic v1)
try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except (ImportError, Exception):
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore


# =============================================================================
# Retry Logic
# =============================================================================


def with_retry(func):
    """Decorator for retrying with exponential backoff (3 attempts)."""

    async def wrapper(*args, **kwargs):
        max_attempts = 3
        base_delay = 1.0

        last_exception = None
        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
        raise last_exception

    return wrapper


# =============================================================================
# LLM Client
# =============================================================================


class LLMClient:
    """
    Centralized LLM client that wraps Ollama API.

    Features:
    - generate(): text generation
    - generate_structured(): Pydantic model output using instructor
    - stream(): async streaming generation
    - Auto-traces to LangFuse (model, input, output, latency, tokens)
    - Retries with exponential backoff (3 attempts)
    - Reads model from config/settings.py
    """

    def __init__(self):
        """Initialize LLM client with settings."""
        self._settings = get_settings()
        self._ollama_client = ollama

        # Initialize LangFuse only if available and keys are provided
        if (
            LANGFUSE_AVAILABLE
            and self._settings.langfuse.public_key
            and self._settings.langfuse.secret_key
        ):
            try:
                self._langfuse = Langfuse(
                    public_key=self._settings.langfuse.public_key,
                    secret_key=self._settings.langfuse.secret_key,
                    host=self._settings.langfuse.host,
                )
            except Exception:
                # Silently fail if LangFuse initialization fails
                self._langfuse = None
        else:
            self._langfuse = None

    @property
    def model(self) -> str:
        """Get default model from config."""
        return self._settings.ollama.model

    @property
    def ollama_host(self) -> str:
        """Get Ollama host from config."""
        return self._settings.ollama.host

    # =========================================================================
    # Generate (text)
    # =========================================================================

    @with_retry
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """
        Generate text response from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            model: Model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text string
        """
        model = model or self.model
        start_time = time.time()

        response = self._ollama_client.generate(
            model=model,
            prompt=prompt,
            system=system_prompt if system_prompt else None,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            stream=False,
        )

        output = response["response"]
        latency = time.time() - start_time
        tokens = response.get("eval_count", 0)

        # Trace to LangFuse
        self._trace(
            model=model,
            input_text=prompt,
            output_text=output,
            latency=latency,
            tokens=tokens,
            usage=response.get("prompt_eval_count", 0),
        )

        return output

    # =========================================================================
    # Generate Structured (Pydantic)
    # =========================================================================

    @with_retry
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        model: str | None = None,
    ) -> BaseModel:
        """
        Generate structured response using instructor.

        Args:
            prompt: User prompt
            response_model: Pydantic model class to parse response
            model: Model name (defaults to config)

        Returns:
            Pydantic model instance
        """
        model = model or self.model
        start_time = time.time()

        # Use instructor for structured output
        import instructor

        # Create instructor client
        client = instructor.from_ollama(
            base_url=self.ollama_host,
            model=model,
        )

        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=response_model,
            temperature=0.1,
        )

        latency = time.time() - start_time

        # Trace to LangFuse
        self._trace(
            model=model,
            input_text=prompt,
            output_text=response.model_dump_json(),
            latency=latency,
            tokens=0,
            usage=0,
        )

        return response

    # =========================================================================
    # Stream (async generator)
    # =========================================================================

    @with_retry
    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from LLM as async generator.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context

        Yields:
            Text chunks as they are generated
        """
        model = self.model
        start_time = time.time()

        stream_response = self._ollama_client.generate(
            model=model,
            prompt=prompt,
            system=system_prompt if system_prompt else None,
            options={"temperature": 0.1},
            stream=True,
        )

        full_output = ""
        for chunk in stream_response:
            text = chunk["response"]
            full_output += text
            yield text

        latency = time.time() - start_time

        # Trace to LangFuse
        self._trace(
            model=model,
            input_text=prompt,
            output_text=full_output,
            latency=latency,
            tokens=0,
            usage=0,
        )

    # =========================================================================
    # LangFuse Tracing
    # =========================================================================

    def _trace(
        self,
        model: str,
        input_text: str,
        output_text: str,
        latency: float,
        tokens: int,
        usage: int,
    ) -> None:
        """
        Trace LLM call to LangFuse.

        Args:
            model: Model name
            input_text: Input prompt
            output_text: Generated output
            latency: Request latency in seconds
            tokens: Number of tokens in output
            usage: Number of tokens in input
        """
        # Skip tracing if LangFuse is not configured
        if self._langfuse is None:
            return

        try:
            # Use LangFuse generation tracing
            self._langfuse.trace(
                name="llm_generation",
                model=model,
                input=input_text,
                output=output_text,
                metadata={
                    "latency": latency,
                    "output_tokens": tokens,
                    "input_tokens": usage,
                },
            )
        except Exception as exc:
            # Keep observability failures non-fatal without logging prompt content.
            logger.warning("Langfuse trace export failed (%s)", type(exc).__name__)


# =============================================================================
# Singleton Accessor
# =============================================================================


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """
    Get singleton LLM client instance.

    Returns:
        LLMClient: Singleton instance
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
