# Claude Code Proxy

[English](README.md)

轻量级 Claude API 反向代理工具，无需重启 Claude Code，通过 Web UI 切换管理多个供应商。

![demo](demo.png)

## 核心功能

- **自动模型发现** - 从供应商 `/v1/models` 自动获取模型列表，无需手动查询和输入 `/model xxx`
- **即时切换** - Web UI 切换供应商，无需重启 Claude Code
- **快速复制** - 一键复制 URL、API key、`/model xxx` 命令
- **热重载** - 修改 `config.json` 后通过 UI 重新加载
- **HTTP 覆写** - 伪装客户端特征（User-Agent、请求体等），绕过站点检测限制

## 快速开始

```bash
# 1. 复制配置
cp config.in.json config.json

# 2. 编辑 config.json 添加供应商

# 3. 启动代理
python ccproxy.py --config config.json

# 4. 配置 Claude Code (~/.claude/config.json)
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<你的APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}

# 5. 访问 Web UI
# http://127.0.0.1:3456 (密码是你的 APIKEY)
```

## 特色对比

| 工具 | 配置 | 模型发现 | 切换 | 部署方式 |
|------|------|---------|------|---------|
| **ccproxy** | JSON | ✅ 自动 | Web UI | 反向代理 |
| ccr | JSON | ❌ 手动 | Web UI | 反向代理 |
| cc-switch | SQLite | ❌ 手动 | GUI | 直接修改本地配置 |
| NewAPI | DB | ✅ 自动 | Web UI | 反向代理 |

**为什么选 ccproxy？**
- 公益站点模型名需要手动查询才知道，ccproxy 自动获取并提供复制功能
- 反向代理方式，适合服务器无 GUI 环境（cc-switch 需要 GUI 直接修改本地配置）
- 一键复制功能，快速获取 URL/key/模型命令

## 配置

```json
{
  "HOST": "0.0.0.0",
  "PORT": 3456,
  "APIKEY": "sk-your-key",
  "HeaderOverrides": {
    "ClaudeCode": {
      "User-Agent": "claude-cli/2.0.76 (external, cli)",
      "x-app": "cli"
    },
    "None (Passthrough)": {}
  },
  "RequestOverrides": {
    "None (Passthrough)": {},
    "ClaudeCode": {
      "tools": []
    }
  },
  "Providers": [
    {
      "name": "供应商名称",
      "api_base_url": "https://api.example.com/v1/messages",
      "api_key": "sk-provider-key",
      "models": [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101"
      ],
      "comment": "备注"
    }
  ]
}
```

**HTTP 覆写说明：**
- `HeaderOverrides` - 覆写请求头（如 User-Agent），伪装成 Claude CLI 等客户端
- `RequestOverrides` - 覆写请求体（如移除 tools 字段），适配不支持的站点
- 通过 Web UI 可为每个供应商单独配置覆写预设

## 后台运行（Linux）

使用 `run.sh` 脚本管理后台进程：

```bash
./run.sh start    # 启动
./run.sh stop     # 停止
./run.sh restart  # 重启
./run.sh status   # 状态
# 定期清理日志
0 0 * * * cd /home/cndaqiang/git/ccproxy && cp ccproxy.log ccproxy.log.old && truncate -s 0 ccproxy.log 2>/dev/null
```

日志：`ccproxy.log` | PID：`ccproxy.pid`

## 工具

**ccp_update_model.py** - 更新 ccproxy config.json 的模型列表
- 输入/输出：`config.json`（默认）
```bash
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"
```

**ccp2ccr.py** - 转换配置为 claude-code-router 格式
- 输入：`config.json` | 输出：`cc-router.json`
```bash
bash tools/ccp2ccr.sh
# 或手动: python tools/ccp2ccr.py --update-models --filter "4-5,sonnet"
```

**ccp2ccswitch.py** - 转换配置为 CC Switch SQL 格式（无需在 GUI 中手动批量管理供应商）
- 输入：`config.json` | 输出：`cc-switch.sql`
```bash
bash tools/ccp2ccswitch.sh
# 或手动: python tools/ccp2ccswitch.py --input config.json --prefix
```

**ccp2cliproxy.py** - 转换配置为 CLIProxyAPI YAML 格式
- 输入：`config.json` | 输出：`cliproxy.yaml`
```bash
bash tools/ccp2cliproxy.sh
```

详见 [tools/README.md](tools/README.md)

## 致谢

Claude Code, Codex, Antigravity

## 许可证

MIT
