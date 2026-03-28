"""Tests for the HTTP API server handler."""
from __future__ import annotations
import json
from io import BytesIO
from unittest.mock import MagicMock
import pytest

def _import_server():
    import dictateme.server as srv
    return srv

class _FakeSocket:
    def __init__(self):
        self.response = BytesIO()
    def makefile(self, mode="rb", buffering=-1):
        if "w" in mode: return self.response
        return BytesIO()
    def sendall(self, data):
        self.response.write(data)

def _make_handler(method, path, body=None, srv_module=None):
    if srv_module is None: srv_module = _import_server()
    body_bytes = b""
    if body is not None: body_bytes = json.dumps(body).encode("utf-8")
    CRLF = chr(13) + chr(10)
    rl = f"{method} {path} HTTP/1.1" + CRLF
    hd = "Host: 127.0.0.1:18234" + CRLF
    if body_bytes:
        hd += f"Content-Length: {len(body_bytes)}" + CRLF
        hd += "Content-Type: application/json" + CRLF
    raw = (rl + hd + CRLF).encode("utf-8") + body_bytes
    sock = _FakeSocket()
    orig = sock.makefile
    def _mf(mode="rb", buffering=-1):
        if "r" in mode: return BytesIO(raw)
        return orig(mode, buffering)
    sock.makefile = _mf
    h = srv_module.DictateMeHandler(request=sock, client_address=("127.0.0.1", 9999), server=MagicMock())
    return h, sock.response.getvalue()

def _parse_response(raw):
    text = raw.decode("utf-8", errors="replace")
    CRLF = chr(13) + chr(10)
    first_line, rest = text.split(CRLF, 1)
    status_code = int(first_line.split(" ", 2)[1])
    _, body_str = rest.split(CRLF + CRLF, 1)
    if body_str.strip(): return status_code, json.loads(body_str)
    return status_code, {}

