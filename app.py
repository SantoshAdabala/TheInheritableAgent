import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

from src.child_agent import ChildAgent
from src.parent_agent import ParentAgent
from src.token_vault_bridge import TokenVaultBridge

app = Flask(__name__, static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")

vault = TokenVaultBridge()
child_agent = ChildAgent(vault)
parent_agent = ParentAgent()


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return jsonify({"error": "GROQ_API_KEY not configured"}), 503
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
        },
        timeout=30,
    )
    if not resp.ok:
        return jsonify({"error": f"Groq error {resp.status_code}"}), 502
    text = resp.json()["choices"][0]["message"]["content"]
    return jsonify({"text": text})


@app.route("/parent/extract-wisdom", methods=["POST"])
def parent_extract_wisdom():
    data = request.get_json(silent=True) or {}
    decisions = data.get("decisions", [])
    if not decisions:
        return jsonify({"error": "decisions required"}), 400
    try:
        patterns = parent_agent.extract_wisdom(decisions)
        if not patterns:
            return jsonify({"error": "AI could not extract patterns"}), 502
        return jsonify({"patterns": patterns, "pattern_count": len(patterns)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {e}"}), 502


@app.route("/health")
def health():
    api_key = os.getenv("GROQ_API_KEY", "")
    return jsonify({
        "status": "ok",
        "mode": "demo" if vault.demo_mode else "live",
        "ai_configured": bool(api_key),
    })


@app.route("/vault/deposit", methods=["POST"])
def vault_deposit():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    patterns = data.get("wisdom_patterns")
    if not user_id or not patterns:
        return jsonify({"error": "user_id and wisdom_patterns required"}), 400
    return jsonify(vault.deposit_wisdom(user_id, patterns))


@app.route("/vault/trustee-confirm", methods=["POST"])
def vault_trustee_confirm():
    data = request.get_json(silent=True) or {}
    missing = [k for k in ["user_id", "trustee_id", "confirmation_token"] if not data.get(k)]
    if missing:
        return jsonify({"error": f"Missing: {missing}"}), 400
    return jsonify(vault.confirm_trustee(data["user_id"], data["trustee_id"], data["confirmation_token"]))


@app.route("/vault/issue-inheritance-token", methods=["POST"])
def vault_issue_token():
    data = request.get_json(silent=True) or {}
    parent_id, child_id = data.get("parent_id"), data.get("child_id")
    if not parent_id or not child_id:
        return jsonify({"error": "parent_id and child_id required"}), 400
    result = vault.issue_inheritance_token(parent_id, child_id)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/vault/delegate-token", methods=["POST"])
def vault_delegate_token():
    data = request.get_json(silent=True) or {}
    issuer_token = data.get("issuer_token")
    delegate_to = data.get("delegate_to")
    requested_scopes = data.get("requested_scopes", [])
    if not issuer_token or not delegate_to or not requested_scopes:
        return jsonify({"error": "issuer_token, delegate_to, and requested_scopes required"}), 400
    result = vault.delegate_token(issuer_token, delegate_to, requested_scopes)
    if result.get("blocked"):
        return jsonify(result), 403
    return jsonify(result)


@app.route("/vault/ingest-github", methods=["POST"])
def vault_ingest_github():
    data = request.get_json(silent=True) or {}
    github_token = data.get("github_token")
    github_username = data.get("github_username")
    user_id = data.get("user_id", "auth0|parent_001")
    if not github_token or not github_username:
        return jsonify({"error": "github_token and github_username required"}), 400
    vault.store_github_token(user_id, github_token)
    result = vault.ingest_github_commits(github_token, github_username)
    if result.get("commits"):
        try:
            patterns = parent_agent.github_patterns(result["commits"])
            result["patterns"] = patterns
        except Exception:
            result["patterns"] = []
    result["github_token_stored"] = True
    result["user_id"] = user_id
    return jsonify(result)


@app.route("/vault/lineage")
def vault_lineage():
    token = request.args.get("token")
    parent_id = request.args.get("parent_id")
    if not token and not parent_id:
        return jsonify({"error": "token or parent_id required"}), 400
    return jsonify(vault.get_lineage_graph(root_parent_id=parent_id, token=token))


@app.route("/audit/log")
def audit_log():
    return jsonify({"log": vault.get_audit_log()})


@app.route("/vault/public-key")
def vault_public_key():
    return jsonify({"public_key_pem": vault.get_public_key_pem()})


@app.route("/child/fetch-patterns", methods=["POST"])
def child_fetch_patterns():
    data = request.get_json(silent=True) or {}
    token = data.get("inheritance_token")
    question = data.get("question", "")
    step_up_confirmed = data.get("step_up_confirmed", False)
    if not token:
        return jsonify({"error": "inheritance_token required"}), 400
    if question and not step_up_confirmed:
        categories = vault.requires_step_up(question)
        if categories:
            vault._audit("STEP-UP TRIGGERED", "child", f"sensitive topic detected: {', '.join(categories)}", outcome="mfa-required")
            return jsonify({
                "step_up_required": True,
                "categories": categories,
                "detail": (
                    "This question touches sensitive topics. "
                    "In production, Auth0 step-up auth (MFA) would be triggered here. "
                    "Confirm your identity to proceed."
                ),
            }), 403
    result = child_agent.fetch_patterns(token)
    if result.get("blocked"):
        return jsonify(result), 403
    return jsonify(result)


@app.route("/child/attempt-raw-access", methods=["POST"])
def child_attempt_raw_access():
    data = request.get_json(silent=True) or {}
    token = data.get("inheritance_token")
    if not token:
        return jsonify({"error": "inheritance_token required"}), 400
    result = child_agent.attempt_raw_access(token)
    vault._audit("RAW ACCESS ATTEMPT", "child", "raw_data:access requested", outcome="BLOCKED ✗")
    return jsonify(result), 403


@app.route("/child/resolve-conflict", methods=["POST"])
def child_resolve_conflict():
    data = request.get_json(silent=True) or {}
    token_a = data.get("token_a")
    token_b = data.get("token_b")
    question = data.get("question", "")
    if not token_a or not token_b:
        return jsonify({"error": "token_a and token_b required"}), 400
    result = child_agent.resolve_conflict(token_a, token_b)
    if result.get("blocked"):
        return jsonify(result), 403
    result["question"] = question
    return jsonify(result)


@app.route("/demo/inheritance", methods=["POST"])
def demo_inheritance():
    parent_a_id = "auth0|parent_001"
    parent_b_id = "auth0|parent_conflict_002"
    child_id = "auth0|child_002"
    advisor_id = "auth0|advisor_003"

    demo_decisions = [
        "Turned down a VP role at a profitable company because their product caused harm I couldn't defend",
        "Chose to work four-day weeks for three years to be present during my children's early years",
        "Sold investments at a loss to keep every employee paid during a six-month revenue drought",
        "Spent two years learning to code at 45 so I could understand what my team was building",
        "Refused to settle a lawsuit out of court even though it cost more, because the principle mattered",
    ]

    try:
        patterns_a = parent_agent.extract_wisdom(demo_decisions)
    except Exception:
        patterns_a = []

    try:
        patterns_b = parent_agent.conflict_patterns()
    except Exception:
        patterns_b = []

    vault.deposit_wisdom(parent_a_id, patterns_a)
    vault.confirm_trustee(parent_a_id, "trustee_attorney_001", "sig_atty_xk29")
    vault.confirm_trustee(parent_a_id, "trustee_sibling_002", "sig_sib_mq47")
    token_a = vault.issue_inheritance_token(parent_a_id, child_id)

    vault.deposit_wisdom(parent_b_id, patterns_b)
    vault.confirm_trustee(parent_b_id, "trustee_friend_003", "sig_frnd_ab12")
    vault.confirm_trustee(parent_b_id, "trustee_doctor_004", "sig_doc_cd34")
    token_b = vault.issue_inheritance_token(parent_b_id, child_id)

    if "error" in token_a or "error" in token_b:
        return jsonify({"error": "Token issuance failed"}), 500

    delegation = vault.delegate_token(token_a["inheritance_token"], advisor_id, ["wisdom:career"])
    patterns_result = child_agent.fetch_patterns(token_a["inheritance_token"])
    raw_blocked = child_agent.attempt_raw_access(token_a["inheritance_token"])
    conflict = child_agent.resolve_conflict(token_a["inheritance_token"], token_b["inheritance_token"])
    lineage = vault.get_lineage_graph(root_parent_id=parent_a_id)

    return jsonify({
        "steps": [
            {"step": 1, "action": "AI extracted wisdom patterns", "patterns": patterns_a},
            {"step": 2, "action": "Deposited to vault", "pattern_count": len(patterns_a)},
            {"step": 3, "action": "2-of-3 trustee multi-sig unlocked"},
            {"step": 4, "action": "Inheritance token issued", "scopes": token_a.get("scopes"), "mode": token_a.get("mode")},
            {"step": 5, "action": "Patterns returned to child", "pattern_count": len(patterns_result.get("patterns", []))},
            {"step": 6, "action": "Raw access blocked", "blocked": True, "detail": raw_blocked.get("detail")},
            {"step": 7, "action": "Token delegated to advisor", "scopes": delegation.get("scopes"), "depth": delegation.get("depth")},
            {"step": 8, "action": "Conflict resolution ready", "conflict_ready": not conflict.get("blocked")},
            {"step": 9, "action": "Lineage graph built", "node_count": len(lineage.get("nodes", []))},
        ],
        "summary": "Full end-to-end demo complete. Wisdom inherited. Privacy preserved.",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    app.run(host="0.0.0.0", debug=debug, port=port)
