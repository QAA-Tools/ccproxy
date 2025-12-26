# 之前ccr的脚本
python3 update_models.py --timeout 5 --filter "4-5,4.5,glm-4.6,glm-4.5,sonnet-4.5,4.5-sonnet,qwen3-max,v3.2" #有的站点采用4.5-cc表示4-5
cp config.json ~/.claude-code-router/
ccr restart