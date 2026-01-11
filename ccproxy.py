#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal Claude Code proxy v2 - Modular design
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
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "content-length", "accept-encoding",
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


class ProxyState:
    """统一管理配置和运行时数据"""

    def __init__(self, config: Dict[str, Any], config_path: Path) -> None:
        self._lock = threading.Lock()
        self._config = config
        self._initial_config = json.loads(json.dumps(config))
        self._config_path = config_path
        self._state = self._load_state()
        self._runtime_providers = self._init_providers()
        self._error_counts: Dict[str, int] = {}
        self._error_threshold = config.get("ERROR_THRESHOLD", 3)

    def _init_providers(self) -> List[Dict[str, Any]]:
        """从 config 初始化运行时 providers（深拷贝）"""
        return [dict(p) for p in self._config.get("Providers", [])]

    def _load_state(self) -> Dict[str, Any]:
        """加载用户状态（selected_provider, provider_overrides）"""
        if STATE_PATH.exists():
            with STATE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_state(self) -> None:
        """保存用户状态到 state.json"""
        try:
            with STATE_PATH.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=True)
        except OSError as exc:
            logging.warning("state: failed to persist proxy_state.json (%s)", exc)

    def get_providers(self) -> List[Dict[str, Any]]:
        """获取运行时 providers（包含 models, test_result）"""
        with self._lock:
            return list(self._runtime_providers)

    def get_selected_provider(self) -> Optional[Dict[str, Any]]:
        """获取当前选中的 provider"""
        with self._lock:
            if self._state.get("selection_required"):
                return None
            selected = self._state.get("selected_provider")
            if selected:
                for p in self._runtime_providers:
                    if p.get("name") == selected:
                        return p
            return self._runtime_providers[0] if self._runtime_providers else None

    def set_selected_provider(self, name: str) -> bool:
        """设置选中的 provider"""
        with self._lock:
            if any(p.get("name") == name for p in self._runtime_providers):
                self._state["selected_provider"] = name
                if self._state.get("selection_required"):
                    self._state["selection_required"] = False
                self.save_state()
                return True
        return False

    def update_provider_models(self, name: str, models: List[str]) -> None:
        """更新 provider 的 models"""
        with self._lock:
            for p in self._runtime_providers:
                if p.get("name") == name:
                    p["models"] = models
                    break

    def set_test_result(self, name: str, success: bool) -> None:
        """设置 provider 的测试结果"""
        with self._lock:
            for p in self._runtime_providers:
                if p.get("name") == name:
                    p["test_result"] = success
                    break

    def reload_config(self) -> None:
        """重新加载 config，重置运行时数据"""
        with self._lock:
            try:
                with self._config_path.open("r", encoding="utf-8-sig") as f:
                    config = json.load(f)
            except OSError as exc:
                logging.warning("config: failed to reload (%s)", exc)
                return
            self._config = config
            self._runtime_providers = self._init_providers()
            selected = self._state.get("selected_provider")
            if selected and any(p.get("name") == selected for p in self._runtime_providers):
                return
            if self._runtime_providers:
                self._state["selected_provider"] = self._runtime_providers[0].get("name", "")
                self.save_state()

    def reset_config(self) -> None:
        """重置到初始配置"""
        with self._lock:
            self._config = json.loads(json.dumps(self._initial_config))
            self._runtime_providers = self._init_providers()
            self._state["selected_provider"] = ""
            self._state["selection_required"] = True
            self._state["global_override"] = {}  # 清空统一的 override
            self.save_state()

    def get_provider_override(self, name: str) -> Dict[str, Any]:
        """获取统一的覆写配置（所有 provider 共享）"""
        with self._lock:
            return dict(self._state.get("global_override", {}))

    def set_provider_override(self, name: str, override: Dict[str, Any]) -> None:
        """设置统一的覆写配置（所有 provider 共享）"""
        with self._lock:
            self._state["global_override"] = override
            self.save_state()

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def get_header_overrides(self) -> Dict[str, Dict[str, str]]:
        """获取 header 覆写配置"""
        return self._config.get("HeaderOverrides", {})

    def get_request_overrides(self) -> Dict[str, Dict[str, Any]]:
        """获取 request 覆写配置"""
        return self._config.get("RequestOverrides", {})

    def increment_error_count(self, provider_name: str) -> int:
        """增加错误计数"""
        with self._lock:
            self._error_counts[provider_name] = self._error_counts.get(provider_name, 0) + 1
            return self._error_counts[provider_name]

    def reset_error_count(self, provider_name: str) -> None:
        """重置错误计数"""
        with self._lock:
            self._error_counts[provider_name] = 0

    def get_error_threshold(self) -> int:
        """获取错误阈值"""
        return self._error_threshold


