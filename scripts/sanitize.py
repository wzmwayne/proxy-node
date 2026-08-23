#!/usr/bin/env python3
"""清洗 Clash 订阅 YAML 中的控制字符等致命错误,保证输出可被 Clash.Meta (go-yaml v3) 解析。

用法:
  python sanitize.py <in.yaml> <out.yaml>

背景:
  go-yaml v3 的读取器只接受白名单码点(U+0009/000A/000D、0x20-0x7E、0x85、
  0xA0-0xD7FF、0xE000-0xFFFD、0x10000-0x10FFFF),遇到真实控制字符
  (C0: 0x00-0x08/0x0B/0x0C/0x0E-0x1F、DEL 0x7F、C1: 0x80-0x84/0x86-0x9F)
  直接报 "yaml: control characters are not allowed"。
  部分订阅源把损坏的 UTF-8 字节写成 "\x9F" 之类的转义,解析后变成真实控制
  字符 —— 仅靠字节扫描发现不了,必须在解码后的值层面检查。
"""
import argparse
import sys

SOURCES = {
    "yoyapai": ("yoyapai.com", "https://yoyapai.com/category/mianfeijiedian"),
    "au1rxx": (
        "Au1rxx/free-vpn-subscriptions",
        "https://github.com/Au1rxx/free-vpn-subscriptions",
    ),
}
AUTHOR = "wzmwayne"
REPO = "https://github.com/wzmwayne/proxy-node"


