#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Claude Code proxy:
- Select upstream URL in a small web UI
- Show models (try /v1/models, fallback to static list)
- Proxy /v1/messages to the selected upstream with an added token query param
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
STATE_PATH = ROOT_DIR / "proxy_state.json"

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "accept-encoding",
}


def extract_base_url(api_base_url: str) -> str:
    if "/anthropic/v1/messages" in api_base_url:
        return api_base_url.replace("/anthropic/v1/messages", "")
    if "/v1/chat/completions" in api_base_url:
        return api_base_url.replace("/v1/chat/completions", "")
    if "/v1/messages" in api_base_url:
        return api_base_url.replace("/v1/messages", "")
    return api_base_url.rstrip("/")


def append_token(url: str, token: str, token_param: str) -> str:
    if not token:
        return url
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append((token_param, token))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


class ProxyState:
    def __init__(self, config: Dict[str, Any], config_path: Path) -> None:
        self._lock = threading.Lock()
        self._config = config
        self._initial_config = json.loads(json.dumps(config))
        self._config_path = config_path
        self._state = self._load_state()
        self._providers = config.get("Providers", [])

    def _load_state(self) -> Dict[str, Any]:
        if STATE_PATH.exists():
            with STATE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_state(self) -> None:
        try:
            with STATE_PATH.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=True)
        except OSError as exc:
            logging.warning("state: failed to persist proxy_state.json (%s)", exc)

    def get_token_param(self) -> str:
        return self._config.get("TOKEN_PARAM", "token")

    def get_timeout(self) -> float:
        timeout_ms = self._config.get("API_TIMEOUT_MS", "600000")
        try:
            return float(timeout_ms) / 1000.0
        except (TypeError, ValueError):
            return 600.0

    def get_providers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._providers)

    def get_selected_provider(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._state.get("selection_required"):
                return None
            selected = self._state.get("selected_provider")
            if selected:
                for p in self._providers:
                    if p.get("name") == selected:
                        return p
            return self._providers[0] if self._providers else None

    def set_selected_provider(self, name: str) -> bool:
        with self._lock:
            if any(p.get("name") == name for p in self._providers):
                self._state["selected_provider"] = name
                if self._state.get("selection_required"):
                    self._state["selection_required"] = False
                self.save_state()
                return True
        return False

    def update_provider_models(self, name: str, models: List[str]) -> None:
        with self._lock:
            for p in self._providers:
                if p.get("name") == name:
                    p["models"] = models
                    break

    def reload_config(self) -> None:
        with self._lock:
            try:
                config = load_config(self._config_path)
            except OSError as exc:
                logging.warning("config: failed to reload (%s)", exc)
                return
            self._config = config
            self._providers = config.get("Providers", [])
            selected = self._state.get("selected_provider")
            if selected and any(p.get("name") == selected for p in self._providers):
                return
            if self._providers:
                self._state["selected_provider"] = self._providers[0].get("name", "")
                self.save_state()

    def reset_config(self) -> None:
        with self._lock:
            self._config = json.loads(json.dumps(self._initial_config))
            self._providers = self._config.get("Providers", [])
            self._state["selected_provider"] = ""
            self._state["selection_required"] = True
            self._state["provider_overrides"] = {}
            self.save_state()

    def get_provider_override(self, name: str) -> Dict[str, Any]:
        with self._lock:
            overrides = self._state.get("provider_overrides", {})
            return dict(overrides.get(name, {}))

    def set_provider_override(self, name: str, override: Dict[str, Any]) -> None:
        with self._lock:
            overrides = self._state.get("provider_overrides", {})
            overrides[name] = override
            self._state["provider_overrides"] = overrides
            self.save_state()

    def get_log_level(self) -> str:
        return str(self._config.get("LOG_LEVEL", "info")).lower()

    def get_log_enabled(self) -> bool:
        return bool(self._config.get("LOG", True))


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def fetch_models(
    provider: Dict[str, Any],
    token_param: str,
    timeout: float,
    override: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[List[str]], Optional[str]]:
    api_base_url = provider.get("api_base_url", "")
    if not api_base_url:
        return None, "missing api_base_url"
    base_url = extract_base_url(api_base_url)
    token = provider.get("token") or provider.get("api_key") or ""
    token_in = str((override or {}).get("token_in") or provider.get("token_in", "header")).lower()
    url = f"{base_url}/v1/models"
    if token_in in ("query", "both"):
        url = append_token(url, token, token_param)
    headers = {}
    if token and token_in in ("header", "both"):
        header_name = (override or {}).get("token_header") or provider.get("token_header", "Authorization")
        header_format = (override or {}).get("token_header_format") or provider.get("token_header_format", "Bearer {token}")
        headers[header_name] = header_format.format(token=token)
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
        if models:
            return models, None
        return None, "empty model list"
    except Exception as exc:
        return None, str(exc)


def refresh_all_models(state: ProxyState) -> None:
    token_param = state.get_token_param()
    timeout = min(state.get_timeout(), 10.0)
    for provider in state.get_providers():
        if provider.get("name") == "Note":
            continue
        override = state.get_provider_override(provider.get("name", ""))
        models, error = fetch_models(provider, token_param, timeout, override)
        if models:
            state.update_provider_models(provider.get("name", ""), models)
        elif error:
            logging.info("models: refresh failed provider=%s error=%s", provider.get("name", ""), error)


def merge_query(url: str, extra_query: str) -> str:
    if not extra_query:
        return url
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.extend(urllib.parse.parse_qsl(extra_query, keep_blank_values=True))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "ClaudeProxy/0.1"

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length > 0 else b""

    def _serve_static(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        self._send_text(file_path.read_bytes(), content_type)

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/", "/app.js", "/styles.css", "/api/state") and not self._ui_authorized():
            return
        if path == "/":
            return self._serve_static(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._serve_static(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self._serve_static(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        if path == "/api/state":
            state: ProxyState = self.server.state
            selected = state.get_selected_provider()
            payload = {
                "selected_provider": selected.get("name") if selected else "",
                "providers": state.get_providers(),
                "selected_override": state.get_provider_override(selected.get("name", "")) if selected else {},
            }
            return self._send_json(payload)
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/api/select", "/api/refresh-models", "/api/reload", "/api/reset", "/api/provider-auth") and not self._ui_authorized():
            return
        if path == "/api/select":
            body = self._read_body()
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                return self._send_json({"error": "invalid_json"}, status=400)
            name = data.get("provider", "")
            state: ProxyState = self.server.state
            if state.set_selected_provider(name):
                logging.info("ui: selected provider=%s", name)
                selected = state.get_selected_provider()
                return self._send_json({"selected_provider": selected.get("name") if selected else ""})
            return self._send_json({"error": "unknown_provider"}, status=400)

        if path == "/api/refresh-models":
            body = self._read_body()
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                return self._send_json({"error": "invalid_json"}, status=400)
            state: ProxyState = self.server.state
            token_param = state.get_token_param()
            timeout = min(state.get_timeout(), 10.0)
            target = data.get("provider")
            providers = state.get_providers()
            results = []
            for p in providers:
                if target and p.get("name") != target:
                    continue
                if p.get("name") == "Note":
                    results.append({"provider": p.get("name", ""), "updated": False, "error": "skip Note"})
                    continue
                override = state.get_provider_override(p.get("name", ""))
                models, error = fetch_models(p, token_param, timeout, override)
                if models:
                    state.update_provider_models(p.get("name", ""), models)
                    logging.info("models: refreshed provider=%s count=%s", p.get("name", ""), len(models))
                    results.append({"provider": p.get("name", ""), "updated": True, "count": len(models)})
                else:
                    logging.info("models: refresh failed provider=%s error=%s", p.get("name", ""), error)
                    results.append({"provider": p.get("name", ""), "updated": False, "error": error or "unknown"})
            selected = state.get_selected_provider()
            payload = {
                "selected_provider": selected.get("name") if selected else "",
                "providers": state.get_providers(),
                "refresh_results": results,
            }
            return self._send_json(payload)

        if path == "/api/reload":
            state: ProxyState = self.server.state
            state.reload_config()
            selected = state.get_selected_provider()
            payload = {
                "selected_provider": selected.get("name") if selected else "",
                "providers": state.get_providers(),
            }
            logging.info("config: reloaded providers=%s", len(payload["providers"]))
            return self._send_json(payload)

        if path == "/api/reset":
            state: ProxyState = self.server.state
            state.reset_config()
            payload = {
                "selected_provider": "",
                "providers": state.get_providers(),
            }
            logging.info("config: reset providers=%s", len(payload["providers"]))
            return self._send_json(payload)

        if path == "/api/provider-auth":
            body = self._read_body()
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                return self._send_json({"error": "invalid_json"}, status=400)
            name = data.get("provider", "")
            override = data.get("override", {})
            if not name or not isinstance(override, dict):
                return self._send_json({"error": "invalid_payload"}, status=400)
            state: ProxyState = self.server.state
            state.set_provider_override(name, override)
            logging.info("auth: provider=%s override=%s", name, override)
            return self._send_json({"ok": True})

        if path == "/v1/messages":
            return self._proxy_messages()

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _proxy_messages(self) -> None:
        state: ProxyState = self.server.state
        provider = state.get_selected_provider()
        if not provider:
            return self._send_json({"error": "no_provider_selected"}, status=503)
        if not self._is_authorized(state):
            return self._send_json({"error": "unauthorized"}, status=401)
        override = state.get_provider_override(provider.get("name", ""))
        token_param = override.get("token_param") or provider.get("token_param") or state.get_token_param()
        token = provider.get("token") or provider.get("api_key") or ""
        client_query = urllib.parse.urlsplit(self.path).query
        upstream_url = merge_query(provider.get("api_base_url", ""), client_query)
        token_in = str(override.get("token_in") or provider.get("token_in", "header")).lower()
        if token_in in ("query", "both"):
            upstream_url = append_token(upstream_url, token, token_param)
        if not upstream_url:
            return self._send_json({"error": "provider_url_missing"}, status=502)
        logging.info(
            "proxy: provider=%s token_param=%s token_len=%s url=%s",
            provider.get("name", ""),
            token_param,
            len(token),
            urllib.parse.urlsplit(upstream_url)._replace(query="").geturl(),
        )

        body = self._read_body()
        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in HOP_HEADERS
        }
        if token and token_in in ("header", "both"):
            header_name = override.get("token_header") or provider.get("token_header", "Authorization")
            header_format = override.get("token_header_format") or provider.get("token_header_format", "Bearer {token}")
            headers[header_name] = header_format.format(token=token)
        timeout = state.get_timeout()

        try:
            resp = requests.post(
                upstream_url,
                headers=headers,
                data=body,
                stream=True,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            return self._send_json({"error": "upstream_error", "detail": str(exc)}, status=502)

        logging.info(
            "proxy: provider=%s status=%s bytes=%s",
            provider.get("name", ""),
            resp.status_code,
            resp.headers.get("Content-Length", "?"),
        )

        self.send_response(resp.status_code)
        for key, value in resp.headers.items():
            if key.lower() in HOP_HEADERS:
                continue
            self.send_header(key, value)
        self.end_headers()
        try:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except BrokenPipeError:
            pass

    def _extract_client_token(self) -> str:
        header_map = {k.lower(): v for k, v in self.headers.items()}
        token = header_map.get("x-api-key", "")
        if token:
            return token.strip()
        auth = header_map.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        token = header_map.get("anthropic-auth-token", "")
        if token:
            return token.strip()
        query = urllib.parse.urlsplit(self.path).query
        if query:
            params = urllib.parse.parse_qs(query)
            for key in ("token", "key", "api_key"):
                if key in params and params[key]:
                    return params[key][0].strip()
        return ""

    def _ui_authorized(self) -> bool:
        state: ProxyState = self.server.state
        expected = state._config.get("APIKEY", "")
        if not expected:
            return True
        provided = self._extract_client_token()
        if provided == expected:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                _, password = decoded.split(":", 1)
                if password == expected:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="ccproxy"')
        self.end_headers()
        return False

    def _is_authorized(self, state: ProxyState) -> bool:
        expected = state._config.get("APIKEY", "")
        if not expected:
            return True
        provided = self._extract_client_token()
        return provided == expected


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Claude Code proxy")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Config file with Providers list (default: config.json)",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    state = ProxyState(config, config_path)
    if state.get_log_enabled():
        level_name = state.get_log_level()
        level = logging.INFO if level_name not in ("debug", "info", "warning", "error") else getattr(logging, level_name.upper())
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    host = config.get("HOST", "127.0.0.1")
    port = int(config.get("PORT", 3456))

    server = ThreadingHTTPServer((host, port), ProxyHandler)
    server.state = state  # type: ignore[attr-defined]

    threading.Thread(target=refresh_all_models, args=(state,), daemon=True).start()

    print(f"Proxy listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
