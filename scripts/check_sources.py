#!/usr/bin/env python3
"""校验 output/ 目录与 sources.py 来源清单一致,防止再出现"孤儿来源目录"。

  * output/<name>/ 必须能在 SOURCES 里找到(只有 output/aio、output/aio-all 例外);
  * 每个来源都应有已发布的 clash.yaml,缺失只告警(v1 可自动重建)。

用法:
  python scripts/check_sources.py
"""
import os
import sys

from sources import SOURCES

ALLOWED_EXTRA = {"aio", "aio-all"}
OUTPUT = "output"


def main():
    if not os.path.isdir(OUTPUT):
        raise SystemExit(f"[FAIL] 找不到 {OUTPUT}/ 目录")
    dirs = sorted(d for d in os.listdir(OUTPUT) if os.path.isdir(os.path.join(OUTPUT, d)))

    orphans = [d for d in dirs if d not in SOURCES and d not in ALLOWED_EXTRA]
    unknown_src = []
    missing = []
    for name in SOURCES:
        p = os.path.join(OUTPUT, name, "clash.yaml")
        if not os.path.isfile(p):
            missing.append(name)

    print(f"来源目录 {len(dirs)} 个: {dirs}")
    print(f"sources.py 来源 {len(SOURCES)} 个: {sorted(SOURCES)}")
    if unknown_src:
        print(f"[WARN] 清单里没有对应抓取方式的来源: {unknown_src}")
    if missing:
        print(f"[WARN] 尚未发布 clash.yaml 的来源: {missing}")
    if orphans:
        print(f"[FAIL] 孤儿目录(不在 SOURCES 中): {orphans}")
        print("       请删除该目录,或在 sources.py 中登记来源。")
        return 1
    print("[OK] output/ 与来源清单一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
