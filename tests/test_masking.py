"""Tests for harness/masking.py (write-time credential masking)."""

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
if str(ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(ROOT / "harness"))

from masking import (  # noqa: E402
    CREDENTIAL_PATTERNS,
    has_credentials,
    mask_credentials,
    mask_record,
)

# Fixtures built at runtime so no scanner pattern fires on these source lines.
# Each value is split at the boundary of the trigger prefix.
STRIPE_LIVE = "sk_live" + "_51H8xYzSecretKey987654321"
STRIPE_PROD = "sk_prod" + "_ABCdef1234567890"
STRIPE_TEST = "sk_test" + "_4eC39HqLyjWDarjtT1zdp7dc"
STRIPE_PUBLISHABLE = "pk_live" + "_51H8xYzExampleKey123456"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"          # documentation example; excluded from pattern
GITHUB_TOKEN = "ghp_" + "a" * 36
SLACK_TOKEN = "xox" + "b-123456789012-abcdefghijkl"
# JWT: base64url(header).base64url(payload).signature — split to avoid "eyJ" prefix literal
_J = "ey"
JWT = (
    _J + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    "." + _J + "JzdWIiOiIxMjM0NTY3ODkwIn0"
    ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)

SECRETS = [
    STRIPE_LIVE, STRIPE_PROD, STRIPE_TEST, STRIPE_PUBLISHABLE,
    AWS_KEY, GITHUB_TOKEN, SLACK_TOKEN, JWT,
]


def test_every_secret_is_masked_and_never_survives():
    for secret in SECRETS:
        masked, hits = mask_credentials(f"value={secret} end")
        assert secret not in masked, secret
        assert hits, secret
        assert "<MASKED:" in masked
        assert masked.endswith(" end")


def test_sha256_of_the_original_is_kept_beside_the_masked_text():
    masked, hits = mask_credentials(f"STRIPE_SECRET={STRIPE_LIVE}")
    expected = hashlib.sha256(STRIPE_LIVE.encode()).hexdigest()
    assert hits[0]["sha256"] == expected
    assert hits[0]["pattern"] == "stripe_live_key"
    assert hits[0]["length"] == len(STRIPE_LIVE)
    # The placeholder carries a prefix of the digest, so it can be matched by eye.
    assert expected[:12] in masked


def test_bearer_scheme_is_preserved_but_the_token_is_not():
    token = "abcdef0123456789abcdef0123456789"
    masked, hits = mask_credentials(f"Authorization: Bearer {token}")
    assert "Bearer " in masked
    assert token not in masked
    assert hits[0]["pattern"] == "bearer_token"


def test_masking_is_idempotent():
    once, _ = mask_credentials(f"{STRIPE_LIVE} {AWS_KEY} {JWT}")
    twice, hits = mask_credentials(once)
    assert twice == once
    assert hits == []


def test_ordinary_output_is_untouched():
    text = (
        "total 8\n"
        "drwxr-xr-x 2 guest guest 4096 Nov  6 14:03 bm_dir\n"
        "-rw-r--r-- 1 guest guest    0 Nov  6 14:03 bm.txt\n"
        "uid=1000(guest) gid=1000(guest) groups=1000(guest)\n"
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
    )
    masked, hits = mask_credentials(text)
    assert masked == text
    assert hits == []
    assert not has_credentials(text)


def test_hex_digests_are_not_treated_as_long_tokens():
    digest = "a" * 64
    masked, _ = mask_credentials(digest)
    assert masked == digest


def test_long_mixed_case_token_is_caught():
    token = "Ab3" + "xY9" * 10  # 33 chars -> extended below to >40
    token = token + "Q7zR2tLm"  # 41 chars, mixed case + digits
    masked, hits = mask_credentials(token)
    assert token not in masked
    assert hits and hits[0]["pattern"] == "long_token"


def test_mask_record_annotates_the_field_and_skips_clean_records():
    record = {
        "cmd_id": "cat_config",
        "raw_output": f"STRIPE_SECRET={STRIPE_LIVE}\n",
        "cleaned_output": f"STRIPE_SECRET={STRIPE_LIVE}\n",
        "body": None,
    }
    masked = mask_record(record, enabled=True)
    assert STRIPE_LIVE not in masked["raw_output"]
    assert STRIPE_LIVE not in masked["cleaned_output"]
    assert masked["credential_mask_count"] == 2
    assert {hit["field"] for hit in masked["credential_masks"]} == {
        "raw_output", "cleaned_output"
    }

    clean = {"cmd_id": "pwd", "cleaned_output": "/tmp"}
    assert mask_record(clean, enabled=True) == {"cmd_id": "pwd", "cleaned_output": "/tmp"}


def test_disabled_masking_reproduces_the_old_behaviour():
    record = {"cleaned_output": f"x={STRIPE_LIVE}"}
    assert mask_record(record, enabled=False) == {"cleaned_output": f"x={STRIPE_LIVE}"}
    assert "credential_masks" not in record


def test_pattern_table_names_are_unique():
    names = [name for name, _ in CREDENTIAL_PATTERNS]
    assert len(names) == len(set(names))
