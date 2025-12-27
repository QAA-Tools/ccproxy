# 工具说明

ccproxy 的辅助工具集。

**配置说明：**
- `ccr.in.json` 和 `config.json` 格式完全相同
- 配置兼容 ccr 和 ccproxy
- `update_models.py` 只是刷新其中的 model 列表

## update_models.py

**用途：** 批量获取供应商的模型列表并过滤（弥补 ccr 无法自动拉取模型的问题）

**使用：**

```bash
# 从所有供应商获取模型
python update_models.py

# 过滤模型（只保留包含 "4-5" 或 "glm" 的模型）
python update_models.py --filter "4-5,glm"

# 自定义超时时间
python update_models.py --timeout 60
```

**工作流：**

```
ccr.in.json → update_models.py → config.json → ccr/ccproxy.py
                                                  ↓
                                            (两者都可以)
```

1. 编辑 `ccr.in.json`，填入供应商 URL 和 API key
2. 运行 `update_models.py` 刷新模型列表
3. 脚本保存到 `config.json`，包含更新后的模型
4. 用 `config.json` 启动 ccr 或 ccproxy

**输出示例：**

```
共有 23 个提供商需要更新（超时: 30s）

[1/23] [OK] runanytime: 6 个模型 (2.3s) ***
[2/23] [OK] wong: 7 个模型 (3.1s)
[3/23] [FAIL] rewind: 请求超时
...
```

最快的 3 个供应商会标记 `***`。

**ccr.sh** - 示例脚本，展示如何使用 update_models.py 的常用参数

## ccr2switch.py

**用途：** 将 ccproxy 配置转换为 CC Switch SQL 格式（无需在 GUI 中手动批量管理供应商）

**使用：**

```bash
# 基本转换
python ccr2switch.py --input config.json --output cc-switch.sql

# 添加序号前缀（01-, 02-, ...）保持顺序
python ccr2switch.py --input config.json --prefix

# 设置当前激活的供应商
python ccr2switch.py --input config.json --current "runanytime"
```

**参数：**

- `--input`, `-i`: 输入 JSON 文件（默认：`config.json`）
- `--output`, `-o`: 输出 SQL 文件（默认：`cc-switch.sql`）
- `--prefix`, `-p`: 添加序号前缀到供应商名称
- `--current`, `-c`: 设置激活的供应商（默认：第一个）

**工作流：**

```
config.json → ccr2switch.py → cc-switch.sql → CC Switch
```

1. 从 ccproxy 配置生成 SQL
2. 导入 SQL 到 CC Switch 数据库
3. 使用 CC Switch GUI 管理供应商

**导入到 CC Switch：**

使用 CC Switch GUI 的导入功能导入 `cc-switch.sql` 文件。

## 使用示例

### 示例 1：更新模型并启动代理

```bash
# 获取供应商模型
python tools/update_models.py --filter "4-5,glm"

# 启动代理
python ccproxy.py --config config.json
```

### 示例 2：转换配置给 CC Switch

```bash
# 添加序号前缀转换
python tools/ccr2switch.py --input config.json --prefix

# 使用 CC Switch GUI 导入 cc-switch.sql
```

### 示例 3：完整工作流

```bash
# 1. 编辑 ccr.in.json 添加供应商
# 2. 获取模型
python tools/update_models.py --filter "4-5"

# 3. 服务器使用 ccproxy
python ccproxy.py --config config.json

# 或桌面使用 CC Switch
python tools/ccr2switch.py --input config.json --prefix
# 使用 CC Switch GUI 导入 cc-switch.sql
```

## 注意事项

- 所有工具读取 `ccr.in.json` 或 `config.json`
- `update_models.py` 写入 `config.json`
- `ccr2switch.py` 写入 `cc-switch.sql`
- 工具独立使用，按需选择
