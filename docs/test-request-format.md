# Claude Code 请求格式说明

本文档说明 Claude Code 客户端发送给 API 的完整 HTTP 请求格式。

---

## HTTP Headers

```http
Accept: application/json
Authorization: sk-your-api-key-here
Content-Type: application/json
User-Agent: claude-cli/2.1.5 (external, cli)
X-Forwarded-For: 211.222.233.244
X-Forwarded-Proto: https
X-Real-IP: 211.222.233.244
X-Stainless-Arch: x64
X-Stainless-Lang: js
X-Stainless-OS: Windows
X-Stainless-Package-Version: 0.70.0
X-Stainless-Retry-Count: 0
X-Stainless-Runtime: node
X-Stainless-Runtime-Version: v24.11.0
X-Stainless-Timeout: 600
accept-language: *
anthropic-beta: claude-code-20250219,interleaved-thinking-2025-05-14
anthropic-dangerous-direct-browser-access: true
anthropic-version: 2023-06-01
sec-fetch-mode: cors
x-app: cli
x-stainless-helper-method: stream
```

### 关键字段说明

| 字段 | 说明 |
|------|------|
| `Authorization` | API 密钥 |
| `User-Agent` | 标识为 Claude CLI 客户端 |
| `X-Real-IP` / `X-Forwarded-For` | 客户端 IP 地址 |
| `X-Stainless-*` | Anthropic SDK 特征头 |
| `anthropic-beta` | 启用 Claude Code 和 thinking 功能 |
| `anthropic-version` | API 版本 |
| `x-app` | 标识为 CLI 应用 |

---

## Request Body

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "hi"
        }
      ]
    }
  ],
  "system": [
    {
      "type": "text",
      "text": "You are Claude Code, Anthropic's official CLI for Claude.",
      "cache_control": {
        "type": "ephemeral"
      }
    }
  ],
  "tools": [],
  "metadata": {
    "user_id": "user_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456_account__session_12345678-90ab-cdef-1234-567890abcdef"
  },
  "max_tokens": 32000,
  "thinking": {
    "budget_tokens": 31999,
    "type": "enabled"
  },
  "stream": true
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `model` | 使用的模型 |
| `messages` | 用户消息列表 |
| `system` | 系统提示词（带缓存控制） |
| `tools` | 工具列表（可能为空数组或包含工具定义） |
| `metadata` | 用户元数据（包含 user_id） |
| `max_tokens` | 最大生成 token 数 |
| `thinking` | thinking 模式配置 |
| `stream` | 是否启用流式响应 |

---

## 完整 HTTP 请求示例

```http
POST https://api.anthropic.com/v1/messages HTTP/1.1
Accept: application/json
Authorization: sk-your-api-key-here
Content-Type: application/json
User-Agent: claude-cli/2.1.5 (external, cli)
X-Forwarded-For: 211.222.233.244
X-Forwarded-Proto: https
X-Real-IP: 211.222.233.244
X-Stainless-Arch: x64
X-Stainless-Lang: js
X-Stainless-OS: Windows
X-Stainless-Package-Version: 0.70.0
X-Stainless-Retry-Count: 0
X-Stainless-Runtime: node
X-Stainless-Runtime-Version: v24.11.0
X-Stainless-Timeout: 600
accept-language: *
anthropic-beta: claude-code-20250219,interleaved-thinking-2025-05-14
anthropic-dangerous-direct-browser-access: true
anthropic-version: 2023-06-01
sec-fetch-mode: cors
x-app: cli
x-stainless-helper-method: stream

{
  "model": "claude-sonnet-4-5-20250929",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "hi"
        }
      ]
    }
  ],
  "system": [
    {
      "type": "text",
      "text": "You are Claude Code, Anthropic's official CLI for Claude.",
      "cache_control": {
        "type": "ephemeral"
      }
    }
  ],
  "tools": [],
  "metadata": {
    "user_id": "user_a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456_account__session_12345678-90ab-cdef-1234-567890abcdef"
  },
  "max_tokens": 32000,
  "thinking": {
    "budget_tokens": 31999,
    "type": "enabled"
  },
  "stream": true
}
```

---

## 注意事项

1. **tools 字段**：在实际使用中，`tools` 字段可能包含完整的工具定义列表（如 Bash、Read、Write 等），测试时通常为空数组
2. **IP 地址**：`X-Real-IP` 和 `X-Forwarded-For` 的值可以自定义，用于固定客户端 IP
3. **thinking 模式**：`thinking` 字段启用了 Claude 的思考模式，`budget_tokens` 控制思考的 token 预算
4. **cache_control**：system 提示词使用了 `ephemeral` 缓存控制，可以减少重复请求的成本

---

## 如何使用本文档

### 在 ccproxy 中模拟 Claude Code 请求

1. 在 Web UI 中选择 `ClaudeCode` 预设（Header Override 和 Request Override）
2. 点击 `Apply` 应用配置
3. 使用 `Refresh & Test All` 或 `Test Selected` 测试 Provider

### 自定义部分字段

如果只需要修改部分字段（如 IP 地址），可以在 `config.json` 中创建自定义预设：

```json
{
  "HeaderOverrides": {
    "CustomIP": {
      "X-Real-IP": "1.2.3.4",
      "X-Forwarded-For": "1.2.3.4"
    }
  }
}
```

这样只会覆盖指定的字段，不会影响其他请求内容。

### 查看实际请求

所有请求的详细信息都会记录在 `ccproxy.log` 文件中：
- `forward: upstream_headers` - 实际发送的请求头
- `forward: request_body` - 实际发送的请求体
