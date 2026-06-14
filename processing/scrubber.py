"""
Evidence and entity text scrubber.

Redacts credentials, API keys, tokens, and other secret patterns
from text before persistence or export. Applied at the persistence
boundary — not during scoring or signal detection.
"""
from __future__ import annotations

import re

# Pattern: generic API key / secret token (long hex/base64 strings in key=value context)
_API_KEY_RE = re.compile(
    r'(?i)(?:api[_-]?key|token|secret|password|auth|bearer|access[_-]?key)'
    r'\s*[=:]\s*["\']?([A-Za-z0-9+/=_\-]{16,})["\']?'
)
# Pattern: AWS-style access key
_AWS_KEY_RE = re.compile(r'(?:AKIA|AIPA|ASIA)[A-Z0-9]{16}')
# Pattern: private key PEM block
_PEM_RE = re.compile(r'-----BEGIN [A-Z ]+-----[\s\S]+?-----END [A-Z ]+-----')
# Pattern: JWT token (three base64url segments)
_JWT_RE = re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
# Pattern: hex secrets ≥32 chars in key=value position
_HEX_SECRET_RE = re.compile(
    r'(?i)(?:token|secret|key|hash|digest)\s*[=:]\s*["\']?([0-9a-fA-F]{32,})["\']?'
)

_REDACTED = "[REDACTED]"

_PATTERNS: list[tuple[re.Pattern, str | None]] = [
    (_PEM_RE,      None),   # replace entire match
    (_JWT_RE,      None),
    (_AWS_KEY_RE,  None),
    (_API_KEY_RE,  "\\1"),  # group 1 is the value — replace value only
    (_HEX_SECRET_RE, "\\1"),
]


def scrub_text(text: str) -> str:
    if not text:
        return text
    result = text
    for pattern, group in _PATTERNS:
        if group is None:
            result = pattern.sub(_REDACTED, result)
        else:
            # Replace only the captured group (the secret value), keep the key name
            def _replace_group(m: re.Match) -> str:
                full = m.group(0)
                val = m.group(1)
                return full.replace(val, _REDACTED, 1)
            result = pattern.sub(_replace_group, result)
    return result


def scrub_entity_texts(attributes: dict) -> dict:
    """Scrub all string values in an entity attributes dict in-place."""
    return {
        k: scrub_text(v) if isinstance(v, str) else v
        for k, v in attributes.items()
    }
