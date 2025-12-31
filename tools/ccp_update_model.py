#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 ccproxy config.json 中的模型列表
使用 OpenAI SDK 获取每个提供商支持的模型列表，更新 models 字段
用法: python ccp_update_model.py [--input config.json] [--output config.json] [--timeout 30] [--filter "4-5,sonnet"]
"""

import json
import sys
import argparse
import requests
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def get_models_from_provider(base_url, api_key, timeout=30.0):
    """
    先用 requests 获取模型列表，失败或为空时用 OpenAI SDK 重试
    """
    import time
    start_time = time.time()

    # 先尝试 requests
    try:
        headers = {'Authorization': f'Bearer {api_key}'}
        r = requests.get(f"{base_url}/v1/models", headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        models = [m['id'] for m in data.get('data', [])]
        if models:
            return models, None, time.time() - start_time
    except Exception:
        pass

    # requests 失败或为空，用 OpenAI SDK 重试
    try:
        client = OpenAI(
            base_url=f"{base_url}/v1",
            api_key=api_key,
            timeout=timeout
        )
        models_response = client.models.list()
        models = [model.id for model in models_response.data]
        return models, None, time.time() - start_time
    except Exception as e:
        error_msg = str(e)
        if '<html' in error_msg.lower() or '<!doctype' in error_msg.lower():
            error_msg = "API 返回 HTML 错误页面(可能是认证失败或 URL 错误)"
        elif len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        return None, error_msg, 0


def process_provider(idx, total, provider, timeout):
    """处理单个提供商"""
    name = provider['name']

    # 跳过 Note 类型的 provider
    if name == 'Note':
        return (idx, name, 0, None, 0, None, True)

    api_base_url = provider['api_base_url']
    api_key = provider['api_key']

    base_url = extract_base_url(api_base_url)
    models, error, elapsed = get_models_from_provider(base_url, api_key, timeout)

    if models is not None:
        if len(models) > 0:
            provider['models'] = models
        # 如果返回 0 个模型，保留原有模型列表不变
        return (idx, name, len(provider.get('models', [])), None, elapsed, None, False)
    else:
        # 失败时在模型列表前面添加错误标记
        error_msg = error or '未知错误'
        # 简化错误信息
        if 'HTML' in error_msg:
            error_tag = '[错误:HTML响应]'
        elif 'timed out' in error_msg or 'timeout' in error_msg.lower():
            error_tag = '[错误:超时]'
        elif 'blocked' in error_msg.lower():
            error_tag = '[错误:被拦截]'
        elif '401' in error_msg or '认证' in error_msg or '令牌' in error_msg:
            error_tag = '[错误:认证失败]'
        elif '402' in error_msg:
            error_tag = '[错误:余额不足]'
        else:
            error_tag = '[错误:获取失败]'

        old_models = provider.get('models', [])
        provider['models'] = [error_tag] + old_models
        return (idx, name, len(provider['models']), error_msg, elapsed, f"{base_url}/v1/models", False)


def main():
    parser = argparse.ArgumentParser(
        description='更新 ccproxy config.json 的模型列表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ccp_update_model.py                                 # 使用默认文件
  python ccp_update_model.py --timeout 5                     # 设置超时 5 秒
  python ccp_update_model.py --filter "4-5,sonnet"           # 筛选包含关键词的模型
  python ccp_update_model.py --input config.json --output config.json
        """
    )

    parser.add_argument('--input', '-i',
                        default='config.json',
                        help='输入的 JSON 配置文件(默认: config.json)')
    parser.add_argument('--output', '-o',
                        default='config.json',
                        help='输出的 JSON 文件(默认: config.json)')
    parser.add_argument('--timeout', '-t',
                        type=float,
                        default=30.0,
                        help='API 请求超时时间(秒)，默认 30 秒')
    parser.add_argument('--filter', '-f',
                        type=str,
                        default='',
                        help='模型筛选关键词，逗号分隔，如 "4-5,sonnet"')

    args = parser.parse_args()

    # 读取原始配置文件
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
    total = len(providers)
    print(f"共有 {total} 个提供商需要更新(超时: {args.timeout}s)\n")

    # 并发处理所有提供商
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_provider, idx, total, provider, args.timeout)
            for idx, provider in enumerate(providers, 1)
        ]

        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                pass

    # 找出最快的三个成功的 provider
    success_results = [(idx, name, count, elapsed) for idx, name, count, error, elapsed, url, is_note in results if not error and not is_note]
    success_results.sort(key=lambda x: x[3])  # 按时间排序
    fastest_names = {name for _, name, _, _ in success_results[:3]}

    # 按索引排序并输出结果
    results.sort(key=lambda x: x[0])
    for idx, name, count, error, elapsed, url, is_note in results:
        if is_note:
            continue
        if error:
            print(f"[{idx}/{total}] [FAIL] {name}: {error}")
            print(f"           URL: {url}")
        else:
            slow_mark = " [SLOW]" if elapsed > 15 else ""
            fast_mark = " ***" if name in fastest_names else ""
            print(f"[{idx}/{total}] [OK] {name}: {count} 个模型 ({elapsed:.1f}s){slow_mark}{fast_mark}")

    # 筛选模型
    if args.filter:
        keywords = [k.strip().lower() for k in args.filter.split(',') if k.strip()]
        print(f"\n筛选模型关键词: {', '.join(keywords)}")
        for p in providers:
            if p.get('name') == 'Note':
                continue
            models = p.get('models', [])
            filtered = [m for m in models if any(k in m.lower() for k in keywords)]
            if filtered:
                p['models'] = filtered

    # 保存到输出文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✓ 处理完成！结果已保存到 {args.output}")
    if args.filter:
        print(f"✓ 已应用模型筛选: {args.filter}")


if __name__ == "__main__":
    main()
