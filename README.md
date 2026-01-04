# Claude Code Proxy

[简体中文](README_zh.md)

A lightweight Claude API reverse proxy providing Anthropic endpoint access only. Switch providers via Web UI without restarting Claude Code. Works as a public gateway management tool: auto model refresh, quick copy URL/Token, generate ccr/ccswitch/cliproxyapi configs.

![demo](demo.png)

## Core Features

- **Auto Model Discovery** - Automatically fetch model lists from provider's `/v1/models`, no need to manually query and input `/model xxx`
- **Instant Switching** - Switch providers via Web UI without restarting Claude Code
- **Quick Copy** - One-click copy URL, API key, `/model xxx` commands
- **Hot Reload** - Reload `config.json` changes via UI
- **HTTP Overrides** - Spoof client characteristics (User-Agent, request body, etc.) to bypass site detection

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
  "env-models": {
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-5-20251101",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5-20250929",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5-20250929"
  },
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
      "name": "Provider Name",
      "api_base_url": "https://api.example.com/v1/messages",
      "api_key": "sk-provider-key",
      "models": [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101"
      ],
      "comment": "Notes",
      "env-models": {
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "custom-haiku",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "custom-opus",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "custom-sonnet",
        "ANTHROPIC_MODEL": "custom-sonnet"
      }
    }
  ]
}
```

**Configuration Notes:**
- `env-models` (optional) - Model name mapping configuration for Claude Code environment variables
  - **Global level** (top-level `env-models`): Default model name mapping for all providers
  - **Provider level** (`env-models` inside Provider): Custom model name mapping for specific provider
  - **Priority**: Provider-level config overrides global config
  - **Use case**: Different providers may use different model naming (e.g., `gemini-claude-sonnet-4-5` vs `claude-sonnet-4-20250514`)
  - Empty `{}` means using Claude Code defaults

**HTTP Overrides:**
- `HeaderOverrides` - Override request headers (e.g., User-Agent) to spoof as Claude CLI or other clients
- `RequestOverrides` - Override request body (e.g., remove tools field) to adapt to unsupported sites
- Configure override presets per provider via Web UI

## Background Run (Linux)

Use `run.sh` script to manage background process:

```bash
./run.sh start    # Start
./run.sh stop     # Stop
./run.sh restart  # Restart
./run.sh status   # Status
# Clean logs periodically
0 0 * * * cd /home/cndaqiang/git/ccproxy && cp ccproxy.log ccproxy.log.old && truncate -s 0 ccproxy.log 2>/dev/null
```

Logs: `ccproxy.log` | PID: `ccproxy.pid`

## Tools

**ccp_update_model.py** - Update model list in ccproxy config.json
- Input/Output: `config.json` (default)
```bash
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"
```

**ccp2ccr.py** - Convert config to claude-code-router format
- Input: `config.json` | Output: `cc-router.json`
```bash
bash tools/ccp2ccr.sh
# Or manually: python tools/ccp2ccr.py --update-models --filter "4-5,sonnet"
```

**ccp2ccswitch.py** - Convert config to CC Switch SQL format (no need to manually manage providers in GUI)
- Input: `config.json` | Output: `cc-switch.sql` or standalone Claude Code config file
```bash
# Export CC Switch SQL format
bash tools/ccp2ccswitch.sh
# Or manually: python tools/ccp2ccswitch.py --input config.json --prefix

# Export standalone Claude Code config file (with env-models)
python tools/ccp2ccswitch.py --export-cc --provider "example-provider1" --output provider1.json
# Or use --current to specify provider
python tools/ccp2ccswitch.py --export-cc --current "example-provider1"
```

**ccp2cliproxy.py** - Convert config to CLIProxyAPI YAML format
- Input: `config.json` | Output: `cliproxy.yaml`
```bash
bash tools/ccp2cliproxy.sh
```

See [tools/README.md](tools/README.md) for details.

## Credits

Claude Code, Codex, Antigravity

## License

MIT
