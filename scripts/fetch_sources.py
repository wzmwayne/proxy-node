#!/usr/bin/env python3
"""下载各来源的 clash.yaml 到 output/<source>/clash.yaml(原始内容,由 sanitize.py 清洗)。

用法:
  python scripts/fetch_sources.py            # 下载全部来源(不含 yoyapai,由 scraper.py 抓取)
  python scripts/fetch_sources.py au1rxx     # 只下载指定来源
"""
import os
import sys

import requests

from sources import FETCH_URLS

HEADERS = {"User-Agent": "proxy-node-bot/1.0"}


def main():
    names = sys.argv[1:] if len(sys.argv) > 1 else list(FETCH_URLS)
    ok, fail = 0, []
    for name in names:
        url = FETCH_URLS[name]
        out_dir = os.path.join("output", name)
        os.makedirs(out_dir, exist_ok=True)
        try:
            print(f"  [GET] {name}: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=120)
            resp.raise_for_status()
            with open(os.path.join(out_dir, "clash.yaml"), "wb") as f:
                f.write(resp.content)
            print(f"  [OK] {name} ({len(resp.content)} bytes)")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            fail.append(name)
    print(f"下载完成: 成功 {ok}, 失败 {len(fail)} {fail}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
