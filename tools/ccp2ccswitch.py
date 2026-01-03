#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 ccproxy 的 config.json 转换为 CC Switch 的 SQLite 格式
用法: python ccp2ccswitch.py [--input config.json] [--output cc-switch.sql]
"""

import json
import sys
import argparse
from datetime import datetime
from urllib.parse import urlparse

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def extract_base_url(api_base_url):
    """
    从 api_base_url 中提取基础 URL
    支持多种格式:
    - Claude 格式: https://api.example.com/v1/messages -> https://api.example.com
    - OpenAI 格式: https://api.example.com/v1/chat/completions -> https://api.example.com
    - Anthropic 格式: https://api.example.com/anthropic/v1/messages -> https://api.example.com
    """
    # 优先检查更具体的格式
    if "/anthropic/v1/messages" in api_base_url:
        return api_base_url.replace("/anthropic/v1/messages", "")
    elif "/v1/chat/completions" in api_base_url:
        return api_base_url.replace("/v1/chat/completions", "")
    elif "/v1/messages" in api_base_url:
        return api_base_url.replace("/v1/messages", "")
    # 如果都不匹配，返回原始 URL
    return api_base_url


def sanitize_id(name):
    """
    将 provider name 转换为合法的 ID
    例如: "runanytime.hxi.me" -> "runanytime_hxi_me"
    """
    # 替换特殊字符为下划线
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    # 移除连续的下划线
    sanitized = re.sub(r'_+', '_', sanitized)
    # 移除首尾的下划线
    sanitized = sanitized.strip('_')
    return sanitized.lower()


def escape_sql_string(s):
    """转义 SQL 字符串中的单引号"""
    if s is None:
        return ''
    return str(s).replace("'", "''")


def provider_to_sql(provider, is_current=False, index=None, add_prefix=False, global_env_models=None):
    """
    将单个 provider 转换为 SQL INSERT 语句

    Args:
        provider: ccproxy 的 provider 对象
        is_current: 是否为当前激活的供应商
        index: 供应商序号（从1开始）
        add_prefix: 是否在名称前添加序号前缀
        global_env_models: 全局的 env-models 配置（可以被 provider 级别的配置覆盖）

    Returns:
        SQL INSERT 语句字符串
    """
    # 提取字段
    name = provider.get('name', 'Unknown')
    api_base_url = provider.get('api_base_url', '')
    api_key = provider.get('api_key', '')
    comment = provider.get('comment', '')
    models = provider.get('models', [])
    checkin = provider.get('checkin', '')  # 获取 checkin 属性

    # 如果需要添加序号前缀
    if add_prefix and index is not None:
        name = f"{index:02d}-{name}"

    # 生成 ID
    provider_id = sanitize_id(name)

    # 提取基础 URL
    base_url = extract_base_url(api_base_url)

    # 提取网站 URL
    # 1. 优先使用 provider 中的 website_url 字段
    # 2. 如果不存在，则从 api_base_url 中提取 https://domain/ 部分
    if 'website_url' in provider and provider['website_url']:
        website_url = provider['website_url']
    else:
        # 从 base_url 提取 https://domain/
        parts = base_url.split('/')
        if len(parts) >= 3:
            website_url = f"{parts[0]}//{parts[2]}"
        else:
            website_url = base_url

    # 提取签到 URL
    # 1. 优先使用 provider 中的 checkin 字段
    # 2. 如果不存在或为空，则从 api_base_url 提取 domain，默认为 https://domain/console/personal
    if checkin and checkin.strip():
        checkin_url = checkin
    else:
        # 从 base_url 提取 https://domain/
        parts = base_url.split('/')
        if len(parts) >= 3:
            domain = f"{parts[0]}//{parts[2]}"
            checkin_url = f"{domain}/console/personal"
        else:
            checkin_url = f"{base_url}/console/personal"

    # 构建 settings_config JSON（简化版，只保留必要信息）
    settings_config = {
        "env": {
            "ANTHROPIC_AUTH_TOKEN": api_key,
            "ANTHROPIC_BASE_URL": base_url
        }
    }

    # 合并 env-models 配置
    # 优先级：provider 级别的 env-models > 全局 env-models
    env_models = {}
    if global_env_models:
        env_models.update(global_env_models)
    if 'env-models' in provider and provider['env-models']:
        env_models.update(provider['env-models'])

    # 将 env-models 添加到 settings_config.env
    if env_models:
        settings_config['env'].update(env_models)

    # 如果有模型列表，添加到 meta 中
    meta = {}
    if models:
        meta['models'] = models
    # 添加 checkin_url 到 meta 中
    if checkin_url:
        meta['checkin_url'] = checkin_url

    # 转义字符串（使用紧凑 JSON 格式，无空格）
    name_escaped = escape_sql_string(name)
    settings_config_json = json.dumps(settings_config, ensure_ascii=False, separators=(',', ':'))
    settings_config_escaped = escape_sql_string(settings_config_json)
    website_url_escaped = escape_sql_string(website_url)
    comment_escaped = escape_sql_string(comment)
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(',', ':'))
    meta_escaped = escape_sql_string(meta_json)

    # 生成 SQL
    sql = f"""INSERT INTO "providers" ("id", "app_type", "name", "settings_config", "website_url", "category", "created_at", "sort_index", "notes", "icon", "icon_color", "meta", "is_current") VALUES ('{provider_id}', 'claude', '{name_escaped}', '{settings_config_escaped}', '{website_url_escaped}', 'custom', NULL, NULL, '{comment_escaped}', NULL, NULL, '{meta_escaped}', {1 if is_current else 0});"""

    return sql


def export_claudecode_config(provider, output_file, global_env_models=None):
    """
    导出单个 provider 的 Claude Code 配置文件

    Args:
        provider: ccproxy 的 provider 对象
        output_file: 输出文件路径
        global_env_models: 全局的 env-models 配置

    Returns:
        导出的配置字典
    """
    api_base_url = provider.get('api_base_url', '')
    api_key = provider.get('api_key', '')
    base_url = extract_base_url(api_base_url)

    # 构建配置
    config = {
        "env": {
            "ANTHROPIC_AUTH_TOKEN": api_key,
            "ANTHROPIC_BASE_URL": base_url
        },
        "includeCoAuthoredBy": False
    }

    # 合并 env-models 配置
    env_models = {}
    if global_env_models:
        env_models.update(global_env_models)
    if 'env-models' in provider and provider['env-models']:
        env_models.update(provider['env-models'])

    # 将 env-models 添加到配置
    if env_models:
        config['env'].update(env_models)

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    return config


def generate_sql_file(config, output_file, current_provider=None, add_prefix=False):
    """
    生成完整的 SQL 文件

    Args:
        config: ccproxy 配置对象
        output_file: 输出文件路径
        current_provider: 当前激活的 provider 名称（默认为第一个非 Note 的）
        add_prefix: 是否在名称前添加序号前缀（01-, 02-, ...）
    """
    providers = config.get('Providers', [])
    global_env_models = config.get('env-models', None)

    # 如果没有指定 current_provider，使用第一个 provider
    if current_provider is None and len(providers) > 0:
        current_provider = providers[0].get('name')

    # 生成 SQL 头部(包含表结构和数据)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql_lines = [
        "-- CC Switch SQLite 导出",
        f"-- 生成时间: {now}",
        "-- 由 ccp2ccswitch.py 自动生成",
        "",
        "PRAGMA foreign_keys=OFF;",
        "BEGIN TRANSACTION;",
        "",
        "-- 创建表结构(如果不存在)",
        """CREATE TABLE IF NOT EXISTS mcp_servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                server_config TEXT NOT NULL,
                description TEXT,
                homepage TEXT,
                docs TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                enabled_claude BOOLEAN NOT NULL DEFAULT 0,
                enabled_codex BOOLEAN NOT NULL DEFAULT 0,
                enabled_gemini BOOLEAN NOT NULL DEFAULT 0
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS prompts (
                id TEXT NOT NULL,
                app_type TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT,
                enabled BOOLEAN NOT NULL DEFAULT 1,
                created_at INTEGER,
                updated_at INTEGER,
                PRIMARY KEY (id, app_type)
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS provider_endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT NOT NULL,
                app_type TEXT NOT NULL,
                url TEXT NOT NULL,
                added_at INTEGER,
                FOREIGN KEY (provider_id, app_type) REFERENCES providers(id, app_type) ON DELETE CASCADE
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS providers (
                id TEXT NOT NULL,
                app_type TEXT NOT NULL,
                name TEXT NOT NULL,
                settings_config TEXT NOT NULL,
                website_url TEXT,
                category TEXT,
                created_at INTEGER,
                sort_index INTEGER,
                notes TEXT,
                icon TEXT,
                icon_color TEXT,
                meta TEXT NOT NULL DEFAULT '{}',
                is_current BOOLEAN NOT NULL DEFAULT 0,
                PRIMARY KEY (id, app_type)
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS skill_repos (
                owner TEXT NOT NULL,
                name TEXT NOT NULL,
                branch TEXT NOT NULL DEFAULT 'main',
                enabled BOOLEAN NOT NULL DEFAULT 1,
                PRIMARY KEY (owner, name)
            );""",
        "",
        """CREATE TABLE IF NOT EXISTS skills (
                key TEXT PRIMARY KEY,
                installed BOOLEAN NOT NULL DEFAULT 0,
                installed_at INTEGER NOT NULL DEFAULT 0
            );""",
        "",
        "-- 清空 providers 表(避免主键冲突)",
        "DELETE FROM providers;",
        "",
        "-- 插入 providers 数据",
    ]

    # 转换每个 provider
    index = 1
    for provider in providers:
        is_current = (provider.get('name') == current_provider)
        sql = provider_to_sql(provider, is_current, index, add_prefix, global_env_models)
        sql_lines.append(sql)
        index += 1

    # 不再添加 skill_repos(用户可能已有配置)

    # SQL 尾部
    sql_lines.extend([
        "",
        "-- 插入 Claude Code 配置",
    ])

    # 构建 common_config_claude
    common_config = {
        "env": {},
        "includeCoAuthoredBy": False
    }

    # 添加全局 env-models 到 common_config
    if global_env_models:
        common_config["env"].update(global_env_models)

    # 转义并格式化 JSON
    common_config_json = json.dumps(common_config, ensure_ascii=False, indent=2)
    common_config_escaped = escape_sql_string(common_config_json)

    sql_lines.append(f"""INSERT INTO "settings" ("key", "value") VALUES ('common_config_claude', '{common_config_escaped}');""")

    sql_lines.extend([
        "",
        "COMMIT;",
        "PRAGMA foreign_keys=ON;",
        ""
    ])

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_lines))

    return len([p for p in providers if p.get('name') != 'Note'])


def main():
    parser = argparse.ArgumentParser(
        description='将 ccproxy 配置转换为 CC Switch SQL 格式或导出 Claude Code 配置',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换为 CC Switch SQL
  python ccp2ccswitch.py                                    # 使用默认文件
  python ccp2ccswitch.py --input config.json                # 指定输入文件
  python ccp2ccswitch.py --current "runanytime.hxi.me"      # 指定当前激活的供应商
  python ccp2ccswitch.py --output my-switch.sql             # 指定输出文件

  # 导出 Claude Code 配置
  python ccp2ccswitch.py --export-cc --provider "example-provider1" --output provider1.json
  python ccp2ccswitch.py --export-cc --current "example-provider1"  # 导出指定的供应商
        """
    )

    parser.add_argument('--input', '-i',
                        default='config.json',
                        help='输入的 JSON 配置文件（默认: config.json）')
    parser.add_argument('--output', '-o',
                        default=None,
                        help='输出文件（默认: SQL 模式为 cc-switch.sql，Claude Code 模式为 <provider-name>.json）')
    parser.add_argument('--current', '-c',
                        default=None,
                        help='当前激活的 provider 名称（默认: 第一个非 Note 的）')
    parser.add_argument('--prefix', '-p',
                        action='store_true',
                        help='在供应商名称前添加序号前缀(01-, 02-, ...)，使其按配置文件顺序排列')
    parser.add_argument('--export-cc', '--export-claudecode',
                        action='store_true',
                        help='导出 Claude Code 配置文件（JSON 格式）而不是 CC Switch SQL')
    parser.add_argument('--provider',
                        default=None,
                        help='[仅用于 --export-cc] 要导出的 provider 名称（默认: 使用 --current 或第一个）')

    args = parser.parse_args()

    # 读取配置文件
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 '{args.input}'")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: JSON 解析失败: {e}")
        sys.exit(1)

    providers = config.get('Providers', [])
    global_env_models = config.get('env-models', None)

    if args.export_cc:
        # Claude Code 配置导出模式
        provider_name = args.provider or args.current
        if not provider_name and len(providers) > 0:
            provider_name = providers[0].get('name')

        # 查找 provider
        target_provider = None
        for p in providers:
            if p.get('name') == provider_name:
                target_provider = p
                break

        if not target_provider:
            print(f"错误: 找不到 provider '{provider_name}'")
            sys.exit(1)

        # 确定输出文件名
        output_file = args.output
        if not output_file:
            safe_name = sanitize_id(provider_name)
            output_file = f"{safe_name}.json"

        print(f"正在读取配置文件: {args.input}")
        print(f"正在导出 Claude Code 配置: {provider_name}")

        config_data = export_claudecode_config(target_provider, output_file, global_env_models)

        print(f"✓ 成功导出 Claude Code 配置")
        print(f"✓ 配置文件已保存到: {output_file}")
        print(f"\n配置内容预览:")
        print(json.dumps(config_data, ensure_ascii=False, indent=2))

    else:
        # CC Switch SQL 导出模式
        output_file = args.output or 'cc-switch.sql'

        print(f"正在读取配置文件: {args.input}")
        count = generate_sql_file(config, output_file, args.current, args.prefix)
        print(f"✓ 成功转换 {count} 个 providers")
        print(f"✓ SQL 文件已保存到: {output_file}")

        if args.prefix:
            print(f"✓ 已添加序号前缀（01-, 02-, ...）")

        if args.current:
            print(f"✓ 当前激活的供应商: {args.current}")
        else:
            # 找出实际激活的供应商
            if len(providers) > 0:
                print(f"✓ 当前激活的供应商: {providers[0].get('name')} (默认)")


if __name__ == "__main__":
    main()
