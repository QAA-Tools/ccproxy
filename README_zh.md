# Claude Code Proxy

[English](README.md)

轻量级 Claude API 反向代理工具，无需重启 Claude Code，通过 Web UI 切换管理多个供应商。

![demo](demo.png)

## 核心功能

- **自动模型发现** - 从供应商 `/v1/models` 自动获取模型列表，无需手动查询和输入 `/model xxx`
- **即时切换** - Web UI 切换供应商，无需重启 Claude Code
- **快速复制** - 一键复制 URL、API key、`/model xxx` 命令
- **热重载** - 修改 `config.json` 后通过 UI 重新加载

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
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
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
  "Providers": [
    {
      "name": "供应商名称",
      "api_base_url": "https://api.example.com/v1/messages",
      "api_key": "sk-provider-key",
      "models": [],  // 留空，用 Web UI 刷新按钮自动获取
      "comment": "备注"
    }
  ]
}
```

## 后台运行（Linux）

使用 `run.sh` 脚本管理后台进程：

```bash
./run.sh start    # 启动
./run.sh stop     # 停止
./run.sh restart  # 重启
./run.sh status   # 状态
```

日志：`ccproxy.log` | PID：`ccproxy.pid`

## 工具

**update_models.py** - 批量获取并过滤模型列表（弥补 ccr 无法自动拉取模型的问题）
- 输入：`ccr.in.json`
- 输出：`config.json`
```bash
python tools/update_models.py --filter "4-5,glm"
```

**ccr2switch.py** - 转换配置为 CC Switch SQL 格式（无需在 GUI 中手动批量管理供应商）
- 输入：`config.json`
- 输出：`cc-switch.sql`
```bash
python tools/ccr2switch.py --input config.json --prefix
```

详见 [tools/README.md](tools/README.md)

## 致谢

灵感来自 [claude-code-router](https://github.com/musistudio/claude-code-router)

## 许可证

MIT
