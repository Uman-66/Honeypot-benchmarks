#!/usr/bin/env python3
"""
harness/honeybee_generate.py
────────────────────────────
Offline harness for honeybee's generator core.

Runs a fixed set of benchmark cases through honeybee's generators (no
Streamlit, no browser) and writes outputs to results/honeybee/<case>_runNN/.

SAFETY RULES (enforced here):
  - Generated files are written as INERT TEXT under results/honeybee/.
  - Nothing is executed.  No subprocess.  No docker.sock.
  - No secrets are printed or logged.

Usage (from repo root, with OPENAI_API_KEY and OPENAI_BASE_URL set):
  python harness/honeybee_generate.py [--runs N] [--dry-run]

The script exits non-zero if any run produces zero output files or a
file that fails YAML parsing (when it is expected to be YAML).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml  # PyYAML – already a honeybee dep


# ── Path setup ────────────────────────────────────────────────────────────────
# This script lives in harness/, one level below the repo root.
# The honeybee source tree is at <repo_root>/honeybee/honeybee/.
REPO_ROOT = Path(__file__).resolve().parent.parent
HONEYBEE_PKG = REPO_ROOT / "honeybee" / "honeybee"

# Add the honeybee package directory to sys.path so we can import its modules
# directly from the source tree (no install required for the harness itself,
# though the container does run `pip install`).
if str(HONEYBEE_PKG.parent) not in sys.path:
    sys.path.insert(0, str(HONEYBEE_PKG.parent))

# Now import honeybee's internal modules (no Streamlit involved).
try:
    from honeybee.src.client_provider import get_llm_client  # type: ignore
    from honeybee.src import generators  # type: ignore
except ImportError as exc:
    sys.exit(
        f"ERROR: Cannot import honeybee modules from {HONEYBEE_PKG.parent}.\n"
        f"  Make sure you run this script from the repo root and that\n"
        f"  `pip install -e honeybee/` (or `pip install honeybee/`) has been run.\n"
        f"  Import error: {exc}"
    )

# ── Benchmark cases ───────────────────────────────────────────────────────────
# Two cases from the honeybee README examples.
# Each case runs generate_docker_compose (always) and optionally
# generate_dockerfile and generate_nuclei.

CASES: list[dict[str, Any]] = [
    {
        # README example 1
        "id": "postgresql_no_password",
        "application": "PostgreSQL",
        "misconfigurations": [
            "Weak password policies or no password set",
            "Trust authentication method used allowing login without password",
            "Remote access allowed to all IPs (listen_addresses configuration set to '*')",
        ],
        "generators": ["docker_compose", "dockerfile", "nuclei"],
    },
    {
        # README example 2
        "id": "grafana_multi_misconfig",
        "application": "Grafana",
        "misconfigurations": [
            "Default admin password not changed",
            "Admin user exposed to the internet",
            "No data source authentication",
            "Failure to set up role-based access control (RBAC)",
        ],
        "generators": ["docker_compose", "dockerfile", "nuclei"],
    },
]

# ── Validity checks ───────────────────────────────────────────────────────────
REQUIRED_KEYS_FILE = {"file_name", "file_path", "file_type", "file_content"}


def _type_guess(name: str, content: str) -> str:
    lower_name = name.lower()
    first_line = next(
        (line.strip() for line in content.splitlines()
         if line.strip() and not line.lstrip().startswith(("#", "//", "/*"))),
        "",
    )
    if lower_name.startswith("readme") or lower_name.endswith(".md"):
        return "markdown"
    if lower_name.endswith((".sql", ".psql")):
        return "sql"
    if lower_name.endswith((".sh", ".bash", ".cmd", ".ps1")):
        return "shell"
    if lower_name.startswith("dockerfile") or first_line.upper().startswith("FROM "):
        return "dockerfile"
    if lower_name.endswith((".yaml", ".yml")):
        return "yaml"
    if lower_name.endswith((".conf", ".ini", ".cfg")):
        return "config"
    return "text"


def _file_info(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": "unnamed", "type_guess": "unknown", "content": "",
                "errors": [f"Expected dict, got {type(item).__name__}"]}
    missing = REQUIRED_KEYS_FILE - item.keys()
    return {
        "name": str(item.get("file_name") or "unnamed"),
        "type_guess": _type_guess(
            str(item.get("file_name") or ""),
            str(item.get("file_content") or ""),
        ),
        "content": str(item.get("file_content") or ""),
        "errors": [f"Missing keys: {', '.join(sorted(missing))}"] if missing else [],
    }


def _classify_files(gen_type: str, output: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(output, list):
        return None, []
    infos = [_file_info(item) for item in output]
    primary = None
    if gen_type == "docker_compose":
        named = [
            info for info in infos
            if re.search(r"(^|[/\\])(?:docker-compose|compose)[^/\\]*\.ya?ml$",
                         info["name"], re.IGNORECASE)
        ]
        if named:
            primary = named[0]
        else:
            for info in infos:
                if info["type_guess"] != "yaml":
                    continue
                try:
                    parsed = yaml.safe_load(info["content"])
                except yaml.YAMLError:
                    continue
                if isinstance(parsed, dict) and "services" in parsed:
                    primary = info
                    break
    elif gen_type == "dockerfile":
        for info in infos:
            first = next(
                (line.strip() for line in info["content"].splitlines()
                 if line.strip() and not line.lstrip().startswith("#")),
                "",
            )
            if info["name"].lower().split("/")[-1].startswith("dockerfile") or \
                    first.upper().startswith("FROM "):
                primary = info
                break
    return primary, [info for info in infos if info is not primary]


def _check_file_item(item: Any) -> list[str]:
    """Return a list of validity errors for a single file-item dict."""
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"Expected dict, got {type(item).__name__}"]
    missing = REQUIRED_KEYS_FILE - item.keys()
    if missing:
        errors.append(f"Missing keys: {missing}")
    ft = str(item.get("file_type", "")).lower()
    content = item.get("file_content", "")
    if ft in ("yaml", "yml") and content:
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            errors.append(f"YAML parse error in {item.get('file_name')}: {e}")
    return errors


def _semantic_check(gen_type: str, application: str, output: Any) -> tuple[bool | None, list[str]]:
    """Run static format/content checks only; this is not a security verdict."""
    if gen_type == "dockerfile":
        if not isinstance(output, dict):
            return False, ["Dockerfile primary artifact is missing"]
        first = next(
            (line.strip() for line in output["content"].splitlines()
             if line.strip() and not line.lstrip().startswith("#")),
            "",
        )
        ok = first.upper().startswith("FROM ")
        return ok, [] if ok else [f"Missing FROM in {output['name']}"]
    if gen_type == "nuclei":
        if not isinstance(output, str):
            return False, ["Nuclei primary artifact is missing"]
        try:
            parsed = yaml.safe_load(output)
        except yaml.YAMLError as exc:
            return False, [f"Nuclei YAML parse error: {exc}"]
        if not isinstance(parsed, dict):
            return False, ["Nuclei template is not a mapping"]
        missing = [key for key in ("id", "info") if key not in parsed]
        if "http" not in parsed and "requests" not in parsed:
            missing.append("http or requests")
        return not missing, [f"Nuclei missing {', '.join(missing)}"] if missing else []
    if gen_type == "docker_compose":
        if not isinstance(output, dict):
            return False, ["Compose primary artifact is missing"]
        try:
            compose = yaml.safe_load(output["content"])
        except yaml.YAMLError as exc:
            return False, [f"Compose YAML parse error: {exc}"]
        semantic_errors: list[str] = []
        if not isinstance(compose, dict) or not compose.get("services"):
            semantic_errors.append("Compose document has no services")
            return False, semantic_errors
        service_values = list(compose["services"].values())
        ports = [str(port) for service in service_values if isinstance(service, dict)
                 for port in service.get("ports", [])]
        env_values: list[Any] = []
        for service in service_values:
            if not isinstance(service, dict):
                continue
            environment = service.get("environment", []) or []
            env_values.extend(
                f"{key}={'' if value is None else value}"
                for key, value in environment.items()
            ) if isinstance(environment, dict) else env_values.extend(environment)
        env_text = "\n".join(
            f"{item.get('name', '')}={'' if item.get('value') is None else item.get('value')}"
            if isinstance(item, dict) else str(item)
            for item in env_values
        )
        if application.lower() == "postgresql":
            if not any("5432:5432" in port or port.startswith("5432") for port in ports):
                semantic_errors.append("PostgreSQL port 5432 is not published")
            password = re.search(r"(?im)^POSTGRES_PASSWORD\s*=\s*(.*)$", env_text)
            trust = "trust" in env_text.lower()
            if password and password.group(1).strip(" '\"") and not trust:
                semantic_errors.append("PostgreSQL password is non-empty and trust auth is absent")
        if application.lower() == "grafana":
            checks = {
                "anonymous access": "GF_AUTH_ANONYMOUS_ENABLED=true",
                "admin password": "GF_SECURITY_ADMIN_PASSWORD=admin",
                "sign-up": "GF_USERS_ALLOW_SIGN_UP=true",
            }
            for label, needle in checks.items():
                if needle.lower() not in env_text.lower():
                    semantic_errors.append(f"Grafana {label} check failed")
            if not any("3000:3000" in port or port.startswith("3000") for port in ports):
                semantic_errors.append("Grafana port 3000 is not published")
        return not semantic_errors, semantic_errors
    return None, []


def _validate_output(gen_type: str, application: str, output: Any) -> dict[str, Any]:
    """
    Returns {"valid": bool, "errors": [...], "files": int}.
    For nuclei the output is a raw string (YAML or JSON); for the others it
    is a list of file-item dicts.
    """
    if output is None:
        return {"valid": False, "semantic_ok": False,
                "errors": ["Generator returned None (all retries exhausted)"], "files": 0}

    if gen_type == "nuclei":
        # Raw string — just check it is non-empty and try to parse as YAML
        if not isinstance(output, str) or not output.strip():
            return {"valid": False, "semantic_ok": False,
                    "errors": ["Nuclei output is empty or not a string"], "files": 0}
        errors: list[str] = []
        try:
            yaml.safe_load(output)
        except yaml.YAMLError as e:
            errors.append(f"Nuclei YAML parse error: {e}")
        semantic_ok, semantic_errors = _semantic_check(gen_type, application, output)
        return {"valid": not errors, "semantic_ok": semantic_ok,
                "errors": errors + semantic_errors, "files": 1}

    # docker_compose / dockerfile: list of file-item dicts
    if not isinstance(output, list) or len(output) == 0:
        return {"valid": False, "semantic_ok": False,
                "errors": [f"Expected non-empty list, got {type(output).__name__}"], "files": 0}
    all_errors: list[str] = []
    for i, item in enumerate(output):
        errs = _check_file_item(item)
        all_errors.extend([f"[item {i}] {e}" for e in errs])
    semantic_ok, semantic_errors = _semantic_check(gen_type, application, output)
    return {"valid": not all_errors, "semantic_ok": semantic_ok,
            "errors": all_errors + semantic_errors, "files": len(output)}


def _score_output(
    gen_type: str,
    application: str,
    output: Any,
    accepted_finish_reason: str | None = None,
    length_limited: bool | None = None,
) -> dict[str, Any]:
    """Score only the primary artifact; static check, not a security verdict."""
    truncated = accepted_finish_reason == "length"
    if length_limited is None:
        length_limited = truncated
    if gen_type == "nuclei":
        primary_found = isinstance(output, str) and bool(output.strip())
        errors: list[str] = []
        if primary_found:
            try:
                yaml.safe_load(output)
            except yaml.YAMLError as exc:
                errors.append(f"Nuclei YAML parse error: {exc}")
        semantic_ok, semantic_errors = _semantic_check(
            gen_type, application, output if primary_found else None
        )
        return {
            "primary_found": primary_found,
            "produced_output": primary_found,
            "syntactic_ok": primary_found and not errors and not truncated,
            "semantic_ok": semantic_ok if primary_found and not errors and not truncated else False,
            "truncated_accepted": bool(truncated),
            "length_limited": bool(length_limited),
            "valid": bool(primary_found and not errors and not truncated),
            "errors": errors + semantic_errors,
            "files": 1 if primary_found else 0,
            "auxiliary_files": [],
        }
    if not isinstance(output, list) or not output:
        return {
            "primary_found": False, "syntactic_ok": False, "semantic_ok": False,
            "produced_output": False,
            "truncated_accepted": bool(truncated), "valid": False,
            "length_limited": bool(length_limited),
            "errors": [f"Expected non-empty list, got {type(output).__name__}"],
            "files": 0, "auxiliary_files": [],
        }
    primary, auxiliaries = _classify_files(gen_type, output)
    auxiliary_files = [
        {"name": info["name"], "type_guess": info["type_guess"]}
        for info in auxiliaries
    ]
    if primary is None:
        return {
            "primary_found": False, "syntactic_ok": False, "semantic_ok": False,
            "produced_output": bool(output),
            "truncated_accepted": bool(truncated), "valid": False,
            "length_limited": bool(length_limited),
            "errors": [f"No primary {gen_type} artifact found"],
            "files": len(output), "auxiliary_files": auxiliary_files,
        }
    errors = list(primary["errors"])
    try:
        parsed = yaml.safe_load(primary["content"]) if gen_type == "docker_compose" else None
        syntactic_ok = (
            isinstance(parsed, (dict, list))
            if gen_type == "docker_compose"
            else bool(primary["content"].strip())
        )
    except yaml.YAMLError as exc:
        syntactic_ok = False
        errors.append(f"Compose YAML parse error: {exc}")
    semantic_ok, semantic_errors = _semantic_check(gen_type, application, primary)
    errors.extend(semantic_errors)
    return {
        "primary_found": True,
        "produced_output": True,
        "syntactic_ok": syntactic_ok and not truncated,
        "semantic_ok": semantic_ok if syntactic_ok and not truncated else False,
        "truncated_accepted": bool(truncated),
        "length_limited": bool(length_limited),
        "valid": bool(syntactic_ok and not truncated),
        "errors": errors,
        "files": len(output),
        "primary_file": primary["name"],
        "auxiliary_files": auxiliary_files,
    }


# ── Output writer ─────────────────────────────────────────────────────────────

def _write_outputs(out_dir: Path, gen_type: str, output: Any) -> None:
    """Write generator output to out_dir as inert text files.  Never executed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if gen_type == "nuclei":
        (out_dir / "nuclei_template.yaml").write_text(str(output), encoding="utf-8")
        return
    if isinstance(output, list):
        for item in output:
            fname = item.get("file_name", f"output_{gen_type}.txt")
            (out_dir / fname).write_text(str(item.get("file_content", "")), encoding="utf-8")
    else:
        (out_dir / f"output_{gen_type}.txt").write_text(str(output), encoding="utf-8")


