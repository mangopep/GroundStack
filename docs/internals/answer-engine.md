# Answer engine status

`src/llm/client.py` wraps the Ollama library for generation, streaming, and structured responses and includes a retry decorator. Langfuse initialization is optional. No route or application service calls it to answer a retrieved query. `src/answer/generator.py` and `streamer.py` are empty.

Retries can repeat model work and add latency; they should apply only to transient errors and be bounded by a request deadline. Do not include private source documents in external traces without an explicit privacy policy. Current implementation has no answer quality measurements.
