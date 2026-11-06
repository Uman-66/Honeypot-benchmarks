import csv
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "harness" / "api_probe.py"
SPEC = importlib.util.spec_from_file_location("api_probe", MODULE_PATH)
api_probe = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(api_probe)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b'{"choices":[]}'


def test_probe_uses_fake_http_and_writes_utf8_csv(tmp_path):
    seen = {}

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["authorization"] = request.get_header("Authorization")
        seen["body"] = request.data
        return FakeResponse()

    output = tmp_path / "api_probe.csv"
    row = api_probe.probe_once(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        output_path=output,
        opener=fake_open,
        clock=iter((10.0, 10.25)).__next__,
    )

    assert row["http_status"] == "200"
    assert row["error_type"] == ""
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["timeout"] == 60
    assert seen["authorization"] == "Bearer test-key"
    assert b'"max_tokens": 16' in seen["body"]
    with output.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [row]
