# Deployment profiles

No deployment profile has been measured or validated end to end. The current Compose file is a development stack, not production configuration. The startup script defaults Ollama to `llama3.2:1b`; Ollama's official library lists 1B and 3B variants for Llama 3.2. No quality or memory benchmark has been run for this default. [Ollama model listing](https://ollama.com/library/llama3.2)

| Profile | Intended scope | Status |
|---|---|---|
| Lite | single Mac/Linux host, constrained memory, local inference, minimal services | proposed; 8 GB Apple Silicon NOT TESTED |
| Standard | local Docker Compose services for development/integration | Compose exists; credentials and health/dependency behavior require hardening |
| Production | isolated services, managed secrets, backups, monitoring, TLS, access control | design only; not implemented |

Do not infer ARM64 support solely from upstream image tags. Verify every image/architecture, model size, peak memory, health ordering, restart behavior, and graceful shutdown on the target host. Current compose includes services beyond what a lightweight profile can run.
