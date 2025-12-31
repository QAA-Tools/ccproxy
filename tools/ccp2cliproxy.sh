#!/bin/bash
# 将 ccproxy 配置转换为 CLIProxyAPI 格式

python3 tools/ccp2cliproxy.py --input config.json --output cliproxy.yaml
