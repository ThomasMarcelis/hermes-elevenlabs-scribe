"""Install into a disposable profile; use real discovery, config and HTTP multipart."""

import json
import shutil
import socket
import sys
import wave
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
import yaml

PLUGIN = Path(__file__).resolve().parents[1]
NAME = "elevenlabs-scribe"


@pytest.fixture
def stub(monkeypatch):
    calls = []
    reply = {"status": 200, "body": {"text": " synthetic transcript "}}
    connect = socket.socket.connect

    def local_only(sock, address):
        assert isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}, address
        return connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", local_only)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            message = BytesParser(policy=default).parsebytes(
                f'Content-Type: {self.headers["Content-Type"]}\r\nMIME-Version: 1.0\r\n\r\n'.encode() + raw)
            parts = [(part.get_param("name", header="Content-Disposition"),
                      part.get_filename(), part.get_payload(decode=True))
                     for part in message.iter_parts()]
            calls.append({"path": self.path, "key": self.headers.get("xi-api-key"),
                          "parts": parts, "raw": raw})
            body = reply["body"]
            payload = json.dumps(body).encode() if not isinstance(body, bytes) else body
            self.send_response(reply["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield SimpleNamespace(url=f"http://127.0.0.1:{server.server_port}/v1",
                              calls=calls, reply=reply)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.fixture
def installed(tmp_path, monkeypatch, stub):
    home = tmp_path / "home"
    home.mkdir()
    profile = tmp_path / "profile"
    target = profile / "plugins" / NAME
    target.mkdir(parents=True)
    # A native directory install is supported by Hermes; no source-tree import shortcut.
    for path in PLUGIN.iterdir():
        if path.suffix == ".py" or path.name in {"plugin.yaml", "LICENSE"}:
            shutil.copy2(path, target / path.name)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(profile))
    monkeypatch.setenv("ELEVENLABS_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.delenv("HERMES_LOCAL_STT_LANGUAGE", raising=False)
    import hermes_cli.plugins as plugins
    from agent import transcription_registry
    from tools.transcription_tools import transcribe_audio

    # Check the interpreter's editable install has not selected a sibling checkout.
    for module in (plugins, transcription_registry, sys.modules[transcribe_audio.__module__]):
        assert Path(module.__file__).is_relative_to(Path.cwd()), module.__file__
    plugins._reset_plugin_managers_for_tests()
    cfg = {"plugins": {"enabled": [NAME]}, "stt": {"provider": NAME,
           "cloud_trim_silence": False, NAME: {"base_url": stub.url, "model": "scribe_v2"}}}
    audio = tmp_path / "synthetic.wav"
    with wave.open(str(audio), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\x01\x00" * 1600)

    def write_config():
        (profile / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def dispatch(**kwargs):
        write_config()
        return transcribe_audio(str(audio), **kwargs)

    write_config()
    context = SimpleNamespace(cfg=cfg, settings=cfg["stt"][NAME], home=home,
                              profile=profile, target=target, audio=audio,
                              dispatch=dispatch, write_config=write_config, stub=stub)
    try:
        yield context
    finally:
        plugins._reset_plugin_managers_for_tests()
        transcription_registry._reset_for_tests()


def fields(call):
    return [(name, body.decode()) for name, filename, body in call["parts"] if filename is None]
