# Verification engine status

`src/answer/verifier.py` and `confidence.py` are empty. There is no claim segmentation, evidence entailment check, citation validator, contradiction policy, or abstention contract.

A future verifier should check deterministic citation existence/page consistency first, preserve conflicting source passages, and measure claim support with human-reviewed samples. An LLM judge alone is not sufficient evidence. No current claim-level accuracy value is available.
