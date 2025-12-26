# 缝合 newapi/ccr/cc-switch 的轻量反代脚本 用来切换各位佬的公益站

最近站里各位佬的公益站/转发站越来越多，屯屯鼠本鼠余额也攒了不少。不过有的站能跑 CC，有的只能 Chat；今天稳得一批，明天就开始抽风。经常写着写着代码就得停下来换站点。

之前采用的 CC&公益站 切换方案：
- **[NewAPI](https://github.com/Calcium-Ion/new-api)**：能自动拉模型列表，兼容 CC/Chat 等调用方式，适合佬们开公益站。但个人用来管理公益站 URL 的话，出问题排查太费事
- **[ccr](https://github.com/musistudio/claude-code-router)**：功能很全，路由能力强（能把不同模型转换）。但模型列表要自己填，Web 界面改配置经常不生效，路由功能用不到
- **[cc-switch](https://github.com/farion1231/cc-switch)**：热重启切换，单机体验很好。但配置只能图形界面或 SQLite 改，我更习惯直接编辑 JSON

因为经常要在 Linux 服务器上跑（没有图形界面，cc-switch 不适合），就想要个更简单的方案：JSON 配置 + 不重启 CC 就能切换 + 自动拉模型列表。

所以让 Codex 搓了这个：**Claude Code Proxy**

用了两天还算稳定，仓库地址（就一个 py 脚本）：https://github.com/QAA-Tools/ccproxy

```
python ccproxy.py --config config.json
```

然后浏览器打开 `http://127.0.0.1:3456`

- 网页上选 provider
- **刷新获取模型列表**（从上游 `/v1/models` 拉取）
- 复制 `/model xxx` 命令粘贴到 CC 即可切换模型
- 上游挂了就回网页换一个
- 改了 config.json 网页上点 Reload 重新载入

就是个轻量反向代理，配置格式参考 ccr（完全兼容）。