def _read_dotenv_key(path: Path, key: str) -> str | None:
    """Read one KEY=VALUE entry without printing or exposing the file."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip("\"'")
    except OSError:
        return None
    return None


def _attempt_metadata() -> dict[str, Any]:
    attempts = getattr(generators, "LAST_ATTEMPTS", [])
    finish_reasons = [item.get("finish_reason") for item in attempts]
    return {
        "attempts": len(attempts),
        "finish_reasons": finish_reasons,
        "completion_tokens": [item.get("completion_tokens") for item in attempts],
        "accepted_finish_reason": (
            attempts[-1].get("finish_reason") if attempts else None
        ),
        "length_limited": "length" in finish_reasons,
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_generator: dict[str, list[dict[str, Any]]] = {}
    by_case: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_generator.setdefault(record["generator"], []).append(record)
        by_case.setdefault(record["case_id"], []).append(record)

    def counts(items: list[dict[str, Any]]) -> dict[str, str | int]:
        n = len(items)
        return {
            "n": n,
            "produced_output": f"{sum(bool(item.get('produced_output')) for item in items)}/{n}",
            "clean_ok": f"{sum(bool(item.get('semantic_ok')) and not bool(item.get('truncated_accepted')) for item in items)}/{n}",
            "length_limited": f"{sum(bool(item.get('length_limited')) for item in items)}/{n}",
        }

    return {
        "by_generator": {name: counts(items) for name, items in sorted(by_generator.items())},
        "by_case": {name: counts(items) for name, items in sorted(by_case.items())},
        "note": "n=3 per cell means no confidence statements.",
    }


def _case_map() -> dict[str, dict[str, Any]]:
    return {case["id"]: case for case in CASES}


def _rescore_directory(root: Path, selected_cases: set[str] | None) -> int:
    validity_path = root / "validity.json"
    if not validity_path.exists():
        print(f"ERROR: {validity_path} not found.")
        return 1
    records = json.loads(validity_path.read_text(encoding="utf-8"))
    case_map = _case_map()
    rescored: list[dict[str, Any]] = []
    for original in records:
        case_id = original["case_id"]
        if selected_cases and case_id not in selected_cases:
            continue
        run = original["run"]
        generator = original["generator"]
        output_dir = root / f"{case_id}_{run}" / generator
        output: Any
        if generator == "nuclei":
            template = output_dir / "nuclei_template.yaml"
            output = template.read_text(encoding="utf-8") if template.exists() else ""
        else:
            items = []
            if output_dir.exists():
                for path in sorted(output_dir.iterdir()):
                    if path.is_file():
                        items.append({
                            "file_name": path.name,
                            "file_path": ".",
                            "file_type": _type_guess(path.name, path.read_text(encoding="utf-8")),
                            "file_content": path.read_text(encoding="utf-8"),
                        })
            output = items
        finishes = original.get("finish_reasons", [])
        accepted = finishes[-1] if finishes else None
        length_limited = "length" in finishes
        scored = _score_output(
            generator,
            case_map.get(case_id, {}).get("application", ""),
            output,
            accepted_finish_reason=accepted,
            length_limited=length_limited,
        )
        rescored.append({
            "case_id": case_id,
            "run": run,
            "generator": generator,
            "attempts": original.get("attempts", 0),
            "finish_reasons": finishes,
            "completion_tokens": original.get("completion_tokens", []),
            "length_limited": length_limited,
            **scored,
            "produced_output": bool(output),
            "dry_run": original.get("dry_run", False),
        })
    (root / "validity_rescored.json").write_text(
        json.dumps(rescored, indent=2), encoding="utf-8"
    )
    (root / "summary_rescored.json").write_text(
        json.dumps(_summary(rescored), indent=2), encoding="utf-8"
    )
    print(f"Wrote {root / 'validity_rescored.json'}")
    print(f"Wrote {root / 'summary_rescored.json'}")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="honeybee benchmark harness")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs per case (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls; write placeholder files")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Maximum completion tokens (default: MAX_TOKENS or 8192)")
    parser.add_argument("--cases", default=None,
                        help="Comma-separated case IDs to run")
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "results" / "honeybee"),
                        help="Output directory (default: results/honeybee)")
    parser.add_argument("--rescore", default=None,
                        help="Rescore saved outputs in this directory without API calls")
    args = parser.parse_args()
    selected_cases = (
        {name.strip() for name in args.cases.split(",") if name.strip()}
        if args.cases else None
    )
    if args.rescore:
        return _rescore_directory(Path(args.rescore), selected_cases)

    # ── Credentials check ────────────────────────────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY") or _read_dotenv_key(REPO_ROOT / ".env", "OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        sys.exit("ERROR: OPENAI_API_KEY not set in the environment or repo-root .env.")

    # ── Build a minimal settings dict (no Streamlit) ─────────────────────────
    base_url = os.getenv("OPENAI_BASE_URL") or _read_dotenv_key(REPO_ROOT / ".env", "OPENAI_BASE_URL")
    model = os.getenv("MODEL") or _read_dotenv_key(REPO_ROOT / ".env", "MODEL") or "accounts/fireworks/models/glm-5p3-flash"
    temperature = float(os.getenv("TEMPERATURE", "0.2"))
    max_tokens = args.max_tokens if args.max_tokens is not None else int(os.getenv("MAX_TOKENS", "8192"))
    if base_url and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = base_url

    settings = {
        "provider": "OpenAI",
        "api_key": api_key or "dry-run-placeholder",
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    client = get_llm_client(settings)

    configured_root = Path(args.out_dir)
    if not configured_root.is_absolute():
        configured_root = REPO_ROOT / configured_root
    results_root = (
        REPO_ROOT / "results" / "honeybee_dryrun"
        if args.dry_run and args.out_dir == str(REPO_ROOT / "results" / "honeybee")
        else configured_root
    )
    results_root.mkdir(parents=True, exist_ok=True)

    validity_records: list[dict[str, Any]] = []
    overall_ok = True

    active_cases = [
        case for case in CASES
        if selected_cases is None or case["id"] in selected_cases
    ]
    for case in active_cases:
        for run_idx in range(1, args.runs + 1):
            run_label = f"run{run_idx:02d}"
            run_dir = results_root / f"{case['id']}_{run_label}"
            run_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n── {case['id']} / {run_label} ─────────────────────────")

            for gen_type in case["generators"]:
                out_dir = run_dir / gen_type
                output: Any = None
                errors: list[str] = []
                generators.LAST_ATTEMPTS = []

                if args.dry_run:
                    output = (
                        [{"file_name": "dry-run.yaml", "file_path": ".", "file_type": "YAML",
                          "file_content": "# dry-run placeholder\n"}]
                        if gen_type != "nuclei"
                        else "# dry-run nuclei placeholder\n"
                    )
                else:
                    try:
                        if gen_type == "docker_compose":
                            output = generators.generate_docker_compose(
                                client, model, case["application"], case["misconfigurations"],
                                temperature=temperature, max_tokens=max_tokens,
                            )
                        elif gen_type == "dockerfile":
                            output = generators.generate_dockerfile(
                                client, model, case["application"], case["misconfigurations"],
                                temperature=temperature, max_tokens=max_tokens,
                            )
                        elif gen_type == "nuclei":
                            output = generators.generate_nuclei(
                                client, model, case["application"], case["misconfigurations"],
                                temperature=temperature, max_tokens=max_tokens,
                            )
                    except Exception as exc:
                        errors.append(f"{type(exc).__name__}: {str(exc).splitlines()[0]}")
                        print(f"  ✗ {gen_type}: EXCEPTION {errors[-1]}")

                attempt_metadata = _attempt_metadata()
                accepted_finish_reason = attempt_metadata["accepted_finish_reason"]
                validity = _score_output(
                    gen_type, case["application"], output,
                    accepted_finish_reason=accepted_finish_reason,
                    length_limited=attempt_metadata["length_limited"],
                )
                if errors:
                    validity["valid"] = False
                    validity["errors"] = errors + validity["errors"]

                status = "✓" if validity["valid"] else "✗"
                print(f"  {status} {gen_type}: {validity['files']} file(s), "
                      f"valid={validity['valid']}"
                      + (f", errors={validity['errors']}" if validity["errors"] else ""))

                if not validity["valid"]:
                    overall_ok = False

                # Write outputs — always, even on partial failure, so you can
                # inspect raw model responses.
                if output is not None:
                    _write_outputs(out_dir, gen_type, output)

                record = {
                    "case_id": case["id"],
                    "run": run_label,
                    "generator": gen_type,
                    **attempt_metadata,
                    **validity,
                    "errors": validity["errors"],
                    "dry_run": args.dry_run,
                    "produced_output": bool(output),
                }
                validity_records.append(record)

    # ── Write consolidated validity record ───────────────────────────────────
    validity_path = results_root / "validity.json"
    validity_path.write_text(json.dumps(validity_records, indent=2), encoding="utf-8")
    print(f"\n── Validity record written to {validity_path} ──")
    (results_root / "summary.json").write_text(
        json.dumps(_summary(validity_records), indent=2), encoding="utf-8"
    )
    if args.dry_run:
        print("DRY RUN - placeholder output, not results")

    passed = sum(1 for r in validity_records if r["valid"])
    total = len(validity_records)
    print(f"── {passed}/{total} generator runs valid ──")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