class ProxyRequest:
    """构建代理请求"""

    def __init__(self, provider: Dict[str, Any], override: Dict[str, Any],
                 client_headers: Dict[str, str], client_query: str, client_body: bytes,
                 state: ProxyState):
        self.provider = provider
        self.override = override
        self.client_headers = client_headers
        self.client_query = client_query
        self.client_body = client_body
        self.state = state
        self.provider_token = provider.get("token") or provider.get("api_key") or ""
        self.client_apikey = state.get_config("APIKEY", "")
        self.token_in = override.get("token_in") or provider.get("token_in", "")
        if self.token_in:
            self.token_in = str(self.token_in).lower()

    def build_url(self) -> str:
        """构建上游 URL"""
        api_base_url = self.provider.get("api_base_url", "")

        if not self.token_in:
            # 透传模式：处理 query 参数
            query_params = urllib.parse.parse_qsl(self.client_query, keep_blank_values=True)
            replaced_params = []
            for k, v in query_params:
                if self.client_apikey and self.client_apikey in v:
                    replaced_params.append((k, self.provider_token))
                else:
                    replaced_params.append((k, v))
            client_query = urllib.parse.urlencode(replaced_params) if replaced_params else ""
            url = merge_query(api_base_url, client_query)
        else:
            # Override 模式：移除客户端的 token 参数
            query_params = urllib.parse.parse_qsl(self.client_query, keep_blank_values=True)
            filtered_params = [(k, v) for k, v in query_params
                             if k.lower() not in ("token", "key", "api_key", "apikey")]
            client_query = urllib.parse.urlencode(filtered_params) if filtered_params else ""
            url = merge_query(api_base_url, client_query)

            # 注入额外的查询参数
            if self.override and self.override.get("query_params"):
                url = merge_query(url, self.override.get("query_params", ""))

            # 根据 token_in 配置添加认证
            if self.token_in in ("query", "both"):
                token_param = self.override.get("token_param") or self.provider.get("token_param") or self.state.get_config("TOKEN_PARAM", "token")
                url = append_token(url, self.provider_token, token_param)

        return url

    def build_headers(self) -> Dict[str, str]:
        """构建上游 headers"""
        if not self.token_in:
            # 透传模式：复制客户端 headers，替换包含 APIKEY 的项
            headers = {}
            for k, v in self.client_headers.items():
                if k.lower() not in HOP_HEADERS:
                    if self.client_apikey and self.client_apikey in v:
                        headers[k] = self.provider_token
                    else:
                        headers[k] = v
        else:
            # Override 模式：移除客户端的认证 headers
            AUTH_HEADERS = {"authorization", "x-api-key", "anthropic-auth-token"}
            headers = {
                k: v
                for k, v in self.client_headers.items()
                if k.lower() not in HOP_HEADERS and k.lower() not in AUTH_HEADERS
            }

            # 根据 token_in 配置添加认证
            if self.token_in in ("header", "both"):
                header_name = self.override.get("token_header") or self.provider.get("token_header", "Authorization")
                header_format = self.override.get("token_header_format") or self.provider.get("token_header_format", "Bearer {token}")
                headers[header_name] = header_format.format(token=self.provider_token)

        # 应用 Header Override
        header_override = self.override.get("header_override") or self.provider.get("header_override", "")
        if header_override:
            overrides = self.state.get_header_overrides()
            override_headers = overrides.get(header_override, {})
            if override_headers:
                override_keys_lower = {k.lower(): k for k in override_headers.keys()}
                headers = {k: v for k, v in headers.items() if k.lower() not in override_keys_lower}
                browser_headers = {'http-referer', 'referer', 'x-title', 'origin', 'priority'}
                headers = {k: v for k, v in headers.items()
                          if not (k.lower() in browser_headers or
                                 k.lower().startswith('sec-ch-') or
                                 k.lower().startswith('sec-fetch-'))}
                headers.update(override_headers)

        return headers

    def build_body(self) -> bytes:
        """构建上游请求体"""
        inject_fields = None
        if self.override:
            override_name = self.override.get("request_override")
            if override_name:
                overrides = self.state.get_request_overrides()
                inject_fields = overrides.get(override_name)
            if not inject_fields and self.override.get("request_inject"):
                inject_fields = self.override.get("request_inject")

        if inject_fields:
            try:
                request_data = json.loads(self.client_body)
                ordered = {}
                if "model" in request_data:
                    ordered["model"] = request_data["model"]
                if "messages" in request_data:
                    ordered["messages"] = request_data["messages"]
                for field in ["system", "tools", "metadata"]:
                    if field in inject_fields and field not in request_data:
                        ordered[field] = inject_fields[field]
                    elif field in request_data:
                        ordered[field] = request_data[field]
                for k, v in request_data.items():
                    if k not in ordered:
                        ordered[k] = v
                return json.dumps(ordered, separators=(',', ':')).encode("utf-8")
            except Exception:
                pass

        return self.client_body


