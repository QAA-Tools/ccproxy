#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 ccproxy 的 config.json 转换为 CLIProxyAPI 的 openai-compatibility 格式
用法: python ccp2cliproxy.py [--input config.json] [--output cliproxy.yaml]
"""

import json
import sys
import argparse
from datetime import datetime

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def provider_to_cliproxy(provider):
    """
    将单个 ccproxy provider 转换为 CLIProxyAPI openai-compatibility 格式

    Args:
        provider: ccproxy 的 provider 对象

    Returns:
        dict: CLIProxyAPI openai-compatibility 格式的配置
    """
    # 提取字段
    name = provider.get('name', 'Unknown')
    api_base_url = provider.get('api_base_url', '')
    api_key = provider.get('api_key', '')
    models = provider.get('models', [])

    # 提取基础 URL - 移除常见的端点路径
    base_url = api_base_url
    for endpoint in ["/anthropic/v1/messages", "/v1/chat/completions", "/v1/messages", "/v1"]:
        if endpoint in base_url:
            base_url = base_url.replace(endpoint, "")
            break

    # 构建 CLIProxyAPI 格式
    cliproxy_provider = {
        'name': name,
        'base-url': base_url,
        'api-key-entries': [
            {'api-key': api_key}
        ]
    }

    # 添加模型列表
    if models:
        cliproxy_provider['models'] = [
            {'name': model, 'alias': ''} for model in models
        ]

    return cliproxy_provider


def generate_yaml_file(config, output_file):
    """
    生成 CLIProxyAPI YAML 配置文件

    Args:
        config: ccproxy 配置对象
        output_file: 输出文件路径
    """
    providers = config.get('Providers', [])

    # 转换所有 providers
    cliproxy_providers = []
    for provider in providers:
        # 跳过 Note 类型的 provider
        if provider.get('name') == 'Note':
            continue
        cliproxy_provider = provider_to_cliproxy(provider)
        cliproxy_providers.append(cliproxy_provider)

    # 手动构建 YAML 格式(保持简洁的格式)
    yaml_lines = [
        "# CLIProxyAPI 配置文件",
        f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# 由 ccp2cliproxy.py 自动生成",
        "",
        "openai-compatibility:",
    ]

    # 写入每个 provider
    for provider in cliproxy_providers:
        yaml_lines.append(f"  - name: {provider['name']}")
        yaml_lines.append(f"    base-url: {provider['base-url']}")
        yaml_lines.append("    api-key-entries:")
        for entry in provider['api-key-entries']:
            yaml_lines.append(f"      - api-key: {entry['api-key']}")

        # 如果有模型列表
        if 'models' in provider and provider['models']:
            yaml_lines.append("    models:")
            for model in provider['models']:
                yaml_lines.append(f"      - name: {model['name']}")
                yaml_lines.append(f"        alias: \"{model['alias']}\"")

        # 添加空行分隔不同的 provider
        yaml_lines.append("")

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(yaml_lines))

    return len(cliproxy_providers)


def main():
    parser = argparse.ArgumentParser(
        description='将 ccproxy 配置转换为 CLIProxyAPI openai-compatibility 格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ccp2cliproxy.py                          # 使用默认文件
  python ccp2cliproxy.py --input config.json      # 指定输入文件
  python ccp2cliproxy.py --output my-config.yaml  # 指定输出文件
        """
    )

    parser.add_argument('--input', '-i',
                        default='config.json',
                        help='输入的 JSON 配置文件（默认: config.json）')
    parser.add_argument('--output', '-o',
                        default='cliproxy.yaml',
                        help='输出的 YAML 文件（默认: cliproxy.yaml）')

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

    # 生成 YAML
    print(f"正在读取配置文件: {args.input}")
    count = generate_yaml_file(config, args.output)
    print(f"✓ 成功转换 {count} 个供应商")
    print(f"✓ YAML 文件已保存到: {args.output}")


if __name__ == "__main__":
    main()
