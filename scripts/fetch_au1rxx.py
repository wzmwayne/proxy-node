#!/usr/bin/env python3
"""下载 au1rxx/free-vpn-subscriptions 的 clash.yaml 到 output/au1rxx/(原始内容,由 sanitize.py 清洗)。"""
import os

import requests

URL = "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/clash.yaml"
HEADERS = {"User-Agent": "proxy-node-bot/1.0"}


def main():
    out_dir = os.path.join("output", "au1rxx")
    os.makedirs(out_dir, exist_ok=True)
    print(f"  [GET] {URL}")
    resp = requests.get(URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    with open(os.path.join(out_dir, "clash.yaml"), "wb") as f:
        f.write(resp.content)
    print(f"  [OK] clash.yaml ({len(resp.content)} bytes)")


if __name__ == "__main__":
    main()
