#!/usr/bin/env python3
"""
harness/masking.py
Write-time credential masking for the benchmark harnesses.

Any credential-like substring in captured output is replaced by

    <MASKED:<pattern-name>:<first-12-hex-of-sha256>>

and the SHA-256 of the *original* token is stored beside the masked text in the
record's ``credential_masks`` list.  That keeps two properties at once:

  * the published raw file no longer contains a string that trips provider-side
    secret scanning (the nine withheld galah bodies, docs/WITHHELD_FILES.md);
  * a reader can still verify which token they are looking at by hashing their
    own copy and comparing, without the repository republishing the value.

The masked text never contains the matched token, so masking is idempotent:
running it twice changes nothing the second time.

This module is imported by run_ssh.py and run_http.py.  It is deliberately
dependency-free (stdlib only) so the tests need no network and no paramiko.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

ENCODING = "utf-8"

#: Placeholder shape.  ``<`` and ``>`` are outside every pattern below, so a
#: masked string is never re-matched.
MASK_TEMPLATE = "<MASKED:{name}:{digest}>"
DIGEST_PREFIX = 12

#: Ordered (name, pattern) pairs.  Order matters: the specific prefixes come
#: before the generic catch-alls so the label stays informative.
CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Stripe
    ("stripe_live_key",       re.compile(r"\bsk_live_[A-Za-z0-9]{8,}\b")),
    ("stripe_prod_key",       re.compile(r"\bsk_prod_[A-Za-z0-9]{8,}\b")),
    ("stripe_test_key",       re.compile(r"\bsk_test_[A-Za-z0-9]{8,}\b")),
    ("stripe_publishable",    re.compile(r"\bpk_live_[A-Za-z0-9]{8,}\b")),
    ("stripe_publishable_test", re.compile(r"\bpk_test_[A-Za-z0-9]{8,}\b")),
    ("stripe_restricted",     re.compile(r"\brk_live_[A-Za-z0-9]{8,}\b")),
    # AWS
    ("aws_access_key_id",     re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # GitHub / Slack
    ("github_token",          re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("slack_token",           re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    # OpenAI-style key (also catches sk-proj- forms)
    ("openai_key",            re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    # JWT-like: three dot-separated base64url segments
    ("jwt",                   re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    # Bearer token, keeping the scheme word readable
    ("bearer_token",          re.compile(r"(?<=Bearer )[A-Za-z0-9._\-]{20,}")),
    # Generic long token: >= 40 chars, mixed case AND at least one digit.
    # Hex digests (lower-case only) and ordinary words do not match.
    ("long_token",            re.compile(
        r"\b(?=[A-Za-z0-9_\-]*[A-Z])(?=[A-Za-z0-9_\-]*[a-z])"
        r"(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{40,}\b")),
)

#: Fields whose content is captured from the target and may carry credentials.
DEFAULT_OUTPUT_FIELDS: tuple[str, ...] = ("raw_output", "cleaned_output", "body", "body_snippet", "error")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode(ENCODING)).hexdigest()


def mask_credentials(text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Return ``(masked_text, hits)``.

    ``hits`` is a list of ``{"pattern", "sha256", "length"}`` dicts describing
    every token that was replaced, in replacement order.  The SHA-256 is of the
    original token, never of the placeholder.
    """
    if not text:
        return text, []

    hits: list[dict[str, Any]] = []
    masked = text
    for name, pattern in CREDENTIAL_PATTERNS:
        def _replace(match: re.Match[str], name: str = name) -> str:
            original = match.group(0)
            token_hash = _digest(original)
            hits.append({
                "pattern": name,
                "sha256": token_hash,
                "length": len(original),
            })
            return MASK_TEMPLATE.format(
                name=name, digest=token_hash[:DIGEST_PREFIX]
            )
        masked = pattern.sub(_replace, masked)
    return masked, hits


def has_credentials(text: str) -> bool:
    """True if *text* contains at least one credential-like substring."""
    return any(pattern.search(text or "") for _, pattern in CREDENTIAL_PATTERNS)


def mask_record(
    record: dict[str, Any],
    enabled: bool = True,
    fields: Iterable[str] = DEFAULT_OUTPUT_FIELDS,
) -> dict[str, Any]:
    """
    Mask *fields* of *record* in place and attach ``credential_masks``.

    The key is only added when something was actually masked, so a record with
    no credentials is byte-identical to what the unmasked harness would write.
    Each hit carries the name of the field it came from.
    """
    if not enabled:
        return record

    all_hits: list[dict[str, Any]] = []
    for field in fields:
        value = record.get(field)
        if not isinstance(value, str) or not value:
            continue
        masked, hits = mask_credentials(value)
        if not hits:
            continue
        record[field] = masked
        for hit in hits:
            entry = dict(hit)
            entry["field"] = field
            all_hits.append(entry)

    if all_hits:
        record["credential_masks"] = all_hits
        record["credential_mask_count"] = len(all_hits)
    return record
