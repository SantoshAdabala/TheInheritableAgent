# Wisdom Vault

**Authorized to Act Hackathon - Auth0 for AI Agents**

When someone passes away, their family inherits their belongings - but never their way of thinking. Wisdom Vault changes that. It lets a parent's AI-extracted decision patterns be inherited by their child through cryptographically scoped tokens, while keeping every piece of personal data permanently out of reach.

The child can ask for guidance rooted in how their parent actually lived and decided. They cannot access emails, financials, or anything personal. That boundary is enforced at the identity layer by Auth0 Token Vault - not by application code that can be changed.

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Auth0](https://img.shields.io/badge/Auth0-Token%20Vault-EB5424?style=flat-square&logo=auth0&logoColor=white)](https://auth0.com)
[![JWT](https://img.shields.io/badge/JWT-PyJWT-000000?style=flat-square&logo=jsonwebtokens&logoColor=white)](https://pyjwt.readthedocs.io)
[![Claude](https://img.shields.io/badge/Claude-Anthropic-D97706?style=flat-square)](https://anthropic.com)

[![Hackathon](https://img.shields.io/badge/Hackathon-Auth0%20for%20AI%20Agents-7C3AED?style=flat-square)](https://github.com/SantoshAdabala/TheInheritableAgent)
[![Last Commit](https://img.shields.io/github/last-commit/SantoshAdabala/TheInheritableAgent?style=flat-square&color=64748B)](https://github.com/SantoshAdabala/TheInheritableAgent/commits/main)
[![Stars](https://img.shields.io/github/stars/SantoshAdabala/TheInheritableAgent?style=flat-square&color=FBBF24)](https://github.com/SantoshAdabala/TheInheritableAgent/stargazers)

---

## Features

- **Wisdom extraction** - Claude distills life decisions into anonymous behavioral patterns. Raw input never leaves the browser.
- **Token Vault inheritance** - Auth0 issues scoped JWTs. The `raw_data:access` scope is explicitly denied at issuance, not just absent.
- **2-of-3 trustee multi-sig** - Inheritance only unlocks when two designated trustees confirm, preventing unilateral access.
- **Multi-generational delegation** - Tokens can be delegated to advisors with narrower scopes. Scopes can only shrink, never expand.
- **Step-up authentication** - Sensitive topics (grief, debt, mental health) trigger an additional confirmation step before patterns are returned.
- **Conflict resolution** - Two parents with opposing values both contribute. Claude arbitrates and synthesises a unified response.
- **Token lineage tree** - Visual graph of every token in the delegation chain with scopes on each edge.
- **GitHub import** - Commit history ingested via Token Vault, then distilled into engineering values by Claude.

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
