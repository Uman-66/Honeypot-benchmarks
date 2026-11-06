import importlib
import sys
import types
from pathlib import Path

import pytest


HONEYBEE_ROOT = Path(__file__).parents[1] / "honeybee"
if str(HONEYBEE_ROOT) not in sys.path:
    sys.path.insert(0, str(HONEYBEE_ROOT))


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _Column:
    def caption(self, *args, **kwargs):
        pass

    def code(self, *args, **kwargs):
        pass

    def markdown(self, *args, **kwargs):
        pass


class _FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.errors = []
        self.successes = []

    def button(self, label, **kwargs):
        return label.startswith("Generate")

    def toggle(self, *args, **kwargs):
        return False

    def spinner(self, *args, **kwargs):
        return _Context()

    def error(self, message):
        self.errors.append(message)

    def success(self, message):
        self.successes.append(message)

    def columns(self, count, **kwargs):
        return [_Column() for _ in range(count)]

    def write(self, *args, **kwargs):
        pass


def _load_tab(name, fake_streamlit):
    sys.modules["streamlit"] = fake_streamlit
    if name == "dockercompose_tab":
        yamlfix = types.ModuleType("yamlfix")
        yamlfix.fix_code = lambda value, config=None: value
        yamlfix.model = types.SimpleNamespace(
            YamlfixConfig=lambda **kwargs: kwargs,
            YamlNodeStyle=types.SimpleNamespace(KEEP_STYLE="keep"),
        )
        sys.modules["yamlfix"] = yamlfix
        oyaml = types.ModuleType("oyaml")
        oyaml.safe_load = lambda value: {}
        oyaml.safe_dump = lambda value: ""
        sys.modules["oyaml"] = oyaml
    module = importlib.import_module(f"honeybee.tabs.{name}")
    return importlib.reload(module)


TAB_CASES = [
    ("dockercompose_tab", "generate_docker_compose", "comps"),
    ("dockerfile_tab", "generate_dockerfile", "dockerfile"),
    ("nuclei_tab", "generate_nuclei", "nuclei"),
]


@pytest.mark.parametrize("tab_name,generator_name,result_name", TAB_CASES)
@pytest.mark.parametrize("generated", [None, []])
def test_generation_failure_is_reported_without_iteration(
    tab_name, generator_name, result_name, generated, monkeypatch
):
    fake_streamlit = _FakeStreamlit()
    tab = _load_tab(tab_name, fake_streamlit)
    monkeypatch.setattr(tab.generators, generator_name, lambda *args, **kwargs: generated)
    monkeypatch.setattr(tab.query_history, "save_query", lambda *args, **kwargs: None)

    tab.render(
        "PostgreSQL",
        "custom",
        None,
        ["bad config"],
        object(),
        "test-model",
        **({"docker_compose_supported": False} if tab_name == "dockercompose_tab" else {}),
    )

    assert fake_streamlit.errors == [tab.GENERATION_FAILURE_MESSAGE]
    assert result_name not in fake_streamlit.session_state


@pytest.mark.parametrize("tab_name,generator_name", [
    ("dockercompose_tab", "generate_docker_compose"),
    ("dockerfile_tab", "generate_dockerfile"),
    ("nuclei_tab", "generate_nuclei"),
])
def test_normal_generation_still_succeeds(tab_name, generator_name, monkeypatch):
    fake_streamlit = _FakeStreamlit()
    tab = _load_tab(tab_name, fake_streamlit)
    result = [{"file_type": "markdown", "file_name": "README.md", "file_content": "# ok"}]
    monkeypatch.setattr(tab.generators, generator_name, lambda *args, **kwargs: result)
    monkeypatch.setattr(tab.query_history, "save_query", lambda *args, **kwargs: None)

    tab.render(
        "PostgreSQL",
        "custom",
        None,
        ["bad config"],
        object(),
        "test-model",
        **({"docker_compose_supported": False} if tab_name == "dockercompose_tab" else {}),
    )

    assert not fake_streamlit.errors
    expected_success = {
        "dockercompose_tab": "Docker Compose generated successfully!",
        "dockerfile_tab": "Dockerfile generated successfully!",
        "nuclei_tab": "Nuclei generated successfully!",
    }
    assert fake_streamlit.successes == [expected_success[tab_name]]
