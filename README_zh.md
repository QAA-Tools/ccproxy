# Claude Code Proxy

[English](README.md)

轻量级 Claude API 反向代理工具，提供 Web UI 管理多个供应商，支持自动模型发现、即时切换等功能。

![demo](demo.png)

## 核心特性

- **即时切换** - Web UI 切换供应商，无需重启 Claude Code
- **自动发现** - 从供应商 `/v1/models` 自动获取模型列表
- **HTTP 覆写** - 支持客户端特征伪装，绕过站点检测
- **批量测试** - Refresh & Test 一键测试所有供应商
- **热重载** - 修改配置后通过 UI 重新加载

## 快速开始

```bash
# 1. 复制配置
cp config.in.json config.json

# 2. 编辑 config.json 添加供应商信息

# 3. 启动代理
python ccproxy.py --config config.json

# 4. 配置 Claude Code (~/.claude/settings.json)
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<你的APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}

# 5. 访问 Web UI
# http://127.0.0.1:3456 (密码是你的 APIKEY)
```

## 完整文档

详细的配置说明、按钮功能、HTTP 覆写、FAQ 等请访问：

**📖 [完整文档](https://qaa-tools.github.io/ccproxy/)** 或本地访问 `http://127.0.0.1:3456/docs`

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

**ccp_update_model.py** - 更新 ccproxy config.json 的模型列表
```bash
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"
```

**ccp2ccr.py** - 转换配置为 claude-code-router 格式
```bash
bash tools/ccp2ccr.sh
```

**ccp2ccswitch.py** - 转换配置为 CC Switch SQL 格式
```bash
bash tools/ccp2ccswitch.sh
```

**ccp2cliproxy.py** - 转换配置为 CLIProxyAPI YAML 格式
```bash
bash tools/ccp2cliproxy.sh
```

详见 [tools/README.md](tools/README.md)

## 致谢

Claude Code, Codex, Antigravity

## 许可证

MIT
