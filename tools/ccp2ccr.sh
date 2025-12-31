#!/bin/bash
# 将 ccproxy 配置转换为 claude-code-router 格式
# 更新模型列表并筛选，添加 transformer 配置

python3 tools/ccp2ccr.py --input config.json --output cc-router.json --update-models --timeout 5 --filter "4-5,4.5,sonnet-4.5,4.5-sonnet"
# cp cc-router.json ~/.claude-code-router/config.json
# ccr restart