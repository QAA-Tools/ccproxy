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
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
DOCS_DIR = ROOT_DIR / "docs"
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
        self._error_counts: Dict[str, int] = {}
        self._error_threshold = config.get("ERROR_THRESHOLD", 3)

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

    def get_header_overrides(self) -> Dict[str, Dict[str, str]]:
        return self._config.get("HeaderOverrides", {})

    def get_request_overrides(self) -> Dict[str, Dict[str, Any]]:
        return self._config.get("RequestOverrides", {})

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

    def increment_error_count(self, provider_name: str) -> int:
        with self._lock:
            self._error_counts[provider_name] = self._error_counts.get(provider_name, 0) + 1
            return self._error_counts[provider_name]

    def reset_error_count(self, provider_name: str) -> None:
        with self._lock:
            self._error_counts[provider_name] = 0

    def get_error_threshold(self) -> int:
        return self._error_threshold


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
        transfer_encoding = self.headers.get("Transfer-Encoding", "")
        if "chunked" in transfer_encoding.lower():
            chunks: List[bytes] = []
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                size_str = line.split(b";", 1)[0].strip()
                try:
                    size = int(size_str, 16)
                except ValueError:
                    break
                if size == 0:
                    # Drain trailing headers after last chunk.
                    while True:
                        tail = self.rfile.readline()
                        if not tail or tail in (b"\r\n", b"\n"):
                            break
                    break
                data = self.rfile.read(size)
                chunks.append(data)
                # Consume the trailing CRLF after each chunk.
                self.rfile.read(2)
            return b"".join(chunks)
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
        if path == "/docs":
            return self._serve_static(DOCS_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/api/state":
            state: ProxyState = self.server.state
            selected = state.get_selected_provider()
            payload = {
                "selected_provider": selected.get("name") if selected else "",
                "providers": state.get_providers(),
                "selected_override": state.get_provider_override(selected.get("name", "")) if selected else {},
                "header_overrides": list(state.get_header_overrides().keys()),
                "request_overrides": list(state.get_request_overrides().keys()),
                "global_env_models": state._config.get("env-models", {}),
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
        provider_token = provider.get("token") or provider.get("api_key") or ""
        client_apikey = state._config.get("APIKEY", "")

        # 获取token_in配置，注意：默认为空字符串（透传模式）
        token_in = override.get("token_in") or provider.get("token_in", "")
        if token_in:
            token_in = str(token_in).lower()

        provider_name = provider.get("name", "")
        start_time = time.time()
        logging.info("-" * 60)

        # ====== 判断使用透传模式还是Override模式 ======
        if not token_in:
            # 【透传模式】：查找并替换所有值为APIKEY的项
            logging.info("proxy: mode=passthrough provider=%s", provider_name)

            # 1. 处理headers：复制客户端headers，替换包含APIKEY的项
            headers = {}
            replaced_headers = []
            for k, v in self.headers.items():
                if k.lower() not in HOP_HEADERS:
                    if client_apikey and client_apikey in v:
                        headers[k] = provider_token
                        replaced_headers.append(k)
                    else:
                        headers[k] = v

            if replaced_headers:
                logging.info("proxy: passthrough replaced_headers=%s", replaced_headers)

            # 2. 处理URL query：替换包含APIKEY的查询参数
            client_query = urllib.parse.urlsplit(self.path).query
            replaced_query_keys = []
            if client_query:
                query_params = urllib.parse.parse_qsl(client_query, keep_blank_values=True)
                replaced_params = []
                for k, v in query_params:
                    if client_apikey and client_apikey in v:
                        replaced_params.append((k, provider_token))
                        replaced_query_keys.append(k)
                    else:
                        replaced_params.append((k, v))
                client_query = urllib.parse.urlencode(replaced_params) if replaced_params else ""

            if replaced_query_keys:
                logging.info("proxy: passthrough replaced_query_keys=%s", replaced_query_keys)

            upstream_url = merge_query(provider.get("api_base_url", ""), client_query)

        else:
            # 【Override模式】：按照配置的token_in强制改变认证方式
            logging.info("proxy: mode=override token_in=%s provider=%s", token_in, provider_name)

            token_param = override.get("token_param") or provider.get("token_param") or state.get_token_param()

            # 移除客户端的所有认证header，避免冲突
            AUTH_HEADERS = {"authorization", "x-api-key", "anthropic-auth-token"}
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() not in HOP_HEADERS and k.lower() not in AUTH_HEADERS
            }

            # 处理query参数（移除常见的token参数）
            client_query = urllib.parse.urlsplit(self.path).query
            if client_query:
                query_params = urllib.parse.parse_qsl(client_query, keep_blank_values=True)
                filtered_params = [(k, v) for k, v in query_params
                                 if k.lower() not in ("token", "key", "api_key", "apikey")]
                client_query = urllib.parse.urlencode(filtered_params) if filtered_params else ""

            upstream_url = merge_query(provider.get("api_base_url", ""), client_query)

            # 注入额外的查询参数
            if override and override.get("query_params"):
                upstream_url = merge_query(upstream_url, override.get("query_params", ""))
                logging.info("proxy: injected query_params=%s", override.get("query_params"))

            # 根据token_in配置添加认证
            if token_in in ("query", "both"):
                upstream_url = append_token(upstream_url, provider_token, token_param)

            if token_in in ("header", "both"):
                header_name = override.get("token_header") or provider.get("token_header", "Authorization")
                header_format = override.get("token_header_format") or provider.get("token_header_format", "Bearer {token}")
                headers[header_name] = header_format.format(token=provider_token)
                logging.info("proxy: override adding_auth_header=%s format=%s", header_name, header_format.replace("{token}", "***"))

        # ====== 应用Header Override ======
        header_override = override.get("header_override") or provider.get("header_override", "")
        if header_override:
            overrides = state.get_header_overrides()
            override_headers = overrides.get(header_override, {})
            if override_headers:
                # 大小写不敏感替换：先删除与override key匹配的现有headers
                override_keys_lower = {k.lower(): k for k in override_headers.keys()}
                headers = {k: v for k, v in headers.items() if k.lower() not in override_keys_lower}
                # 删除浏览器/客户端特有的headers
                browser_headers = {'http-referer', 'referer', 'x-title', 'origin', 'priority'}
                headers = {k: v for k, v in headers.items()
                          if not (k.lower() in browser_headers or
                                 k.lower().startswith('sec-ch-') or
                                 k.lower().startswith('sec-fetch-'))}
                # 然后添加override headers
                headers.update(override_headers)
                logging.info("proxy: applied header_override=%s", header_override)
            else:
                logging.warning("proxy: header_override=%s not found", header_override)

        if not upstream_url:
            return self._send_json({"error": "provider_url_missing"}, status=502)

        # ====== 日志记录 ======
        parsed_url = urllib.parse.urlsplit(upstream_url)
        query_dict = dict(urllib.parse.parse_qsl(parsed_url.query))
        logging.info(
            "proxy: provider=%s token_len=%s url=%s",
            provider_name,
            len(provider_token),
            parsed_url._replace(query="").geturl(),
        )

        if query_dict:
            logging.info("proxy: url_query_params (total %d):", len(query_dict))
            for k, v in query_dict.items():
                safe_v = "***" if k.lower() in ("token", "key", "api_key", "apikey") else v
                logging.info("  %s: %s", k, safe_v)

        body = self._read_body()

        # ====== 注入请求体字段 ======
        inject_fields = None
        if override:
            # 优先使用 request_override
            override_name = override.get("request_override")
            if override_name:
                overrides = state.get_request_overrides()
                inject_fields = overrides.get(override_name)
                if inject_fields:
                    logging.info("proxy: using request_override=%s", override_name)
            # 向后兼容：直接使用 request_inject
            if not inject_fields and override.get("request_inject"):
                inject_fields = override.get("request_inject")

        if inject_fields:
            try:
                request_data = json.loads(body)
                # 按 Claude CLI 顺序重建: model, messages, system, tools, metadata, max_tokens, stream
                ordered = {}
                if "model" in request_data:
                    ordered["model"] = request_data["model"]
                if "messages" in request_data:
                    ordered["messages"] = request_data["messages"]
                for field in ["system", "tools", "metadata"]:
                    if field in inject_fields and field not in request_data:
                        ordered[field] = inject_fields[field]
                        logging.info("proxy: injected field=%s", field)
                    elif field in request_data:
                        ordered[field] = request_data[field]
                for k, v in request_data.items():
                    if k not in ordered:
                        ordered[k] = v
                body = json.dumps(ordered, separators=(',', ':')).encode("utf-8")
            except Exception as e:
                logging.warning("proxy: request_inject failed error=%s", e)

        try:
            req_data = json.loads(body)
            logging.info("proxy: request_body:")
            for key, value in req_data.items():
                value_str = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                logging.info("  %s: %s", key, value_str)
        except Exception:
            req_text = body.decode("utf-8", errors="replace")
            req_preview = req_text[:200] + "..." if len(req_text) > 200 else req_text
            logging.info("proxy: request_body=%s", req_preview)

        # 记录最终发送到上游的所有header（原始内容，格式化输出）
        logging.info("proxy: upstream_headers (total %d):", len(headers))
        for k, v in sorted(headers.items()):
            logging.info("  %s: %s", k, v)

        timeout = (10.0, state.get_timeout())

        try:
            resp = requests.post(
                upstream_url,
                headers=headers,
                data=body,
                stream=True,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            elapsed = time.time() - start_time
            logging.info("proxy: provider=%s error=%s elapsed=%.1fs", provider_name, exc, elapsed)
            return self._send_json({"error": "upstream_error", "detail": str(exc)}, status=502)

        logging.info(
            "proxy: provider=%s status=%s bytes=%s",
            provider_name,
            resp.status_code,
            resp.headers.get("Content-Length", "?"),
        )

        # 检查是否为非200错误
        if resp.status_code != 200:
            error_count = state.increment_error_count(provider_name)
            threshold = state.get_error_threshold()

            # 详细记录错误信息
            logging.error("=" * 60)
            logging.error("proxy: ERROR DETECTED")
            logging.error("  provider: %s", provider_name)
            logging.error("  status_code: %d", resp.status_code)
            logging.error("  error_count: %d/%d", error_count, threshold)
            logging.error("  url: %s", upstream_url)
            logging.error("  elapsed: %.1fs", time.time() - start_time)

            # 尝试读取错误响应体
            try:
                error_body = resp.content[:1000].decode("utf-8", errors="replace")
                logging.error("  response_preview: %s", error_body)
            except Exception:
                logging.error("  response_preview: (unable to read)")

            logging.error("=" * 60)

            if error_count < threshold:
                # 未达到阈值，断开连接（不返回响应）
                logging.warning("proxy: provider=%s dropping connection to trigger client retry", provider_name)
                return  # 直接返回，不发送响应
        else:
            # 成功，重置错误计数
            state.reset_error_count(provider_name)

        self.send_response(resp.status_code)
        for key, value in resp.headers.items():
            if key.lower() in HOP_HEADERS:
                continue
            self.send_header(key, value)
        self.end_headers()

        total_bytes = 0
        all_chunks = []
        try:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    total_bytes += len(chunk)
                    all_chunks.append(chunk)
        except BrokenPipeError:
            logging.warning("proxy: client disconnected (BrokenPipeError)")
        except Exception as e:
            logging.error("proxy: stream error=%s", e)

        elapsed = time.time() - start_time

        # 显示响应内容
        try:
            text = b"".join(all_chunks).decode("utf-8", errors="replace")
            try:
                resp_data = json.loads(text)
                logging.info("proxy: response_body:")
                for key, value in resp_data.items():
                    value_str = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                    logging.info("  %s: %s", key, value_str)
            except json.JSONDecodeError:
                # 尝试解析 SSE 格式
                if text.startswith("event:") or "data:" in text:
                    logging.info("proxy: response_body (SSE stream):")
                    accumulated_text = []
                    for event in text.split('\n\n'):
                        if not event.strip():
                            continue
                        lines = event.strip().split('\n')
                        event_type = ""
                        for line in lines:
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                try:
                                    data = json.loads(line[5:].strip())
                                    if event_type == "content_block_delta" and data.get("delta", {}).get("type") == "text_delta":
                                        accumulated_text.append(data["delta"]["text"])
                                    else:
                                        if accumulated_text:
                                            logging.info("  [content_block_delta] accumulated_text:\n%s", "".join(accumulated_text))
                                            accumulated_text = []
                                        data_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                                        logging.info("  [%s] %s", event_type or "data", data_str)
                                except:
                                    logging.info("  [%s] %s", event_type or "data", line[5:].strip())
                    if accumulated_text:
                        logging.info("  [content_block_delta] accumulated_text:\n%s", "".join(accumulated_text))
                else:
                    preview_len = 500
                    if len(text) <= preview_len * 2:
                        preview = text
                    else:
                        preview = text[:preview_len] + " ... " + text[-preview_len:]
                    preview = preview.replace("\n", "\\n").replace("\r", "")
                    logging.info("proxy: response_preview=%s", preview)
        except Exception:
            pass

        logging.info("proxy: provider=%s completed bytes=%s elapsed=%.1fs", provider_name, total_bytes, elapsed)

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
