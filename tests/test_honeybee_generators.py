import json
import sys
from pathlib import Path


HONEYBEE_ROOT = Path(__file__).parents[1] / "honeybee"
if str(HONEYBEE_ROOT) not in sys.path:
    sys.path.insert(0, str(HONEYBEE_ROOT))

from honeybee.src.generators import _strip_think_and_fences
from harness.honeybee_generate import _score_output


def test_strip_none_and_empty():
    assert _strip_think_and_fences(None) == ""
    assert _strip_think_and_fences("") == ""


def test_strip_think_only():
    assert _strip_think_and_fences("<think>internal reasoning</think>") == ""


def test_strip_think_and_fenced_json():
    value = '{"id": "x"}'
    assert json.loads(_strip_think_and_fences(f"<think>why</think>```json\n{value}\n```")) == {"id": "x"}


def test_strip_fenced_json_array_and_object():
    assert json.loads(_strip_think_and_fences("```json\n[1, 2]\n```")) == [1, 2]
    assert json.loads(_strip_think_and_fences("```json\n{\"a\": 1}\n```")) == {"a": 1}


def test_strip_plain_json_and_no_fence():
    assert json.loads(_strip_think_and_fences('{"plain": true}')) == {"plain": True}
    assert _strip_think_and_fences("plain response") == "plain response"


def _file(name, content, file_type="YAML"):
    return {
        "file_name": name,
        "file_path": ".",
        "file_type": file_type,
        "file_content": content,
    }


def test_multifile_compose_scores_only_compose_primary():
    output = [
        _file("postgresql.conf", "log_connections = off"),
        _file("docker-compose.yaml", "services:\n  db:\n    image: postgres\n    ports: ['5432:5432']\n    environment:\n      POSTGRES_PASSWORD:\n"),
        _file("README.md", "# PostgreSQL"),
    ]
    scored = _score_output("docker_compose", "PostgreSQL", output, "stop")
    assert scored["primary_found"] is True
    assert scored["syntactic_ok"] is True
    assert scored["semantic_ok"] is True
    assert {item["name"] for item in scored["auxiliary_files"]} == {
        "postgresql.conf", "README.md"
    }


def test_dockerfile_bundle_ignores_readme():
    output = [
        _file("Dockerfile", "FROM postgres:16\n"),
        _file("README.md", "# build instructions"),
        _file("datasource.yaml", "apiVersion: v1\n"),
    ]
    scored = _score_output("dockerfile", "PostgreSQL", output, "stop")
    assert scored["syntactic_ok"] is True
    assert scored["semantic_ok"] is True
    assert scored["valid"] is True


def test_truncated_accepted_attempt_is_invalid():
    output = [_file("Dockerfile", "FROM postgres:16\n")]
    scored = _score_output("dockerfile", "PostgreSQL", output, "length")
    assert scored["truncated_accepted"] is True
    assert scored["syntactic_ok"] is False
    assert scored["semantic_ok"] is False
    assert scored["valid"] is False


def test_all_length_attempts_without_content_are_length_limited():
    scored = _score_output(
        "dockerfile", "PostgreSQL", None, accepted_finish_reason="length",
        length_limited=True,
    )
    assert scored["length_limited"] is True
    assert scored["produced_output"] is False
    assert scored["primary_found"] is False
    assert scored["valid"] is False


def test_missing_primary_file_is_not_scored():
    output = [_file("README.md", "# no primary")]
    scored = _score_output("dockerfile", "PostgreSQL", output, "stop")
    assert scored["primary_found"] is False
    assert scored["syntactic_ok"] is False
    assert scored["valid"] is False
