# Claude Code Proxy

Claude Code Proxy — 轻量直连反向代理，无需重启即可切换供应商。


## 快速开始

1) 复制示例配置：

```bash
copy config.in.json config.json
```

2) 编辑 `config.json` 填入你的上游信息。

3) 启动代理（默认读取 `config.json`）：

```bash
python ccproxy.py --config config.json
```

4) 打开 Web UI（浏览器会弹出 Basic Auth）：

```
http://127.0.0.1:3456
```

密码就是 `APIKEY`（用户名随意）。

5) Claude Code 配置示例：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}
```

## 配置文件说明

- `config.in.json`：示例配置
- `config.json`：实际配置
- `proxy_state.json`：记录上次选择 + 覆盖规则；可删除（UI 会退回第一个 provider）

## 认证覆盖（可选）

每个 provider 可以覆盖 token 的发送方式：

- `token_in`: `header` / `query` / `both`
- `token_header`: 默认 `Authorization`
- `token_header_format`: 默认 `Bearer {token}`

覆盖规则只影响运行时路由。修改 `config.json` 后请点击 **Reload Config** 重新加载。

## 备注与致谢

- 致谢：https://github.com/musistudio/claude-code-router
- `config.json` 采用 [ccr](https://github.com/musistudio/claude-code-router) 的格式，但不包含 openai/deepseek 等模型转换为 Claude Code 的功能。
- 本项目只是简单反向代理，仅适用于已提供 Claude 兼容端点的上游（公益站/官方/GLM 等）。使用 Claude Code 时，需要输入 `/model <模型名>` 选择不同 provider 的指定模型（UI 的 Copy 按钮可以直接复制）。

## ?????Linux?

```bash
./run.sh start
./run.sh stop
./run.sh restart
./run.sh status
```

Logs: `ccproxy.log`  |  PID: `ccproxy.pid`

