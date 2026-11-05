#!/usr/bin/env python3
"""抓取"页面型来源"的最新订阅,写入 output/<来源>/clash.raw.yaml。

页面型来源的订阅地址按日期变化(nodetoolbox、jichangg 等),解析逻辑在
scripts/page_sources.py;下载流程与 fetch_sources.py 一致:先写 .raw.yaml,
只有清洗+mihomo 门禁通过后才会替换已发布的 clash.yaml。

用法:
  python scripts/scrape_page_sources.py                  # 抓取全部页面型来源
  python scripts/scrape_page_sources.py nodetoolbox      # 只抓指定来源
  python scripts/scrape_page_sources.py --dry-run        # 只解析、不下载
  python scripts/scrape_page_sources.py -v               # 打印解析细节
"""
import argparse
import os
import sys

import requests

from page_sources import HEADERS, PAGE_SOURCES, SourceUnavailable

RAW_NAME = "clash.raw.yaml"
TIMEOUT = 120


def download(url, dst):
    """下载订阅到 dst,返回字节数。"""
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.content
    if not content.strip():
        raise ValueError("返回内容为空")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.unlink(dst)
    with open(dst, "wb") as f:
        f.write(content)
    return len(content)


def main():
    ap = argparse.ArgumentParser(description="抓取页面型来源的最新订阅")
    ap.add_argument("sources", nargs="*", help=f"来源标识(可选: {', '.join(PAGE_SOURCES)})")
    ap.add_argument("--dry-run", action="store_true", help="只解析订阅地址,不下载")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印解析细节")
    args = ap.parse_args()

    names = args.sources or list(PAGE_SOURCES)
    unknown = [n for n in names if n not in PAGE_SOURCES]
    if unknown:
        raise SystemExit(f"[FAIL] 未知页面来源: {unknown} (可选: {', '.join(PAGE_SOURCES)})")

    ok, fail = 0, []
    for name in names:
        spec = PAGE_SOURCES[name]
        dst = os.path.join("output", name, RAW_NAME)
        print(f"  [解析] {name}: {spec['homepage']}")
        try:
            info = spec["discover"]()
        except SourceUnavailable as e:
            print(f"    [SKIP] {e}")
            # 解析不到就把上一轮原始文件清掉,避免把它当成本轮抓取结果
            if os.path.exists(dst):
                os.unlink(dst)
            fail.append(name)
            continue

        print(f"    -> 内容日期 {info.get('date')}")
        if args.verbose and info.get("detail"):
            print(f"    -> {info['detail']}")
        print(f"    -> {info['sub_url']}")
        if args.dry_run:
            ok += 1
            continue
        try:
            size = download(info["sub_url"], dst)
            print(f"    [OK] {size} bytes -> {dst}")
            ok += 1
        except Exception as e:  # noqa: BLE001 - 单个来源失败不影响其它来源
            print(f"    [FAIL] 下载失败: {e}")
            if os.path.exists(dst):
                os.unlink(dst)
            fail.append(name)

    print(f"页面来源抓取完成: 成功 {ok}, 失败 {len(fail)} {fail}")
    if fail:
        print("  (失败来源本次不更新,已发布的 clash.yaml 保持不变)")
    if names and ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
