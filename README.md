# Wisdom Vault

**Authorized to Act Hackathon — Auth0 for AI Agents**

When someone passes away, their family inherits their belongings — but never their way of thinking. Wisdom Vault changes that. It lets a parent's AI-extracted decision patterns be inherited by their child through cryptographically scoped tokens, while keeping every piece of personal data permanently out of reach.

The child can ask for guidance rooted in how their parent actually lived and decided. They cannot access emails, financials, or anything personal. That boundary is enforced at the identity layer by Auth0 Token Vault — not by application code that can be changed.

---

## Features

- **Wisdom extraction** — Claude distills life decisions into anonymous behavioral patterns. Raw input never leaves the browser.
- **Token Vault inheritance** — Auth0 issues scoped JWTs. The `raw_data:access` scope is explicitly denied at issuance, not just absent.
- **2-of-3 trustee multi-sig** — Inheritance only unlocks when two designated trustees confirm, preventing unilateral access.
- **Multi-generational delegation** — Tokens can be delegated to advisors with narrower scopes. Scopes can only shrink, never expand.
- **Step-up authentication** — Sensitive topics (grief, debt, mental health) trigger an additional confirmation step before patterns are returned.
- **Conflict resolution** — Two parents with opposing values both contribute. Claude arbitrates and synthesises a unified response.
- **Token lineage tree** — Visual graph of every token in the delegation chain with scopes on each edge.
- **GitHub import** — Commit history ingested via Token Vault, then distilled into engineering values by Claude.

---

## Getting Started

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.template .env
# Add your credentials to .env

python app.py
```

Open `http://127.0.0.1:5000`.

---

## Environment Variables

| Variable | Description |
|---|---|
| `AUTH0_DOMAIN` | Your Auth0 tenant domain |
| `AUTH0_CLIENT_ID` | Application client ID |
| `GROQ_API_KEY` | Free API key from console.groq.com |
| `FLASK_SECRET_KEY` | Any long random string |

Without Auth0 credentials the app runs in demo mode using locally signed RSA JWTs. All scope enforcement still applies.

---

## Auth0 Setup

1. Create a **Regular Web Application** in Auth0 (not SPA, not Native)
2. Advanced Settings → Grant Types → enable **Token Vault**
3. Advanced Settings → Application Authentication → select **Private Key JWT**
4. Run the app once to auto-generate `keys/public_key.pem`, then register it under Advanced Settings → Keys
5. Auth0 Management API → authorize your app with `read:users` and `update:users`

---

## How It Works

The inheritance token is a signed JWT with explicit scope grants and denials baked in at issuance:

```
scope: wisdom:read wisdom:career wisdom:finance ...
denied_scopes: raw_data:access personal_history:read
```

The child presents this token to fetch patterns. The server validates it, filters patterns by the granted scopes, and returns only what the token allows. Attempting to access raw data always returns 403 — not because the app checks a flag, but because the scope was denied at the identity layer.

---

## License

MIT
