# Claude Code Proxy

[简体中文](README_zh.md)

A lightweight Claude API reverse proxy providing Web UI to manage multiple providers with auto model discovery and instant switching.

![demo](demo.png)

## Core Features

- **Instant Switching** - Switch providers via Web UI without restarting Claude Code
- **Auto Discovery** - Automatically fetch model lists from provider's `/v1/models`
- **HTTP Overrides** - Spoof client characteristics to bypass site detection
- **Batch Testing** - Refresh & Test all providers in one click
- **Hot Reload** - Reload config changes via UI
- **Multi-Endpoint Support** - Support `/v1/messages`, `/v1/chat/completions`, and `/v1/responses` endpoints

## Quick Start

```bash
# 1. Copy config
cp config.in.json config.json

# 2. Edit config.json to add provider info

# 3. Start proxy
python ccproxy.py --config config.json

# 4. Configure Claude Code (~/.claude/settings.json)
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<YOUR_APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}

# 5. Access Web UI
# http://127.0.0.1:3456 (password is your APIKEY)
```

## Full Documentation

For detailed configuration, button functions, HTTP overrides, FAQ, etc., visit:

**📖 [Full Documentation](https://qaa-tools.github.io/ccproxy/)** or local access `http://127.0.0.1:3456/docs`

## Background Run (Linux)

Use `run.sh` script to manage background process:

```bash
./run.sh start    # Start
./run.sh stop     # Stop
./run.sh restart  # Restart
./run.sh status   # Status
```

Logs: `ccproxy.log` | PID: `ccproxy.pid`

## Tools

**ccp_update_model.py** - Update model list in ccproxy config.json
```bash
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"
```

**ccp2ccr.py** - Convert config to claude-code-router format
```bash
bash tools/ccp2ccr.sh
```

**ccp2ccswitch.py** - Convert config to CC Switch SQL format
```bash
bash tools/ccp2ccswitch.sh
```

**ccp2cliproxy.py** - Convert config to CLIProxyAPI YAML format
```bash
bash tools/ccp2cliproxy.sh
```

See [tools/README.md](tools/README.md) for details.

## Credits

Claude Code, Codex, Antigravity

## License

MIT
