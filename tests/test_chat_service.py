from __future__ import annotations

import json
from importlib.resources import files

from urirun_service_chat import core


class FakeServer:
    def __init__(self) -> None:
        self.served = False

    def serve_forever(self) -> None:
        self.served = True


def test_service_manifest_declares_chat_port() -> None:
    manifest = core.service_manifest()
    assert manifest["id"] == "chat"
    assert manifest["defaultPort"] == 8194
    assert "/api/chat/ask" in manifest["http"]["api"]
    assert "/api/artifacts/dedupe" in manifest["http"]["api"]
    assert "service://host/chat/command/restart" in manifest["routes"]
    assert "service://chat/command/restart" in manifest["routes"]


def test_packaged_manifest_matches_runtime_manifest() -> None:
    packaged = json.loads(files("urirun_service_chat").joinpath("service.manifest.json").read_text())
    assert packaged == core.service_manifest()


def test_serve_delegates_to_host_dashboard_with_defaults(monkeypatch) -> None:
    calls: dict = {}
    replace_calls: dict = {}

    def fake_serve(**kwargs):
        calls.update(kwargs)
        return FakeServer()

    def fake_replace(port, *, force=False, emit=False):
        replace_calls.update({"port": port, "force": force, "emit": emit})
        return {"ok": True, "port": port, "holders": [], "targets": [], "killed": [], "remaining": []}

    monkeypatch.setattr(core.host_dashboard, "_free_port_from_old_chat", fake_replace)
    monkeypatch.setattr(core.host_dashboard, "serve", fake_serve)
    server = core.serve(project="proj", db="db.sqlite")

    assert isinstance(server, FakeServer)
    assert replace_calls == {"port": 8194, "force": False, "emit": True}
    assert server.urirun_replace["ok"] is True
    assert calls["project"] == "proj"
    assert calls["db"] == "db.sqlite"
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8194


def test_serve_can_disable_replace(monkeypatch) -> None:
    calls: dict = {"replace_called": False}

    def fake_replace(*args, **kwargs):
        calls["replace_called"] = True
        return {"ok": True}

    monkeypatch.setattr(core.host_dashboard, "_free_port_from_old_chat", fake_replace)
    monkeypatch.setattr(core.host_dashboard, "serve", lambda **kwargs: FakeServer())

    server = core.serve(replace=False)

    assert isinstance(server, FakeServer)
    assert calls["replace_called"] is False
    assert server.urirun_replace is None


def test_serve_reports_non_replaceable_port_holder(monkeypatch) -> None:
    monkeypatch.setattr(core.host_dashboard, "_free_port_from_old_chat", lambda *a, **k: {
        "ok": False,
        "port": 8194,
        "holders": [123],
        "skipped": [{"pid": 123, "cmdline": "python other.py"}],
        "remaining": [{"pid": 123, "cmdline": "python other.py"}],
    })

    try:
        core.serve()
    except OSError as exc:
        assert "non-chat process" in str(exc)
        assert "python other.py" in str(exc)
    else:
        raise AssertionError("expected OSError")


def test_main_serve_defaults_to_replace(monkeypatch, capsys) -> None:
    calls: dict = {}

    def fake_serve(**kwargs):
        calls.update(kwargs)
        server = FakeServer()
        server.urirun_replace = {"ok": True, "holders": [11], "killed": [11]}
        return server

    monkeypatch.setattr(core, "serve", fake_serve)

    assert core.main(["serve", "--host", "127.0.0.1", "--port", "8194"]) == 0
    assert calls["replace"] is True
    assert calls["force_replace"] is False
    assert '"replace": {"holders": [11], "killed": [11], "ok": true}' in capsys.readouterr().out


def test_main_serve_no_replace_flag(monkeypatch) -> None:
    calls: dict = {}
    monkeypatch.setattr(core, "serve", lambda **kwargs: calls.update(kwargs) or FakeServer())

    assert core.main(["serve", "--host", "127.0.0.1", "--port", "8194", "--no-replace"]) == 0

    assert calls["replace"] is False


def test_url_uses_env_defaults(monkeypatch) -> None:
    monkeypatch.setenv("URIRUN_CHAT_HOST", "0.0.0.0")
    monkeypatch.setenv("URIRUN_CHAT_PORT", "9000")
    assert core.dashboard_url() == "http://0.0.0.0:9000/"


def test_main_reports_start_oserror_as_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(core, "serve", lambda **kwargs: (_ for _ in ()).throw(PermissionError("denied")))

    assert core.main(["serve", "--host", "127.0.0.1", "--port", "8194"]) == 1

    captured = capsys.readouterr()
    assert '"ok": false' in captured.err
    assert "urirun.service_chat.start_failed" in captured.err
