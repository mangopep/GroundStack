"""LLM module for RAG Platform.

Provides centralized LLM client wrapper with:
- generate(): text generation
- generate_structured(): Pydantic model output using instructor
- stream(): async streaming generation
- Auto-traces to LangFuse
- Retry with exponential backoff

Cost tracking with:
- CostTracker: Tracks per-request and cumulative token usage
- Stores daily stats in Redis with daily keys
- Log summary to LangFuse daily
"""

from src.llm.client import LLMClient, get_llm_client
from src.llm.cost_tracker import CostTracker, get_cost_tracker

__all__ = [
    "LLMClient",
    "get_llm_client",
    "CostTracker",
    "get_cost_tracker",
]

