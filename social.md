# 囤囤鼠自用的 Claude Code 轻量反代脚本：切换 + 签到 + 保活公益站

最近站里各位佬的公益站/转发站越来越多，屯屯鼠本鼠余额也攒了不少。不过有的站能跑 CC，有的只能 Chat；今天稳得一批，明天就开始抽风。经常写着写着代码就得停下来换站点。
最近公益站开始清理屯屯鼠账号了，所以增加了 `Refresh & Test` 功能，定期测试所有站点。

之前采用的 CC&公益站 切换方案：
- **[NewAPI](https://github.com/Calcium-Ion/new-api)**：能自动拉模型列表，兼容 CC/Chat 等调用方式，适合佬们开公益站。但个人用来管理公益站 URL 的话，出问题排查太费事
- **[ccr](https://github.com/musistudio/claude-code-router)**：功能很全，路由能力强（能把不同模型转换）。但模型列表要自己填，Web 界面改配置经常不生效，路由功能用不到
- **[cc-switch](https://github.com/farion1231/cc-switch)**：热重启切换，单机体验很好。但配置只能图形界面或 SQLite 改，我更习惯直接编辑 JSON

因为经常要在 Linux 服务器上跑，就想要个更简单的方案：JSON 配置 + 不重启 CC 就能切换 + 自动拉模型列表 + 定期测试。

所以让 Claude 搓了这个：**Claude Code Proxy**

用了N周还算稳定，就一个 py 脚本，核心功能：
- Web UI 切换供应商，自动拉取模型列表
- 一键复制 URL/Key/Model、打开签到/福利站链接
- 多终端统一出口 IP，避免多设备访问同一公益站被封号

## 快速开始

**仓库地址：** https://github.com/QAA-Tools/ccproxy | **使用文档：** https://qaa-tools.github.io/ccproxy/

1. 复制配置文件：
```bash
copy config.in.json config.json  # Windows
cp config.in.json config.json    # Linux/macOS
```

2. 编辑 `config.json`，填入你的公益站信息：
```json
{
  "HOST": "0.0.0.0",
  "PORT": 3456,
  "APIKEY": "sk-your-local-ui-key",
  "Providers": [
    {
      "name": "站点1",
      "api_base_url": "https://api.example.com/v1/messages",
      "api_key": "sk-provider-key-1",
      "models": [],
      "checkin": "https://example.com/console/personal"
    }
  ]
}
```

3. 启动代理：
```bash
python ccproxy.py --config config.json
```

4. 修改 Claude Code 配置（`~/.claude/settings.json` 或 `%USERPROFILE%\.claude\settings.json`）：
```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-your-local-ui-key",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  }
}
```
**注意：** `ANTHROPIC_AUTH_TOKEN` 要和上面的 `APIKEY` 一致。改完重启 CC。

5. 浏览器打开 `http://127.0.0.1:3456`，用 `APIKEY` 作为密码登录（用户名随便填）

## 使用

**基础操作：**
- 下拉选择 provider，立即生效
- 点 **Refresh** 按钮自动拉取上游模型列表
- 选模型后点 **Copy**，粘贴 `/model xxx` 命令到 CC 切换模型
- 上游挂了就回网页换一个
- 改了 `config.json` 点 **Reload Config** 重新载入，不用重启代理

**测试操作：**
- 点 **Refresh & Test** 按钮，批量测试所有站点，测试结果显示为颜色：绿色（成功）/ 黑色（失败）
- 若失败可查看输出日志排查原因
- 点 **签到** 按钮快速跳转到站点签到页面领额度

**进阶技巧：**
- 点击 **settings.json** 按钮，将剪贴板粘贴到 `~/.claude/settings.json` 文件中，也可以不重启 Claude Code 立即切换供应商

---

**注：** 配置格式兼容 ccr，但不包含模型转换功能（只支持原生 Claude 格式的 API）。