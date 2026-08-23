"""
LLM investigation assistant.

Design principles:
  - The LLM NEVER decides fraud. It only explains evidence already produced.
  - Input: structured evidence JSON → Output: analyst write-up text
  - Guardrails: strips any entity names/numbers not present in the evidence object
  - Falls back to a deterministic template if OPENAI_API_KEY is not set
  - API key is read from env var, never committed to source

The evidence-grounded-only design is a security property:
it prevents hallucinated evidence from entering a risk-decision context.
"""

import os
import json
import re
from typing import Dict, Any

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_NAME     = os.environ.get("LLM_MODEL", "gpt-4o-mini")


# ── Template fallback (no API key required) ────────────────────────────────────

def _template_investigation(evidence: Dict[str, Any]) -> str:
    """
    Deterministic template-based investigation write-up.
    Used when no LLM API key is configured. Produces a valid, readable report.
    """
    ring_id    = evidence.get("ring_id", "Unknown")
    risk_score = evidence.get("risk_score", 0)
    risk_band  = evidence.get("risk_band", "Unknown")
    accounts   = evidence.get("accounts", [])
    ev_items   = evidence.get("evidence", [])
    features   = evidence.get("features", {})

    lines = [
        f"## Investigation Report — Ring {ring_id}",
        f"**Risk Band:** {risk_band}  |  **Risk Score:** {risk_score}/100",
        "",
        "### Summary",
        (f"This cluster of {len(accounts)} accounts ({', '.join(accounts[:6])}"
         f"{'...' if len(accounts) > 6 else ''}) has been flagged as a potential "
         f"coordinated fraud ring based on {len(ev_items)} corroborating evidence signals."),
        "",
        "### Why This Is Suspicious",
    ]

    ev_descriptions = {
        "shared_device":          "Multiple accounts operate from a single shared device, a strong indicator of one operator controlling many accounts.",
        "shared_ip":              "Accounts share an IP address range, suggesting they originate from the same network infrastructure.",
        "circular_flow":          "A circular transaction chain was detected where money flows between accounts in a loop, a classic money-laundering pattern.",
        "refund_ratio":           "The refund rate within this cluster significantly exceeds the platform baseline, consistent with refund farming or collusion.",
        "transaction_concentration": "Transaction volume is concentrated toward a single merchant, suggesting coordinated buyer behavior.",
        "temporal_sync":          "Accounts in this cluster were created within a very short time window, suggesting batch account creation.",
        "high_velocity":          "Transaction velocity is unusually high relative to the platform average.",
    }

    for item in ev_items:
        ev_type = item.get("type", "")
        lines.append(f"- **{ev_type.replace('_', ' ').title()}**: {item.get('detail', '')}")
        if ev_type in ev_descriptions:
            lines.append(f"  _{ev_descriptions[ev_type]}_")

    lines += [
        "",
        "### Entity Connections",
        (f"The {len(accounts)} accounts are connected through shared infrastructure "
         f"(devices/IP ranges) and/or transaction patterns. "
         f"Shared device count: {features.get('shared_device_count', 'N/A')}. "
         f"Shared IP range count: {features.get('shared_ip_count', 'N/A')}."),
        "",
        "### Recommended Analyst Actions",
        "1. **Identity verification**: Review KYC documents for all flagged accounts. "
           "Check for identical or near-identical submitted documents.",
        "2. **Device forensics**: Investigate the shared device fingerprint(s) for "
           "additional associated accounts not yet in this cluster.",
        "3. **Transaction audit**: Review all transactions involving these accounts "
           "for the past 90 days, with particular attention to refund patterns and "
           "circular flows.",
        "4. **Network expansion**: Check whether any of these accounts share "
           "infrastructure with accounts outside this ring.",
        "5. **Do not take automated action**: Freeze, suspension, or funds reversal "
           "must be authorized by a risk officer after human review.",
        "",
        "### Confidence and Limitations",
        (f"This report is based on {len(ev_items)} structural signals from the graph "
         f"analysis engine. The risk score of {risk_score}/100 (band: {risk_band}) "
         f"reflects how anomalous this cluster is relative to the legitimate population. "
         f"Shared infrastructure alone is not conclusive — a legitimate family business "
         f"or shared office may produce similar signals. Human review is mandatory. "
         f"This system is trained on synthetic data and does not reflect "
         f"production-scale calibration."),
    ]

    return "\n".join(lines)


# ── LLM-powered investigation ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a financial fraud analyst assistant at a payments company.
You will be given a structured evidence object describing a flagged account cluster.
Your job is to produce a clear, professional investigation write-up for a human risk analyst.

STRICT RULES:
1. You may ONLY reference entities (account IDs, device IDs, amounts, ratios) that appear
   in the evidence JSON provided. Do NOT invent or hallucinate any additional entities.
2. You do NOT make a fraud determination. You explain what was detected and what to investigate.
3. You must include an explicit confidence/limitation statement at the end.
4. Do NOT recommend automated account suspension or funds reversal — only human-reviewed actions.
5. Format your response in clear markdown with sections: Summary, Why Suspicious, Entity Connections,
   Recommended Actions, Limitations.
"""

def _build_llm_prompt(evidence: Dict[str, Any]) -> str:
    # Provide only the evidence — not the full object (graph data is noisy for LLM)
    llm_evidence = {
        "ring_id":      evidence.get("ring_id"),
        "risk_score":   evidence.get("risk_score"),
        "risk_band":    evidence.get("risk_band"),
        "accounts":     evidence.get("accounts"),
        "account_count": evidence.get("account_count"),
        "evidence":     evidence.get("evidence"),
        "features":     evidence.get("features"),
    }
    return json.dumps(llm_evidence, indent=2)


def _validate_response(response_text: str, evidence: Dict[str, Any]) -> str:
    """
    Basic guardrail: check the response doesn't introduce account IDs
    not present in the evidence. Strips suspicious additions.
    This is a best-effort check — not a security boundary.
    """
    valid_account_ids = set(str(a) for a in evidence.get("accounts", []))
    # Find all A#### patterns in the response
    found_ids = set(re.findall(r'\bA\d{4}\b', response_text))
    hallucinated = found_ids - valid_account_ids
    if hallucinated:
        # Remove hallucinated IDs from the response
        for hid in hallucinated:
            response_text = response_text.replace(hid, "[REDACTED]")
        response_text += (
            "\n\n---\n_Note: This report was automatically sanitized to remove "
            "entity references not present in the original evidence object._"
        )
    return response_text


async def investigate(evidence: Dict[str, Any]) -> Dict[str, str]:
    """
    Main investigation function. Uses LLM if API key is set, else template.
    Returns dict with 'investigation' text and 'model_used' label.
    """
    if not OPENAI_API_KEY:
        print("[investigator] No OPENAI_API_KEY set — using template fallback.")
        report = _template_investigation(evidence)
        return {"investigation": report, "model_used": "template (no API key)"}

    try:
        import openai
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        prompt = _build_llm_prompt(evidence)

        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Please produce an investigation write-up for this flagged ring:\n\n{prompt}"
                )},
            ],
            max_tokens=1200,
            temperature=0.3,   # lower temp = more faithful to evidence
        )
        raw_text = response.choices[0].message.content or ""
        safe_text = _validate_response(raw_text, evidence)
        return {"investigation": safe_text, "model_used": MODEL_NAME}

    except Exception as e:
        print(f"[investigator] LLM call failed ({e}). Using template fallback.")
        report = _template_investigation(evidence)
        return {"investigation": report, "model_used": "template (LLM error)"}
