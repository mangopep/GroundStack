"""LLM Cost/Usage Tracker for RAG Platform.

Tracks per-request and cumulative token usage for LLM calls.
Stores data in Redis with daily keys.
For Ollama (free), this tracks compute usage not cost.

Purpose: Know which LLM calls are most expensive so you can optimize.
Log summary to LangFuse daily.
"""

from datetime import date

import redis

from src.config import get_settings

# Try to import LangFuse, but gracefully handle if unavailable
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except (ImportError, Exception):
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore


# =============================================================================
# CostTracker Class
# =============================================================================


class CostTracker:
    """
    Tracks LLM cost and usage metrics.

    Stores daily aggregated stats in Redis with keys: llm_cost:{YYYY-MM-DD}
    For Ollama (free), tracks compute usage not cost.

    Usage:
        tracker = CostTracker()
        tracker.record_call("llama3.2:1b", 100, 50, 500, "rewriter")
        stats = tracker.get_daily_stats()
    """

    def __init__(self):
        """Initialize CostTracker with Redis and LangFuse connections."""
        settings = get_settings()
        self._redis = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            decode_responses=True
        )

        # Initialize LangFuse only if available
        if LANGFUSE_AVAILABLE:
            try:
                self._langfuse = Langfuse()
            except Exception:
                self._langfuse = None
        else:
            self._langfuse = None

    def _get_daily_key(self, day: date | None = None) -> str:
        """Get Redis key for a given date."""
        if day is None:
            day = date.today()
        return f"llm_cost:{day.isoformat()}"

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        purpose: str,
    ) -> None:
        """
        Record a single LLM call to Redis.

        Args:
            model: Model identifier, such as ``llama3.2:1b``.
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            latency_ms: Latency in milliseconds
            purpose: Purpose of the call (e.g., "rewriter", "generator", "verifier")
        """
        day = date.today()
        key = self._get_daily_key(day)

        # Use Redis pipeline for atomic updates
        pipe = self._redis.pipeline(transaction=True)

        # Total stats
        pipe.hincrby(key, "total_calls", 1)
        pipe.hincrby(key, "total_input_tokens", input_tokens)
        pipe.hincrby(key, "total_output_tokens", output_tokens)
        pipe.hincrbyfloat(key, "total_latency_ms", latency_ms)

        # Per-purpose stats
        pipe.hincrby(key, f"purpose:{purpose}:calls", 1)
        pipe.hincrby(key, f"purpose:{purpose}:input_tokens", input_tokens)
        pipe.hincrby(key, f"purpose:{purpose}:output_tokens", output_tokens)
        pipe.hincrbyfloat(key, f"purpose:{purpose}:latency_ms", latency_ms)

        # Per-model stats
        pipe.hincrby(key, f"model:{model}:calls", 1)
        pipe.hincrby(key, f"model:{model}:input_tokens", input_tokens)
        pipe.hincrby(key, f"model:{model}:output_tokens", output_tokens)
        pipe.hincrbyfloat(key, f"model:{model}:latency_ms", latency_ms)

        pipe.execute()

    def get_daily_stats(self, day: date | None = None) -> dict:
        """
        Get aggregated stats for a given day.

        Args:
            day: Date to get stats for (defaults to today)

        Returns:
            Dictionary with:
                - total_calls: Total number of calls
                - total_input_tokens: Total input tokens
                - total_output_tokens: Total output tokens
                - total_tokens: Total tokens (input + output)
                - avg_latency: Average latency in ms
                - by_purpose: Dict of purpose -> {calls, input_tokens, output_tokens, avg_latency}
                - by_model: Dict of model -> {calls, input_tokens, output_tokens, avg_latency}
        """
        if day is None:
            day = date.today()

        key = self._get_daily_key(day)
        data = self._redis.hgetall(key)

        if not data:
            return {
                "date": day.isoformat(),
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "avg_latency": 0.0,
                "by_purpose": {},
                "by_model": {},
            }

        # Parse totals
        total_calls = int(data.get("total_calls", 0))
        total_input_tokens = int(data.get("total_input_tokens", 0))
        total_output_tokens = int(data.get("total_output_tokens", 0))
        total_latency_ms = float(data.get("total_latency_ms", 0))

        avg_latency = total_latency_ms / total_calls if total_calls > 0 else 0.0

        # Parse by purpose
        by_purpose = {}
        for hash_key in data:
            if hash_key.startswith("purpose:") and hash_key.endswith(":calls"):
                purpose = hash_key.split(":")[1]
                by_purpose[purpose] = {
                    "calls": int(data.get(f"purpose:{purpose}:calls", 0)),
                    "input_tokens": int(data.get(f"purpose:{purpose}:input_tokens", 0)),
                    "output_tokens": int(data.get(f"purpose:{purpose}:output_tokens", 0)),
                    "latency_ms": float(data.get(f"purpose:{purpose}:latency_ms", 0)),
                }
                # Calculate avg latency for this purpose
                p_calls = by_purpose[purpose]["calls"]
                by_purpose[purpose]["avg_latency"] = (
                    by_purpose[purpose]["latency_ms"] / p_calls if p_calls > 0 else 0.0
                )
                # Add total tokens
                by_purpose[purpose]["total_tokens"] = (
                    by_purpose[purpose]["input_tokens"] + by_purpose[purpose]["output_tokens"]
                )

        # Parse by model
        by_model = {}
        for hash_key in data:
            if hash_key.startswith("model:") and hash_key.endswith(":calls"):
                model = hash_key.split(":")[1]
                by_model[model] = {
                    "calls": int(data.get(f"model:{model}:calls", 0)),
                    "input_tokens": int(data.get(f"model:{model}:input_tokens", 0)),
                    "output_tokens": int(data.get(f"model:{model}:output_tokens", 0)),
                    "latency_ms": float(data.get(f"model:{model}:latency_ms", 0)),
                }
                # Calculate avg latency for this model
                m_calls = by_model[model]["calls"]
                by_model[model]["avg_latency"] = (
                    by_model[model]["latency_ms"] / m_calls if m_calls > 0 else 0.0
                )
                # Add total tokens
                by_model[model]["total_tokens"] = (
                    by_model[model]["input_tokens"] + by_model[model]["output_tokens"]
                )

        return {
            "date": day.isoformat(),
            "total_calls": total_calls,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "avg_latency": round(avg_latency, 2),
            "by_purpose": by_purpose,
            "by_model": by_model,
        }

    def log_daily_summary(self, day: date | None = None) -> None:
        """
        Log daily summary to LangFuse for observability.

        Args:
            day: Date to log summary for (defaults to today)
        """
        if day is None:
            day = date.today()

        stats = self.get_daily_stats(day)

        # Only log if LangFuse is available
        if self._langfuse is None:
            return

        try:
            self._langfuse.trace(
                name="llm_daily_summary",
                input=stats,
                output={
                    "date": stats["date"],
                    "total_calls": stats["total_calls"],
                    "total_tokens": stats["total_tokens"],
                    "avg_latency_ms": stats["avg_latency"],
                },
                metadata={
                    "total_input_tokens": stats["total_input_tokens"],
                    "total_output_tokens": stats["total_output_tokens"],
                    "by_purpose": stats["by_purpose"],
                    "by_model": stats["by_model"],
                },
            )
        except Exception:
            # Silently fail if LangFuse is not available
            pass

    def get_purpose_stats(self, purpose: str, day: date | None = None) -> dict:
        """
        Get stats for a specific purpose.

        Args:
            purpose: Purpose name (e.g., "rewriter", "generator", "verifier")
            day: Date to get stats for (defaults to today)

        Returns:
            Dictionary with purpose stats or empty dict if not found
        """
        stats = self.get_daily_stats(day)
        return stats.get("by_purpose", {}).get(purpose, {})

    def get_all_purposes(self, day: date | None = None) -> list[str]:
        """
        Get list of all purposes that have been tracked.

        Args:
            day: Date to get purposes for (defaults to today)

        Returns:
            List of purpose names
        """
        if day is None:
            day = date.today()

        key = self._get_daily_key(day)
        data = self._redis.hgetall(key)

        purposes = set()
        for hash_key in data:
            if hash_key.startswith("purpose:") and hash_key.endswith(":calls"):
                purpose = hash_key.split(":")[1]
                purposes.add(purpose)

        return sorted(list(purposes))


# =============================================================================
# Singleton Accessor
# =============================================================================


_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker:
    """
    Get singleton CostTracker instance.

    Returns:
        CostTracker: Singleton instance
    """
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker

