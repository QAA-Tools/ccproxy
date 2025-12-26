# ccproxy

[简体中文](README_zh.md)


Lightweight Claude Code proxy with a local Web UI.

## Quick start

1) Copy the example config:

```bash
copy config.in.json config.json
```

2) Edit `config.json` with your provider info.

3) Start proxy (default config is `config.json`):

```bash
python ccproxy.py --config config.json
```

4) Open the UI (browser will ask for Basic Auth):

```
http://127.0.0.1:3456
```

Password is your `APIKEY` from the config file (username can be anything).

5) Claude Code config example:

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<APIKEY>",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}
```

## Config files

- `config.in.json`: example config
- `config.json`: active config
- `proxy_state.json`: stores last selection + auth overrides; safe to delete (UI will fall back to first provider).

## Auth overrides

Each provider can override how tokens are sent:
- `token_in`: `header` / `query` / `both`
- `token_header`: default `Authorization`
- `token_header_format`: default `Bearer {token}`

These overrides only affect runtime routing. Update `config.json` and click **Reload Config** to apply file changes.

## Notes

- Thanks to https://github.com/musistudio/claude-code-router
- `config.json` follows the [ccr](https://github.com/musistudio/claude-code-router) format, but this project does not provide model conversion (OpenAI/DeepSeek/etc.).
- This proxy is a simple reverse proxy, intended for upstreams that already expose Claude-compatible endpoints (public gateways/official/GLM, etc.).

