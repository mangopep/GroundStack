# Feedback and correction status

The initial SQL schema has `user_feedback` and `human_overrides` tables, and `src/stores/overrides.py` plus API feedback routes are empty. There is no feedback endpoint, actor authorization, provenance/audit trail, review state machine, expiry policy, or conflict-resolution path in active application code.

Do not treat the schema as a working feedback feature. Corrections need actor, time, source answer/version, reason, review status, and reversible application semantics.
