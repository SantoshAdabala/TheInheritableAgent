import os
import time
import uuid
from pathlib import Path

import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEYS_DIR = Path(__file__).parent.parent / "keys"

WISDOM_SCOPES = [
    "wisdom:read",
    "wisdom:career",
    "wisdom:finance",
    "wisdom:relationships",
    "wisdom:values",
    "wisdom:risk",
]

SENSITIVE_KEYWORDS = {
    "death", "die", "dying", "grief", "divorce", "inheritance", "estate",
    "terminal", "suicide", "debt", "bankrupt", "affair", "abuse",
    "depression", "anxiety", "addiction", "rehab", "widow", "orphan",
    "funeral", "will", "testament", "cancer",
}


class TokenVaultBridge:
    def __init__(self):
        self.domain = os.getenv("AUTH0_DOMAIN", "")
        self.client_id = os.getenv("AUTH0_CLIENT_ID", "")
        self.client_secret = os.getenv("AUTH0_CLIENT_SECRET", "")
        self.demo_mode = not (self.domain and self.client_id)

        self._demo_vault: dict = {}
        self._demo_tokens: dict = {}
        self._audit_log: list = []

        KEYS_DIR.mkdir(exist_ok=True)
        self._private_key, self._public_key = self._load_or_generate_keys()

    def _audit(self, event: str, actor: str, detail: str, outcome: str = "ok", scopes=None):
        self._audit_log.append({
            "ts": time.strftime("%H:%M:%S"),
            "event": event,
            "actor": actor.replace("auth0|", ""),
            "detail": detail,
            "outcome": outcome,
            "scopes": scopes or [],
        })
        if len(self._audit_log) > 200:
            self._audit_log.pop(0)

    def get_audit_log(self) -> list:
        return list(reversed(self._audit_log))

    def _load_or_generate_keys(self):
        priv_path = KEYS_DIR / "private_key.pem"
        pub_path = KEYS_DIR / "public_key.pem"
        if priv_path.exists() and pub_path.exists():
            with open(priv_path, "rb") as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None)
            with open(pub_path, "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())
        else:
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )
            public_key = private_key.public_key()
            with open(priv_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
            with open(pub_path, "wb") as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ))
        return private_key, public_key

    def get_public_key_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def _create_token_vault_jwt(self, user_id: str, scopes: list) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self.client_id, "sub": user_id,
                "aud": f"https://{self.domain}/",
                "iat": now, "exp": now + 300,
                "jti": str(uuid.uuid4()),
                "scope": " ".join(scopes),
            },
            self._private_key,
            algorithm="RS256",
            headers={"typ": "token-vault-req+jwt"},
        )

    def _get_management_token(self) -> str:
        now = int(time.time())
        client_assertion = jwt.encode(
            {
                "iss": self.client_id, "sub": self.client_id,
                "aud": f"https://{self.domain}/oauth/token",
                "iat": now, "exp": now + 300, "jti": str(uuid.uuid4()),
            },
            self._private_key, algorithm="RS256",
        )
        resp = requests.post(
            f"https://{self.domain}/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion,
                "audience": f"https://{self.domain}/api/v2/",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def deposit_wisdom(self, user_id: str, wisdom_patterns: list) -> dict:
        self._demo_vault[user_id] = {
            "wisdom_patterns": wisdom_patterns,
            "deposited_at": time.time(),
            "trustees_confirmed": [],
            "inheritance_unlocked": False,
        }
        self._audit("VAULT DEPOSIT", user_id, f"{len(wisdom_patterns)} patterns stored — raw decisions discarded")
        return {
            "status": "deposited",
            "pattern_count": len(wisdom_patterns),
            "mode": "demo" if self.demo_mode else "live",
        }

    def confirm_trustee(self, user_id: str, trustee_id: str, confirmation_token: str) -> dict:
        vault = self._demo_vault.get(user_id)
        if not vault:
            return {"error": "No vault found for this user"}
        trustees = vault.get("trustees_confirmed", [])
        if any(t["trustee_id"] == trustee_id for t in trustees):
            return {"status": "already_confirmed", "trustee_id": trustee_id}
        trustees.append({
            "trustee_id": trustee_id,
            "confirmation_token": confirmation_token,
            "confirmed_at": time.time(),
        })
        vault["trustees_confirmed"] = trustees
        threshold_met = len(trustees) >= 2
        if threshold_met:
            vault["inheritance_unlocked"] = True
        self._audit(
            "TRUSTEE CONFIRMED",
            trustee_id,
            f"{len(trustees)}/3 confirmations — {'inheritance UNLOCKED' if threshold_met else 'threshold not yet met'}",
            outcome="unlocked" if threshold_met else "pending",
        )
        return {
            "status": "confirmed",
            "trustee_id": trustee_id,
            "confirmations": len(trustees),
            "threshold_met": threshold_met,
            "mode": "demo" if self.demo_mode else "live",
        }

    def get_wisdom_patterns(self, parent_id: str, allowed_categories: set = None) -> list:
        patterns = self._demo_vault.get(parent_id, {}).get("wisdom_patterns", [])
        if allowed_categories:
            patterns = [p for p in patterns if p.get("category") in allowed_categories]
        return patterns

    def _mint_token(self, payload: dict) -> str:
        return jwt.encode(payload, self._private_key, algorithm="RS256")  # type: ignore[arg-type]

    def issue_inheritance_token(self, parent_id: str, child_id: str) -> dict:
        vault = self._demo_vault.get(parent_id)
        if not vault:
            return {"error": "No vault found for parent"}
        if not vault.get("inheritance_unlocked"):
            return {"error": "Inheritance not yet unlocked", "detail": "2-of-3 trustee confirmations required"}

        if not self.demo_mode:
            try:
                vault_jwt = self._create_token_vault_jwt(user_id=parent_id, scopes=WISDOM_SCOPES)
                resp = requests.post(
                    f"https://{self.domain}/oauth/token",
                    json={
                        "grant_type": "urn:auth0:params:oauth:grant-type:token-vault",
                        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                        "client_assertion": vault_jwt,
                        "subject_token": child_id,
                        "scope": " ".join(WISDOM_SCOPES),
                    },
                    timeout=10,
                )
                if resp.ok:
                    data = resp.json()
                    return {
                        "inheritance_token": data["access_token"],
                        "scopes": WISDOM_SCOPES,
                        "denied_scopes": ["raw_data:access", "personal_history:read"],
                        "expires_in": data.get("expires_in", 86400),
                        "mode": "live-auth0",
                    }
            except Exception:
                pass

        now = int(time.time())
        token_id = str(uuid.uuid4())
        payload = {
            "iss": self.client_id or "wisdom-vault-demo",
            "sub": child_id,
            "parent_id": parent_id,
            "aud": "wisdom-vault-api",
            "iat": now, "exp": now + 86400, "jti": token_id,
            "scope": " ".join(WISDOM_SCOPES),
            "denied_scopes": ["raw_data:access", "personal_history:read"],
            "delegation_depth": 0,
        }
        token = self._mint_token(payload)
        self._demo_tokens[token_id] = {
            "parent_id": parent_id,
            "child_id": child_id,
            "issued_at": now,
            "revoked": False,
            "granted_scopes": WISDOM_SCOPES,
            "depth": 0,
            "parent_token_id": None,
        }
        mode = "demo" if self.demo_mode else "live-rsa"
        self._audit(
            "TOKEN ISSUED",
            child_id,
            f"inherits from {parent_id.replace('auth0|','')} | mode: {mode} | denied: raw_data:access",
            outcome="ok",
            scopes=WISDOM_SCOPES,
        )
        return {
            "inheritance_token": token,
            "token_id": token_id,
            "scopes": WISDOM_SCOPES,
            "denied_scopes": ["raw_data:access", "personal_history:read"],
            "expires_in": 86400,
            "mode": mode,
        }

    def delegate_token(self, issuer_token: str, delegate_to: str, requested_scopes: list) -> dict:
        validation = self.validate_token(issuer_token)
        if not validation["valid"]:
            return {"error": "Invalid issuer token", "blocked": True}

        claims = validation["claims"]
        issuer_scopes = set(claims.get("scope", "").split())
        depth = claims.get("delegation_depth", 0)

        if depth >= 2:
            return {"error": "Maximum delegation depth (2) reached", "blocked": True}

        allowed = sorted(set(requested_scopes) & issuer_scopes)
        if not allowed:
            return {
                "error": "Scopes can only narrow, never expand",
                "detail": f"Issuer has: {sorted(issuer_scopes)}. Requested: {requested_scopes}",
                "blocked": True,
            }

        parent_token_id = claims.get("jti")
        root_parent_id = claims.get("parent_id") or claims.get("root_parent_id")
        original_denied = set(claims.get("denied_scopes", []))
        newly_denied = issuer_scopes - set(allowed)
        all_denied = sorted(original_denied | newly_denied)

        now = int(time.time())
        token_id = str(uuid.uuid4())
        payload = {
            "iss": claims.get("iss"),
            "sub": delegate_to,
            "root_parent_id": root_parent_id,
            "delegated_from": claims.get("sub"),
            "parent_token_id": parent_token_id,
            "aud": "wisdom-vault-api",
            "iat": now, "exp": now + 86400, "jti": token_id,
            "scope": " ".join(allowed),
            "denied_scopes": all_denied,
            "delegation_depth": depth + 1,
        }
        token = self._mint_token(payload)
        self._demo_tokens[token_id] = {
            "parent_id": root_parent_id,
            "child_id": delegate_to,
            "delegated_from": claims.get("sub"),
            "parent_token_id": parent_token_id,
            "issued_at": now,
            "revoked": False,
            "granted_scopes": allowed,
            "depth": depth + 1,
        }
        self._audit(
            "DELEGATION",
            delegate_to,
            f"delegated from {str(claims.get('sub','')).replace('auth0|','')} | depth {depth+1} | narrowed to {len(allowed)} scope(s)",
            outcome="ok",
            scopes=allowed,
        )
        return {
            "delegation_token": token,
            "token_id": token_id,
            "scopes": allowed,
            "denied_scopes": all_denied,
            "depth": depth + 1,
            "delegated_from": claims.get("sub"),
            "delegate_to": delegate_to,
            "expires_in": 86400,
        }

    def validate_token(self, token: str) -> dict:
        try:
            pub_pem = self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            claims = jwt.decode(token, pub_pem, algorithms=["RS256"], audience="wisdom-vault-api")
            token_id = claims.get("jti")
            if token_id and self._demo_tokens.get(token_id, {}).get("revoked"):
                self._audit("SCOPE CHECK", claims.get("sub", "unknown"), "token revoked", outcome="denied")
                return {"valid": False, "error": "Token has been revoked"}
            scopes = claims.get("scope", "").split()
            self._audit("SCOPE CHECK", claims.get("sub", "unknown"), f"token valid | depth {claims.get('delegation_depth',0)}", outcome="ok", scopes=scopes)
            return {"valid": True, "claims": claims}
        except jwt.ExpiredSignatureError:
            self._audit("SCOPE CHECK", "unknown", "token expired", outcome="denied")
            return {"valid": False, "error": "Token has expired"}
        except jwt.InvalidTokenError as exc:
            self._audit("SCOPE CHECK", "unknown", f"invalid token: {exc}", outcome="denied")
            return {"valid": False, "error": str(exc)}

    def revoke_token(self, token_id: str) -> dict:
        if token_id not in self._demo_tokens:
            return {"error": "Token not found"}
        self._demo_tokens[token_id]["revoked"] = True
        return {"status": "revoked", "token_id": token_id}

    def get_lineage_graph(self, root_parent_id: str = None, token: str = None) -> dict:
        if token:
            validation = self.validate_token(token)
            if not validation["valid"]:
                return {"error": "Invalid token", "nodes": [], "edges": []}
            claims = validation["claims"]
            root_parent_id = claims.get("parent_id") or claims.get("root_parent_id")

        if not root_parent_id:
            return {"nodes": [], "edges": []}

        label = root_parent_id.replace("auth0|", "")
        nodes = [{
            "id": f"parent_{root_parent_id}",
            "label": label,
            "type": "parent",
            "scopes": ["all wisdom scopes"],
            "depth": -1,
        }]
        edges = []

        for jti, meta in self._demo_tokens.items():
            if meta.get("revoked"):
                continue
            pid = meta.get("parent_id") or meta.get("root_parent_id")
            if pid != root_parent_id:
                continue

            subject = meta.get("child_id", jti[:8]).replace("auth0|", "")
            depth = meta.get("depth", 0)
            scopes = meta.get("granted_scopes", ["wisdom:read"])

            nodes.append({
                "id": jti,
                "label": subject,
                "type": "advisor" if depth > 0 else "child",
                "scopes": scopes,
                "depth": depth,
            })

            if depth == 0:
                edges.append({
                    "from": f"parent_{root_parent_id}",
                    "to": jti,
                    "scopes": scopes,
                    "label": "inherits all",
                })
            else:
                parent_jti = meta.get("parent_token_id")
                if parent_jti:
                    edges.append({
                        "from": parent_jti,
                        "to": jti,
                        "scopes": scopes,
                        "label": f"delegates: {', '.join(scopes)}",
                    })

        return {"nodes": nodes, "edges": edges, "root_parent_id": root_parent_id}

    def requires_step_up(self, question: str) -> list:
        words = set(question.lower().split())
        found = words & SENSITIVE_KEYWORDS
        categories = []
        if found & {"death", "die", "dying", "terminal", "funeral", "widow", "orphan", "cancer", "grief"}:
            categories.append("death & grief")
        if found & {"debt", "bankrupt", "inheritance", "estate", "will", "testament"}:
            categories.append("finances & estate")
        if found & {"divorce", "affair", "abuse"}:
            categories.append("relationships")
        if found & {"suicide", "depression", "anxiety", "addiction", "rehab"}:
            categories.append("mental health")
        return categories

    def store_github_token(self, user_id: str, github_token: str) -> dict:
        if user_id not in self._demo_vault:
            self._demo_vault[user_id] = {
                "wisdom_patterns": [],
                "deposited_at": time.time(),
                "trustees_confirmed": [],
                "inheritance_unlocked": False,
            }
        self._demo_vault[user_id]["github_token"] = github_token
        return {"status": "stored", "user_id": user_id}

    def ingest_github_commits(self, github_token: str, github_username: str) -> dict:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token and github_token != "demo":
            headers["Authorization"] = f"Bearer {github_token}"
        resp = requests.get(
            f"https://api.github.com/users/{github_username}/events?per_page=100",
            headers=headers,
            timeout=15,
        )
        if not resp.ok:
            return {"error": f"GitHub API error {resp.status_code} — for private repos provide a Personal Access Token", "commits": []}

        commits = []
        for event in resp.json():
            if event.get("type") == "PushEvent":
                for commit in event.get("payload", {}).get("commits", []):
                    msg = commit.get("message", "").strip().split("\n")[0]
                    if msg and not msg.lower().startswith("merge"):
                        commits.append(msg)

        return {"commits": commits[:50], "commit_count": min(len(commits), 50)}