class TestStatusEndpoint:
    def test_ready_no_components(self):
        srv = _import_server()
        srv._state.config = None; srv._state.audio = None
        srv._state.stt = None; srv._state.llm = None
        srv._state.model_loaded = False; srv._state.model_loading = False
        _, raw = _make_handler("GET", "/status", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200
        assert d["status"] == "ready"
        assert d["model_loaded"] is False
        assert d["model_loading"] is False
        assert d["recording"] is False

    def test_recording_true(self):
        srv = _import_server()
        ma = MagicMock(); ma.is_recording = True
        srv._state.audio = ma; srv._state.model_loaded = True; srv._state.model_loading = False
        _, raw = _make_handler("GET", "/status", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200 and d["recording"] is True and d["model_loaded"] is True

class TestSettingsEndpoint:
    def test_get_settings_ok(self):
        srv = _import_server()
        from dictateme.core.config import AppConfig
        srv._state.config = AppConfig()
        _, raw = _make_handler("GET", "/settings", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200 and "general" in d and "audio" in d
        assert d["audio"]["sample_rate"] == 16000

    def test_get_settings_no_config_500(self):
        srv = _import_server()
        srv._state.config = None
        _, raw = _make_handler("GET", "/settings", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 500 and "error" in d

class TestStartRecordingEndpoint:
    def test_ok(self):
        srv = _import_server()
        ma = MagicMock(); srv._state.audio = ma
        _, raw = _make_handler("POST", "/start_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200 and d["status"] == "recording"
        ma.start_recording.assert_called_once()

    def test_no_audio_503(self):
        srv = _import_server()
        srv._state.audio = None
        _, raw = _make_handler("POST", "/start_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 503 and "Audio not initialised" in d["error"]

class TestStopRecordingEndpoint:
    def test_not_recording_409(self):
        srv = _import_server()
        ma = MagicMock(); ma.is_recording = False
        srv._state.audio = ma; srv._state.stt = MagicMock()
        _, raw = _make_handler("POST", "/stop_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 409 and "Not currently recording" in d["error"]

    def test_no_audio_503(self):
        srv = _import_server()
        srv._state.audio = None; srv._state.stt = None
        _, raw = _make_handler("POST", "/stop_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 503

    def test_empty_audio(self):
        srv = _import_server()
        import numpy as np
        ma = MagicMock(); ma.is_recording = True
        ma.stop_recording.return_value = np.array([])
        srv._state.audio = ma; srv._state.stt = MagicMock()
        from dictateme.core.config import AppConfig
        srv._state.config = AppConfig()
        _, raw = _make_handler("POST", "/stop_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200 and d["text"] == "" and d["duration"] == 0.0

    def test_transcribes(self):
        srv = _import_server()
        import numpy as np
        ma = MagicMock(); ma.is_recording = True
        ma.stop_recording.return_value = np.zeros(16000)
        srv._state.audio = ma
        ms = MagicMock(); mr = MagicMock(); mr.text = "hello world"
        ms.transcribe.return_value = mr
        srv._state.stt = ms; srv._state.model_loaded = True; srv._state.llm = None
        from dictateme.core.config import AppConfig
        srv._state.config = AppConfig()
        _, raw = _make_handler("POST", "/stop_recording", srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200
        assert d["text"] == "hello world" and d["raw"] == "hello world"
        assert d["duration"] == 1.0

class TestReformatEndpoint:
    def test_missing_text_400(self):
        srv = _import_server()
        _, raw = _make_handler("POST", "/reformat", body={"text": ""}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 400 and "Missing text" in d["error"]

    def test_llm_disabled_503(self):
        srv = _import_server()
        srv._state.llm = None
        _, raw = _make_handler("POST", "/reformat", body={"text": "hi"}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 503 and "LLM not enabled" in d["error"]

    def test_invalid_format_400(self):
        srv = _import_server()
        ml = MagicMock(); ml.is_enabled = True; srv._state.llm = ml
        _, raw = _make_handler("POST", "/reformat", body={"text": "hi", "format": "bad"}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 400 and "Unknown format" in d["error"]

class TestInsertEndpoint:
    def test_missing_text_400(self):
        srv = _import_server()
        _, raw = _make_handler("POST", "/insert", body={"text": ""}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 400 and "Missing text" in d["error"]

    def test_no_inserter_503(self):
        srv = _import_server()
        srv._state.inserter = None
        _, raw = _make_handler("POST", "/insert", body={"text": "hello"}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 503 and "Inserter not initialised" in d["error"]

    def test_success(self):
        srv = _import_server()
        mi = MagicMock(); mi.insert_text.return_value = True; srv._state.inserter = mi
        _, raw = _make_handler("POST", "/insert", body={"text": "hello"}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 200 and d["status"] == "ok"
        mi.insert_text.assert_called_once_with("hello")

    def test_failure_500(self):
        srv = _import_server()
        mi = MagicMock(); mi.insert_text.return_value = False; srv._state.inserter = mi
        _, raw = _make_handler("POST", "/insert", body={"text": "hello"}, srv_module=srv)
        s, d = _parse_response(raw)
        assert s == 500 and "Insertion failed" in d["error"]

class TestNotFoundRoute:
    def test_get_404(self):
        _, raw = _make_handler("GET", "/nonexistent")
        s, d = _parse_response(raw)
        assert s == 404
    def test_post_404(self):
        _, raw = _make_handler("POST", "/nonexistent")
        s, d = _parse_response(raw)
        assert s == 404

class TestCorsAndOptions:
    def test_options_204(self):
        _, raw = _make_handler("OPTIONS", "/status")
        text = raw.decode("utf-8", errors="replace")
        CRLF = chr(13) + chr(10)
        assert "204" in text.split(CRLF, 1)[0]

    def test_cors_headers(self):
        srv = _import_server()
        srv._state.config = None; srv._state.audio = None
        srv._state.model_loaded = False; srv._state.model_loading = False
        _, raw = _make_handler("GET", "/status", srv_module=srv)
        text = raw.decode("utf-8", errors="replace")
        assert "Access-Control-Allow-Origin" in text

class TestHelperFunctions:
    def test_dict_to_toml_simple(self):
        srv = _import_server()
        result = srv._dict_to_toml({"key": "value", "num": 42})
        assert "num = 42" in result
    def test_dict_to_toml_nested(self):
        srv = _import_server()
        result = srv._dict_to_toml({"section": {"a": 1, "b": "hello"}})
        assert "[section]" in result and "a = 1" in result
    def test_toml_value_types(self):
        srv = _import_server()
        assert srv._toml_value(True) == "true"
        assert srv._toml_value(False) == "false"
        assert srv._toml_value(42) == "42"
        assert srv._toml_value(3.14) == "3.14"
        assert srv._toml_value([1, 2, 3]) == "[1, 2, 3]"

class TestReadJsonBody:
    def test_invalid_json_400(self):
        srv = _import_server()
        CRLF = chr(13) + chr(10)
        invalid_body = b"not valid json"
        rl = "POST /insert HTTP/1.1" + CRLF
        hd = "Host: 127.0.0.1:18234" + CRLF
        hd += f"Content-Length: {len(invalid_body)}" + CRLF
        hd += "Content-Type: application/json" + CRLF
        raw = (rl + hd + CRLF).encode("utf-8") + invalid_body
        sock = _FakeSocket()
        orig = sock.makefile
        def _mf(mode="rb", buffering=-1):
            if "r" in mode: return BytesIO(raw)
            return orig(mode, buffering)
        sock.makefile = _mf
        srv.DictateMeHandler(request=sock, client_address=("127.0.0.1", 9999), server=MagicMock())
        resp = sock.response.getvalue().decode("utf-8", errors="replace")
        assert "400" in resp and "Invalid JSON" in resp
