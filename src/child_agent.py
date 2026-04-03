"""
Child Agent — validates tokens and returns scoped wisdom patterns.

AI inference runs in the browser via Puter.js.
This module enforces scope boundaries and returns filtered patterns.
"""


class ChildAgent:
    def __init__(self, token_vault_bridge):
        self.vault = token_vault_bridge

    def fetch_patterns(self, inheritance_token: str) -> dict:
        """
        Validate a token and return scoped wisdom patterns.

        Scope filtering:
          wisdom:read → all patterns
          wisdom:career → only career patterns
          wisdom:finance → only finance patterns
          etc.

        Delegation tokens with narrower scopes only see matching pattern categories.
        """
        validation = self.vault.validate_token(inheritance_token)
        if not validation["valid"]:
            return {
                "error": "Invalid or expired inheritance token",
                "detail": validation.get("error"),
                "blocked": True,
            }

        claims = validation["claims"]
        scopes = set(claims.get("scope", "").split())

        if not any(s.startswith("wisdom:") for s in scopes):
            return {
                "error": "Token does not grant any wisdom scope",
                "granted_scopes": sorted(scopes),
                "blocked": True,
            }

        # Determine which pattern categories this token can access
        allowed_categories = None  # None = all
        if "wisdom:read" not in scopes:
            allowed_categories = set()
            for scope in scopes:
                if scope.startswith("wisdom:"):
                    allowed_categories.add(scope.split(":", 1)[1])

        parent_id = claims.get("parent_id") or claims.get("root_parent_id")
        patterns = self.vault.get_wisdom_patterns(parent_id, allowed_categories)

        return {
            "patterns": patterns,
            "scope_used": sorted(scopes),
            "allowed_categories": sorted(allowed_categories) if allowed_categories else "all",
            "raw_data_accessible": False,
            "child_id": claims.get("sub"),
            "delegation_depth": claims.get("delegation_depth", 0),
        }

    def resolve_conflict(self, token_a: str, token_b: str) -> dict:
        """
        Validate two inheritance tokens from different parents and return
        both pattern sets for Claude to arbitrate.
        """
        val_a = self.vault.validate_token(token_a)
        val_b = self.vault.validate_token(token_b)

        if not val_a["valid"]:
            return {"error": f"Token A invalid: {val_a.get('error')}", "blocked": True}
        if not val_b["valid"]:
            return {"error": f"Token B invalid: {val_b.get('error')}", "blocked": True}

        claims_a, claims_b = val_a["claims"], val_b["claims"]

        for label, claims in [("A", claims_a), ("B", claims_b)]:
            scopes = set(claims.get("scope", "").split())
            if not any(s.startswith("wisdom:") for s in scopes):
                return {"error": f"Token {label} missing wisdom scope", "blocked": True}

        parent_a = claims_a.get("parent_id") or claims_a.get("root_parent_id")
        parent_b = claims_b.get("parent_id") or claims_b.get("root_parent_id")

        if parent_a == parent_b:
            return {"error": "Both tokens resolve to the same parent", "blocked": True}

        patterns_a = self.vault.get_wisdom_patterns(parent_a)
        patterns_b = self.vault.get_wisdom_patterns(parent_b)

        if not patterns_a:
            return {"error": "Parent A vault is empty", "blocked": True}
        if not patterns_b:
            return {"error": "Parent B vault is empty", "blocked": True}

        return {
            "patterns_a": patterns_a,
            "patterns_b": patterns_b,
            "parent_a": parent_a,
            "parent_b": parent_b,
            "child_a": claims_a.get("sub"),
            "child_b": claims_b.get("sub"),
        }

    def attempt_raw_access(self, inheritance_token: str) -> dict:
        """
        Attempt to access raw personal data. Always 403.
        raw_data:access is explicitly denied in the token at issuance.
        """
        validation = self.vault.validate_token(inheritance_token)
        if not validation["valid"]:
            return {"blocked": True, "reason": "Invalid token", "detail": validation.get("error")}

        claims = validation["claims"]
        return {
            "blocked": True,
            "http_status": 403,
            "reason": "Token Vault scope enforcement",
            "detail": (
                "The raw_data:access scope was explicitly denied at token issuance. "
                "Enforcement lives in Auth0's identity layer — not application code. "
                "Modifying this application cannot bypass it."
            ),
            "granted_scopes": sorted(claims.get("scope", "").split()),
            "denied_scopes": sorted(claims.get("denied_scopes", [])),
        }
