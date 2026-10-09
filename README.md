# unit2-capstone

## Trust-but-Verify

Qualitative Agent Checks:
Claim verified: The qualitative agent refuses to answer when information is absent from the knowledge base, rather than hallucinating.
How verified: Queried "What is our parental leave policy?" — a topic with no corresponding source document. Agent returned the exact grounding phrase, "I cannot find this information in the provided documents," confirming the prompt's grounding instruction holds on Gemini.
Validator alignment: validate_qualitative detects refusals via the substring "cannot find". Because Gemini emitted the literal phrase, the validator correctly classifies this as a refusal — agent behaviour and validator logic are consistent.
Residual risk noted: This alignment depends on Gemini reproducing the exact wording. At temperature=0.2 it did so reliably here, but a higher temperature or a prompt change could cause a paraphrase the substring check would miss. Low risk at current settings; flagged for awareness.
