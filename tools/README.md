# 工具说明

ccproxy 的辅助工具集。

**工具分类：**
- `ccp_xxx` - ccproxy 内部工具（如 ccp_update_model）
- `ccp2xxx` - ccproxy 转换到其他格式的工具

## ccp_update_model.py

**用途：** 更新 ccproxy config.json 的模型列表

**使用：**

```bash
# 更新模型列表（默认 config.json）
python ccp_update_model.py

# 过滤模型（只保留包含 "4-5" 或 "sonnet" 的模型）
python ccp_update_model.py --filter "4-5,sonnet"

# 自定义超时时间
python ccp_update_model.py --timeout 5

# 指定输入输出文件
python ccp_update_model.py --input config.json --output config.json
```

**参数：**

- `--input`, `-i`: 输入 JSON 文件（默认：`config.json`）
- `--output`, `-o`: 输出 JSON 文件（默认：`config.json`）
- `--timeout`, `-t`: API 请求超时时间（秒，默认：30）
- `--filter`, `-f`: 模型筛选关键词，逗号分隔

**输出示例：**

```
共有 23 个提供商需要更新(超时: 5s)

[1/23] [OK] runanytime: 6 个模型 (2.3s) ***
[2/23] [OK] wong: 7 个模型 (3.1s)
[3/23] [FAIL] rewind: API 返回 HTML 错误页面(可能是认证失败或 URL 错误)
...
```

最快的 3 个供应商会标记 `***`。

## ccp2ccr.py

**用途：** 将 ccproxy 配置转换为 claude-code-router 格式

**使用：**

```bash
# 使用便捷脚本（推荐）
bash ccp2ccr.sh

# 或手动调用
# 仅转换格式
python ccp2ccr.py --input config.json --output cc-router.json

# 转换并更新模型列表
python ccp2ccr.py --update-models --timeout 5

# 转换、更新并筛选模型
python ccp2ccr.py --update-models --filter "4-5,sonnet"
```

**参数：**

- `--input`, `-i`: 输入 JSON 文件（默认：`config.json`）
- `--output`, `-o`: 输出 JSON 文件（默认：`cc-router.json`）
- `--update-models`, `-u`: 是否更新每个提供商的模型列表
- `--timeout`, `-t`: API 请求超时时间（秒，默认：30）
- `--filter`, `-f`: 模型筛选关键词，逗号分隔

**特性：**

- 自动为每个供应商添加 `transformer: { "use": ["Anthropic"] }`
- 自动添加 `Router` 配置（所有值默认为空）
- 支持更新模型列表（可选）

**工作流：**

```
config.json → ccp2ccr.py → cc-router.json → claude-code-router
```

## ccp2ccswitch.py

**用途：** 将 ccproxy 配置转换为 CC Switch SQL 格式（无需在 GUI 中手动批量管理供应商）

**使用：**

```bash
# 使用便捷脚本（推荐，带序号前缀）
bash ccp2ccswitch.sh

# 或手动调用
# 基本转换
python ccp2ccswitch.py --input config.json --output cc-switch.sql

# 添加序号前缀（01-, 02-, ...）保持顺序
python ccp2ccswitch.py --input config.json --prefix

# 设置当前激活的供应商
python ccp2ccswitch.py --input config.json --current "runanytime"
```

**参数：**

- `--input`, `-i`: 输入 JSON 文件（默认：`config.json`）
- `--output`, `-o`: 输出 SQL 文件（默认：`cc-switch.sql`）
- `--prefix`, `-p`: 添加序号前缀到供应商名称
- `--current`, `-c`: 设置激活的供应商（默认：第一个）

**特性：**

- 自动提取 `website_url`（优先使用配置中的字段，否则从 `api_base_url` 提取域名）
- 支持添加序号前缀，保持配置文件中的顺序
- 生成完整的 SQLite 导入脚本

**工作流：**

```
config.json → ccp2ccswitch.py → cc-switch.sql → CC Switch
```

**导入到 CC Switch：**

使用 CC Switch GUI 的导入功能导入 `cc-switch.sql` 文件。

## ccp2cliproxy.py

**用途：** 将 ccproxy 配置转换为 CLIProxyAPI YAML 格式

**使用：**

```bash
# 使用便捷脚本（推荐）
bash ccp2cliproxy.sh

# 或手动调用
python ccp2cliproxy.py --input config.json --output cliproxy.yaml
```

**参数：**

- `--input`, `-i`: 输入 JSON 文件（默认：`config.json`）
- `--output`, `-o`: 输出 YAML 文件（默认：`cliproxy.yaml`）

**工作流：**

```
config.json → ccp2cliproxy.py → cliproxy.yaml → CLIProxyAPI
```

## 使用示例

### 示例 1：更新模型并启动代理

```bash
# 获取供应商模型
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"

# 启动代理
python ccproxy.py --config config.json
```

### 示例 2：转换配置给 claude-code-router

```bash
# 转换配置并更新模型
bash tools/ccp2ccr.sh

# 复制到 claude-code-router 配置目录
cp cc-router.json ~/.claude-code-router/config.json
ccr restart
```

### 示例 3：转换配置给 CC Switch

```bash
# 添加序号前缀转换
bash tools/ccp2ccswitch.sh

# 使用 CC Switch GUI 导入 cc-switch.sql
```

### 示例 4：转换配置给 CLIProxyAPI

```bash
# 转换为 YAML 格式
bash tools/ccp2cliproxy.sh

# 使用生成的 cliproxy.yaml 配置 CLIProxyAPI
```

### 示例 5：完整工作流

```bash
# 1. 编辑 config.json 添加供应商
# 2. 获取模型
python tools/ccp_update_model.py --timeout 5 --filter "4-5,sonnet"

# 3. 选择使用场景
# 场景 A：服务器使用 ccproxy
python ccproxy.py --config config.json

# 场景 B：使用 claude-code-router
bash tools/ccp2ccr.sh
cp cc-router.json ~/.claude-code-router/config.json

# 场景 C：桌面使用 CC Switch
bash tools/ccp2ccswitch.sh
# 使用 CC Switch GUI 导入 cc-switch.sql

# 场景 D：使用 CLIProxyAPI
bash tools/ccp2cliproxy.sh
```

## 注意事项

- 所有工具默认使用 `config.json` 作为输入
- `ccp_update_model.py` 默认就地更新 `config.json`
- `ccp2xxx` 工具生成各自格式的输出文件
- 工具独立使用，按需选择
- 建议使用 `.sh` 便捷脚本，已配置常用参数
