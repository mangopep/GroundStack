# Answer verification

Claim-level verification and abstention are design goals, not implemented API behavior. A target response should separate claims, attach one or more source spans to each claim, verify that each span entails the claim, and abstain or label uncertainty when evidence is missing or contradictory. Citations should include document/version identity and page or stable section anchors.

Evaluation must report citation precision/correctness and evidence coverage separately from answer quality. LLM-based judges alone are not proof; use deterministic citation existence/page checks and human-reviewed samples. Prompt-injection text in retrieved documents is untrusted data and must never grant tool authority.
