# Claude Code Proxy

[简体中文](README_zh.md)

A lightweight Claude API reverse proxy tool for managing multiple providers via Web UI without restarting Claude Code.

![demo](demo.png)

## Core Features

- **Auto Model Discovery** - Automatically fetch model lists from provider's `/v1/models`, no need to manually query and input `/model xxx`
- **Instant Switching** - Switch providers via Web UI without restarting Claude Code
- **Quick Copy** - One-click copy URL, API key, `/model xxx` commands
- **Hot Reload** - Reload `config.json` changes via UI

## Quick Start

```bash
# 1. Copy config
cp config.in.json config.json

# 2. Edit config.json to add providers

# 3. Start proxy
python ccproxy.py --config config.json

# 4. Configure Claude Code (~/.claude/config.json)
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<YOUR_APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}

# 5. Access Web UI
# http://127.0.0.1:3456 (password is your APIKEY)
```

## Comparison

| Tool | Config | Model Discovery | Switching | Deployment |
|------|--------|----------------|-----------|------------|
| **ccproxy** | JSON | ✅ Auto | Web UI | Reverse proxy |
| ccr | JSON | ❌ Manual | Web UI | Reverse proxy |
| cc-switch | SQLite | ❌ Manual | GUI | Direct local config |
| NewAPI | DB | ✅ Auto | Web UI | Reverse proxy |

**Why ccproxy?**
- Public gateways require manual model name lookup, ccproxy auto-fetches and provides copy functionality
- Reverse proxy approach, suitable for servers without GUI (cc-switch requires GUI to modify local config)
- One-click copy for quick access to URL/key/model commands

## Configuration

```json
{
  "HOST": "0.0.0.0",
  "PORT": 3456,
  "APIKEY": "sk-your-key",
  "Providers": [
    {
      "name": "Provider Name",
      "api_base_url": "https://api.example.com/v1/messages",
      "api_key": "sk-provider-key",
      "models": [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101"
      ],
      "comment": "Notes"
    }
  ]
}
```

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

**update_models.py** - Batch fetch and filter model lists (solves ccr's inability to auto-fetch models)
- Input: `ccr.in.json`
- Output: `config.json`
```bash
python tools/update_models.py --filter "4-5,glm"
```

**ccr2switch.py** - Convert config to CC Switch SQL format (no need to manually manage providers in GUI)
- Input: `config.json`
- Output: `cc-switch.sql`
```bash
python tools/ccr2switch.py --input config.json --prefix
```

See [tools/README.md](tools/README.md) for details.

## Credits

Inspired by [claude-code-router](https://github.com/musistudio/claude-code-router)

## License

MIT