def beijing_now():
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def count_non_ascii(node):
    """统计结构中所有字符串值的非 ASCII 字符数(即会被转译的字符数)。"""
    if isinstance(node, str):
        return sum(1 for c in node if ord(c) > 0x7E)
    if isinstance(node, dict):
        return sum(count_non_ascii(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_non_ascii(v) for v in node)
    return 0


def fake_proxy(name):
    """构造一个承载说明信息的假节点(无法实际使用,仅用于展示说明)。"""
    return {
        "name": name,
        "type": "trojan",
        "server": "127.0.0.1",
        "port": 443,
        "password": "dummy",
        "udp": True,
        "skip-cert-verify": True,
    }


def inject_fake_nodes(data, source_label, dropped_count, escaped_chars, time_str):
    """注入一组"说明-"假节点与"说明"分组,承载来源/清洗结果/时间/作者/仓库。"""
    names = [
        f"说明-来源: {source_label}",
        f"说明-清洗结果: 清理 {dropped_count} 个节点、转译 {escaped_chars} 个字符",
        f"说明-更新时间: {time_str} (CST)",
        f"说明-作者: {AUTHOR}",
        f"说明-仓库: {REPO}",
    ]
    # 重跑安全:先移除旧的"说明-"节点与"说明"分组
    proxies = data.get("proxies")
    if isinstance(proxies, list):
        data["proxies"] = [
            p
            for p in proxies
            if not (isinstance(p, dict) and str(p.get("name", "")).startswith("说明-"))
        ] + [fake_proxy(n) for n in names]

    groups = data.get("proxy-groups")
    if isinstance(groups, list):
        cleaned_groups = [
            g for g in groups if not (isinstance(g, dict) and g.get("name") == "说明")
        ]
        # "说明"分组放在最前,便于客户端展示时优先可见
        data["proxy-groups"] = [{"name": "说明", "type": "select", "proxies": names}] + cleaned_groups


def is_allowed(cp: int) -> bool:
    """go-yaml v3 允许的码点白名单(yaml.v3 readerc.go 的检查逻辑)。"""
    return (
        cp in (0x09, 0x0A, 0x0D)
        or 0x20 <= cp <= 0x7E
        or cp == 0x85
        or 0xA0 <= cp <= 0xD7FF
        or 0xE000 <= cp <= 0xFFFD
        or 0x10000 <= cp <= 0x10FFFF
    )


def find_bad_codepoints(text: str):
    """返回文本中所有非法码点(去重)。"""
    return sorted({ord(c) for c in text if not is_allowed(ord(c))})


def check_values(node, path=""):
    """递归检查结构中的所有字符串值,返回违规位置列表 [(path, codepoints)]。"""
    violations = []
    if isinstance(node, dict):
        for k, v in node.items():
            child = f"{path}.{k}" if path else str(k)
            if isinstance(v, str):
                bad = find_bad_codepoints(v)
                if bad:
                    violations.append((child, bad))
            else:
                violations.extend(check_values(v, child))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            child = f"{path}[{i}]"
            if isinstance(v, str):
                bad = find_bad_codepoints(v)
                if bad:
                    violations.append((child, bad))
            else:
                violations.extend(check_values(v, child))
    return violations


def deep_clean(node, removed=None):
    """递归剔除结构中的违规字符串:dict 删键、list 剔除元素,返回清理后的结构。"""
    if removed is None:
        removed = []
    if isinstance(node, dict):
        result = {}
        for k, v in node.items():
            if isinstance(v, str):
                if find_bad_codepoints(v):
                    removed.append(str(k))
                    continue
                result[k] = v
            else:
                result[k] = deep_clean(v, removed)
        return result
    if isinstance(node, list):
        result = []
        for v in node:
            if isinstance(v, str):
                if find_bad_codepoints(v):
                    removed.append(v[:40])
                    continue
                result.append(v)
            else:
                result.append(deep_clean(v, removed))
        return result
    return node


def clean_yaml(src, dst, source):
    import yaml

    if source not in SOURCES:
        raise SystemExit(f"[FAIL] 未知来源: {source} (可选: {', '.join(SOURCES)})")
    source_label, source_url = SOURCES[source]

    raw = open(src, "rb").read()
    try:
        data = yaml.safe_load(raw)
    except Exception as e:
        raise SystemExit(f"[FAIL] {src} YAML 解析失败: {e}") from e
    if data is None:
        raise SystemExit(f"[FAIL] {src} 解析结果为空")

    if not isinstance(data, dict):
        raise SystemExit(f"[FAIL] {src} 顶层不是映射")

    dropped_nodes = []
    dropped_groups = []
    dropped_rules = 0
    dropped_other = []

    # 1) 清洗 proxies:任一字段含非法码点则丢弃整个节点
    if isinstance(data.get("proxies"), list):
        cleaned = []
        for p in data["proxies"]:
            if not isinstance(p, dict):
                continue
            bad = [k for k, v in p.items() if isinstance(v, str) and find_bad_codepoints(v)]
            if bad:
                dropped_nodes.append((p.get("name", "?"), bad))
                continue
            cleaned.append(p)
        data["proxies"] = cleaned

    dropped_names = {name for name, _ in dropped_nodes}

    # 2) 清洗 proxy-groups:剔除引用已删节点的项;组字段含非法码点则丢组
    if isinstance(data.get("proxy-groups"), list):
        cleaned = []
        for g in data["proxy-groups"]:
            if not isinstance(g, dict):
                continue
            bad = [k for k, v in g.items() if isinstance(v, str) and find_bad_codepoints(v)]
            if bad:
                dropped_groups.append((g.get("name", "?"), bad))
                continue
            refs = g.get("proxies")
            if isinstance(refs, list):
                g["proxies"] = [r for r in refs if r not in dropped_names]
            cleaned.append(g)
        data["proxy-groups"] = cleaned

    # 3) 清洗 rules:剔除含非法码点的行
    if isinstance(data.get("rules"), list):
        cleaned = [r for r in data["rules"] if not (isinstance(r, str) and find_bad_codepoints(r))]
        dropped_rules = len(data["rules"]) - len(cleaned)
        data["rules"] = cleaned

    # 4) 清洗其余顶层字段:嵌套结构中的违规字符串一律剔除
    for k, v in list(data.items()):
        if k in ("proxies", "proxy-groups", "rules"):
            continue
        if isinstance(v, str) and find_bad_codepoints(v):
            dropped_other.append((k, find_bad_codepoints(v)))
            del data[k]
        else:
            removed = []
            data[k] = deep_clean(v, removed)
            if removed:
                dropped_other.append((k, removed[:5]))

    # 5) 统计清洗结果,注入"说明-"假节点与"说明"分组
    dropped_count = len(dropped_nodes)
    escaped_chars = count_non_ascii(data)
    inject_fake_nodes(data, source_label, dropped_count, escaped_chars, beijing_now())

    # 6) 输出为纯 ASCII YAML(非 ASCII 全部转义,控制字符绝不会出现在字节里)
    out = yaml.safe_dump(
        data,
        allow_unicode=False,
        default_flow_style=False,
        sort_keys=False,
    ).encode("utf-8")

    # 7) 二次校验:重新解析输出,值层面必须零违规
    recheck = yaml.safe_load(out)
    violations = check_values(recheck)
    if violations:
        raise SystemExit(
            f"[FAIL] {dst} 清洗后仍含非法码点: {violations[:5]}"
        )

    with open(dst, "wb") as f:
        f.write(out)

    total = dropped_count + len(dropped_groups) + dropped_rules + len(dropped_other)
    print(f"[OK] {src} -> {dst} (来源: {source_label})")
    print(f"     节点: 丢弃 {dropped_count} 个: {[n for n, _ in dropped_nodes][:5]}")
    if dropped_groups:
        print(f"     分组: 丢弃 {len(dropped_groups)} 个")
    if dropped_rules:
        print(f"     rules: 剔除 {dropped_rules} 条")
    if dropped_other:
        print(f"     其他: 剔除 {len(dropped_other)} 项: {dropped_other[:5]}")
    print(f"     转译非 ASCII 字符: {escaped_chars} 个")
    if total == 0:
        print("     无需清洗,已原样重编码")


def main():
    ap = argparse.ArgumentParser(description="清洗 Clash 订阅 YAML 中的控制字符并注入说明节点")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--source", required=True, choices=list(SOURCES), help="订阅来源标识")
    args = ap.parse_args()
    clean_yaml(args.src, args.dst, args.source)


if __name__ == "__main__":
    main()