def fetch_models(provider: Dict[str, Any], token_param: str, timeout: float,
                 override: Optional[Dict[str, Any]] = None) -> tuple[Optional[List[str]], Optional[str]]:
    """
    获取 provider 的模型列表
    输入: provider 配置, token 参数名, 超时时间, 覆写配置
    输出: (模型列表, 错误信息)
    """
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
    """
    刷新所有 provider 的模型列表
    输入: ProxyState 对象
    输出: 无（直接更新 state）
    """
    token_param = state.get_config("TOKEN_PARAM", "token")
    timeout_ms = state.get_config("API_TIMEOUT_MS", "600000")
    try:
        timeout = min(float(timeout_ms) / 1000.0, 10.0)
    except (TypeError, ValueError):
        timeout = 10.0
    for provider in state.get_providers():
        if provider.get("name") == "Note":
            continue
        override = state.get_provider_override(provider.get("name", ""))
        models, error = fetch_models(provider, token_param, timeout, override)
        if models:
            state.update_provider_models(provider.get("name", ""), models)
        elif error:
            logging.info("models: refresh failed provider=%s error=%s", provider.get("name", ""), error)


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    server_version = "ClaudeProxy/0.2"

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """
        发送 JSON 响应
        输入: 数据字典, HTTP 状态码
        输出: 无（直接写入响应）
        """
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, body: bytes, content_type: str) -> None:
        """
        发送文本响应
        输入: 响应体, Content-Type
        输出: 无（直接写入响应）
        """
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """
        读取请求体（支持 chunked 编码）
        输入: 无（从 self.rfile 读取）
        输出: 请求体字节
        """
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
                    while True:
                        tail = self.rfile.readline()
                        if not tail or tail in (b"\r\n", b"\n"):
                            break
                    break
                data = self.rfile.read(size)
                chunks.append(data)
                self.rfile.read(2)
            return b"".join(chunks)
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length > 0 else b""

    def _serve_static(self, file_path: Path, content_type: str) -> None:
        """
        提供静态文件服务
        输入: 文件路径, Content-Type
        输出: 无（直接写入响应）
        """
        if not file_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        self._send_text(file_path.read_bytes(), content_type)

    def _extract_client_token(self) -> str:
        """
        从请求中提取客户端 token
        输入: 无（从 self.headers 和 self.path 读取）
        输出: token 字符串
        """
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
        """
        检查 UI 访问权限
        输入: 无（从 self.headers 读取）
        输出: 是否授权
        """
        state: ProxyState = self.server.state
        expected = state.get_config("APIKEY", "")
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
        """
        检查 API 访问权限
        输入: ProxyState 对象
        输出: 是否授权
        """
        expected = state.get_config("APIKEY", "")
        if not expected:
            return True
        provided = self._extract_client_token()
        return provided == expected

    def do_GET(self) -> None:
        """
        处理 GET 请求
        输入: 无（从 self.path 读取）
        输出: 无（直接写入响应）
        """
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
                "selected_override": state.get_provider_override(""),  # 统一的 override
                "header_overrides": list(state.get_header_overrides().keys()),
                "request_overrides": list(state.get_request_overrides().keys()),
                "global_env_models": state.get_config("env-models", {}),
            }
            return self._send_json(payload)
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        """
        处理 POST 请求
        输入: 无（从 self.path 读取）
        输出: 无（直接写入响应）
        """
        path = urllib.parse.urlsplit(self.path).path
        if path in ("/api/select", "/api/refresh-models", "/api/reload", "/api/reset", "/api/provider-auth", "/api/test-provider", "/api/refresh-and-test") and not self._ui_authorized():
            return
        if path == "/api/select":
            return self._handle_select()
        if path == "/api/refresh-models":
            return self._handle_refresh_models()
        if path == "/api/reload":
            return self._handle_reload()
        if path == "/api/reset":
            return self._handle_reset()
        if path == "/api/provider-auth":
            return self._handle_provider_auth()
        if path == "/api/test-provider":
            return self._handle_test_provider()
        if path == "/api/refresh-and-test":
            return self._handle_refresh_and_test()
        if path == "/v1/messages":
            return self._proxy_messages()
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_select(self) -> None:
        """
        处理选择 provider 请求
        输入: 无（从请求体读取）
        输出: 无（直接写入响应）
        """
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

    def _handle_refresh_models(self) -> None:
        """
        处理刷新模型列表请求
        输入: 无（从请求体读取）
        输出: 无（直接写入响应）
        """
        body = self._read_body()
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid_json"}, status=400)
        state: ProxyState = self.server.state
        token_param = state.get_config("TOKEN_PARAM", "token")
        timeout_ms = state.get_config("API_TIMEOUT_MS", "600000")
        try:
            timeout = min(float(timeout_ms) / 1000.0, 10.0)
        except (TypeError, ValueError):
            timeout = 10.0
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

    def _handle_reload(self) -> None:
        """
        处理重新加载配置请求
        输入: 无
        输出: 无（直接写入响应）
        """
        state: ProxyState = self.server.state
        state.reload_config()
        selected = state.get_selected_provider()
        payload = {
            "selected_provider": selected.get("name") if selected else "",
            "providers": state.get_providers(),
        }
        logging.info("config: reloaded providers=%s", len(payload["providers"]))
        return self._send_json(payload)

    def _handle_reset(self) -> None:
        """
        处理重置配置请求
        输入: 无
        输出: 无（直接写入响应）
        """
        state: ProxyState = self.server.state
        state.reset_config()
        payload = {
            "selected_provider": "",
            "providers": state.get_providers(),
        }
        logging.info("config: reset providers=%s", len(payload["providers"]))
        return self._send_json(payload)

    def _handle_provider_auth(self) -> None:
        """
        处理设置 provider 覆写配置请求
        输入: 无（从请求体读取）
        输出: 无（直接写入响应）
        """
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

    def _handle_test_provider(self) -> None:
        """
        处理测试 provider 请求
        输入: 无（从请求体读取）
        输出: 无（直接写入响应）
        """
        body = self._read_body()
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid_json"}, status=400)
        name = data.get("provider", "")
        model = data.get("model", "claude-sonnet-4-5-20250929")
        prompt = data.get("prompt", "hi")
        state: ProxyState = self.server.state
        providers = state.get_providers()
        provider = next((p for p in providers if p.get("name") == name), None)
        if not provider:
            return self._send_json({"error": "provider_not_found"}, status=400)
        test_result = self._test_provider(model, prompt, state)
        state.set_test_result(name, test_result.get("success", False))
        return self._send_json(test_result)

    def _handle_refresh_and_test(self) -> None:
        """
        处理刷新并测试所有 provider 请求（异步处理）
        输入: 无（从请求体读取）
        输出: 无（立即返回，后台处理）
        """
        body = self._read_body()
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid_json"}, status=400)

        prompt = data.get("prompt", "hi")
        state: ProxyState = self.server.state

        # 立即返回，在后台线程中处理
        def background_task():
            token_param = state.get_config("TOKEN_PARAM", "token")
            timeout_ms = state.get_config("API_TIMEOUT_MS", "600000")
            try:
                timeout = min(float(timeout_ms) / 1000.0, 10.0)
            except (TypeError, ValueError):
                timeout = 10.0

            providers = state.get_providers()
            original_selected = state.get_selected_provider()

            logging.info("refresh_and_test: starting background task for %d providers", len(providers))

            for p in providers:
                provider_name = p.get("name", "")
                if provider_name == "Note":
                    continue

                # 1. 刷新模型列表
                override = state.get_provider_override(provider_name)
                models, error = fetch_models(p, token_param, timeout, override)
                if models:
                    state.update_provider_models(provider_name, models)
                    logging.info("refresh_and_test: provider=%s models_count=%s", provider_name, len(models))
                else:
                    logging.warning("refresh_and_test: provider=%s refresh_failed error=%s", provider_name, error)
                    state.set_test_result(provider_name, False)
                    continue

                # 2. 使用第一个模型进行测试
                if models:
                    test_model = models[0]
                    # 临时切换到这个 provider
                    state.set_selected_provider(provider_name)
                    test_result = self._test_provider(test_model, prompt, state)
                    state.set_test_result(provider_name, test_result.get("success", False))
                else:
                    state.set_test_result(provider_name, False)

            # 恢复原来选中的 provider
            if original_selected:
                state.set_selected_provider(original_selected.get("name", ""))

            logging.info("refresh_and_test: background task completed")

        # 启动后台线程
        threading.Thread(target=background_task, daemon=True).start()

        # 立即返回
        return self._send_json({"status": "started", "message": "Refresh and test started in background"})

    def _forward_to_upstream(self, provider: Dict[str, Any], provider_override: Dict[str, Any],
                            client_headers: Dict[str, str], client_query: str, client_body: bytes,
                            state: ProxyState) -> requests.Response:
        """
        转发请求到上游 provider（核心逻辑）
        输入: provider 配置, provider 覆写配置, 客户端 headers/query/body, ProxyState 对象
        输出: requests.Response 对象
        """
        provider_name = provider.get("name", "")
        start_time = time.time()

        # 构建请求
        proxy_request = ProxyRequest(provider, provider_override, client_headers, client_query, client_body, state)
        upstream_url = proxy_request.build_url()
        headers = proxy_request.build_headers()
        body = proxy_request.build_body()

        if not upstream_url:
            raise ValueError("provider_url_missing")

        # 日志记录
        parsed_url = urllib.parse.urlsplit(upstream_url)
        query_dict = dict(urllib.parse.parse_qsl(parsed_url.query))
        logging.info("forward: provider=%s url=%s", provider_name, parsed_url._replace(query="").geturl())
        if query_dict:
            logging.info("forward: url_query_params (total %d):", len(query_dict))
            for k, v in query_dict.items():
                safe_v = "***" if k.lower() in ("token", "key", "api_key", "apikey") else v
                logging.info("  %s: %s", k, safe_v)

        try:
            req_data = json.loads(body)
            logging.info("forward: request_body:")
            for key, value in req_data.items():
                value_str = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                logging.info("  %s: %s", key, value_str)
        except Exception:
            req_text = body.decode("utf-8", errors="replace")
            req_preview = req_text[:200] + "..." if len(req_text) > 200 else req_text
            logging.info("forward: request_body=%s", req_preview)

        logging.info("forward: upstream_headers (total %d):", len(headers))
        for k, v in sorted(headers.items()):
            logging.info("  %s: %s", k, v)

        timeout_ms = state.get_config("API_TIMEOUT_MS", "600000")
        try:
            timeout = (10.0, float(timeout_ms) / 1000.0)
        except (TypeError, ValueError):
            timeout = (10.0, 600.0)

        try:
            resp = requests.post(upstream_url, headers=headers, data=body, stream=True, timeout=timeout)
            elapsed = time.time() - start_time
            logging.info("forward: provider=%s status=%s elapsed=%.1fs", provider_name, resp.status_code, elapsed)
            return resp
        except requests.RequestException as exc:
            elapsed = time.time() - start_time
            logging.error("forward: provider=%s error=%s elapsed=%.1fs", provider_name, exc, elapsed)
            raise

    def _stream_response(self, resp: requests.Response, provider_name: str, start_time: float, state: ProxyState) -> None:
        """
        流式返回响应到客户端（包含错误处理和日志记录）
        输入: Response 对象, provider 名称, 开始时间, ProxyState 对象
        输出: 无（直接写入响应）
        """
        # 检查错误
        if resp.status_code != 200:
            error_count = state.increment_error_count(provider_name)
            threshold = state.get_error_threshold()
            logging.error("=" * 60)
            logging.error("proxy: ERROR DETECTED")
            logging.error("  provider: %s", provider_name)
            logging.error("  status_code: %d", resp.status_code)
            logging.error("  error_count: %d/%d", error_count, threshold)
            logging.error("  elapsed: %.1fs", time.time() - start_time)
            try:
                error_body = resp.content[:1000].decode("utf-8", errors="replace")
                logging.error("  response_preview: %s", error_body)
            except Exception:
                logging.error("  response_preview: (unable to read)")
            logging.error("=" * 60)
            if error_count < threshold:
                logging.warning("proxy: provider=%s dropping connection to trigger client retry", provider_name)
                return
        else:
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

    def _test_provider(self, model: str, prompt: str, state: ProxyState) -> Dict[str, Any]:
        """
        测试当前选中的 provider
        输入: 测试模型, 测试提示词, ProxyState 对象
        输出: 测试结果字典
        """
        provider = state.get_selected_provider()
        if not provider:
            return {"success": False, "error": "no_provider_selected"}

        provider_override = state.get_provider_override(provider.get("name", ""))
        provider_name = provider.get("name", "")

        logging.info("test: provider=%s model=%s prompt=%s", provider_name, model, prompt[:50])

        # 1. 构造测试请求
        client_headers = {"Content-Type": "application/json"}
        client_query = ""
        client_body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100
        }).encode("utf-8")

        try:
            # 2. 转发处理（复用核心逻辑）
            resp = self._forward_to_upstream(provider, provider_override, client_headers, client_query, client_body, state)

            # 3. 记录响应内容
            try:
                response_text = resp.text
                try:
                    resp_data = json.loads(response_text)
                    logging.info("test: response_body:")
                    for key, value in resp_data.items():
                        value_str = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
                        logging.info("  %s: %s", key, value_str)
                except json.JSONDecodeError:
                    preview_len = 200
                    preview = response_text[:preview_len] + "..." if len(response_text) > preview_len else response_text
                    logging.info("test: response_preview=%s", preview)
            except Exception:
                pass

            # 4. 返回结果
            if resp.status_code == 200:
                logging.info("test: provider=%s success", provider_name)
                return {"success": True, "status": resp.status_code}
            logging.warning("test: provider=%s failed status=%d", provider_name, resp.status_code)
            return {"success": False, "status": resp.status_code, "error": resp.text[:200]}
        except Exception as exc:
            logging.error("test: provider=%s error=%s", provider_name, str(exc)[:200])
            return {"success": False, "error": str(exc)[:200]}

    def _proxy_messages(self) -> None:
        """
        代理 /v1/messages 请求到上游 provider
        输入: 无（从请求读取）
        输出: 无（直接写入响应）
        """
        state: ProxyState = self.server.state
        provider = state.get_selected_provider()
        if not provider:
            return self._send_json({"error": "no_provider_selected"}, status=503)
        if not self._is_authorized(state):
            return self._send_json({"error": "unauthorized"}, status=401)
        provider_override = state.get_provider_override(provider.get("name", ""))
        provider_name = provider.get("name", "")
        start_time = time.time()
        logging.info("-" * 60)
        logging.info("proxy: mode=%s provider=%s", "passthrough" if not provider_override.get("token_in") else "override", provider_name)

        # 1. 接收客户端请求
        client_headers = {k: v for k, v in self.headers.items()}
        client_query = urllib.parse.urlsplit(self.path).query
        client_body = self._read_body()

        try:
            # 2. 转发处理（复用核心逻辑）
            resp = self._forward_to_upstream(provider, provider_override, client_headers, client_query, client_body, state)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, status=502)
        except requests.RequestException as exc:
            return self._send_json({"error": "upstream_error", "detail": str(exc)}, status=502)

        # 3. 流式返回响应（复用响应处理逻辑）
        self._stream_response(resp, provider_name, start_time, state)


def build_arg_parser() -> argparse.ArgumentParser:
    """
    构建命令行参数解析器
    输入: 无
    输出: ArgumentParser 对象
    """
    parser = argparse.ArgumentParser(description="Minimal Claude Code proxy v2")
    parser.add_argument("--config", type=str, default="config.json", help="Config file with Providers list (default: config.json)")
    return parser


def main() -> None:
    """
    主函数
    输入: 无
    输出: 无（启动服务器）
    """
    args = build_arg_parser().parse_args()
    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)
    state = ProxyState(config, config_path)

    log_enabled = config.get("LOG", True)
    if log_enabled:
        level_name = str(config.get("LOG_LEVEL", "info")).lower()
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
