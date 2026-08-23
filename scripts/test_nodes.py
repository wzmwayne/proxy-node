#!/usr/bin/env python3
"""用 Clash.Meta (mihomo) 内核逐节点测试可用性,合并生成 AIO 精选订阅。

用法:
  python scripts/test_nodes.py <cleaned1.yaml> [<cleaned2.yaml> ...] -o <out.yaml>

流程:
  1. 合并各来源清洗后的节点(按 type+server+port 去重);
  2. 生成临时测试配置并启动 mihomo 内核;
  3. 通过 RESTful API 对每个节点请求
     GET /proxies/{name}/delay?url=https://www.gstatic.com/generate_204
     测试代理可用性与延迟;
  4. 保留可用的节点,按延迟升序排序,注入说明节点,写出 AIO 精选订阅。

mihomo 二进制:环境变量 MIHOMO_BIN,否则自动探测 /usr/local/bin/mihomo、/tmp/mihomo。
"""
import argparse
import json
import os
import random
import socket
import string
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

TEST_URL = "https://www.gstatic.com/generate_204"
TIMEOUT_MS = 5000
GROUP_TYPES = {
    "Selector", "URLTest", "Fallback", "Relay", "LoadBalance", "Compatible",
    "Pass", "ShadowTLS", "Reject", "Direct",
}
SKIP_NAMES = {"GLOBAL", "DIRECT", "REJECT", "PASS"}
AUTHOR = "wzmwayne"
REPO = "https://github.com/wzmwayne/proxy-node"


def find_free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def api_get(port, secret, path):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    req.add_header("Authorization", f"Bearer {secret}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def test_node(port, secret, name):
    q = urllib.parse.quote(name, safe="")
    url_q = urllib.parse.quote(TEST_URL, safe="")
    try:
        data = api_get(port, secret, f"/proxies/{q}/delay?timeout={TIMEOUT_MS}&url={url_q}")
        return name, data.get("delay")
    except Exception:
        return name, None


def fake_proxy(name):
    return {
        "name": name,
        "type": "trojan",
        "server": "127.0.0.1",
        "port": 443,
        "password": "dummy",
        "udp": True,
        "skip-cert-verify": True,
    }


def find_mihomo():
    for p in [os.environ.get("MIHOMO_BIN"), "/usr/local/bin/mihomo", "/tmp/mihomo", "mihomo"]:
        if p and os.path.isfile(p):
            return p
    raise SystemExit("[FAIL] 未找到 mihomo 内核(设置 MIHOMO_BIN 或安装到 /usr/local/bin/mihomo)")


def main():
    ap = argparse.ArgumentParser(description="mihomo 内核节点测试 + AIO 合并")
    ap.add_argument("inputs", nargs="+", help="清洗后的各来源 clash.yaml")
    ap.add_argument("-o", "--output", required=True, help="输出 AIO clash.yaml")
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()

    import yaml

    # 1) 合并各来源节点(去重)
    merged = {}
    for inp in args.inputs:
        with open(inp, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        for p in d.get("proxies", []):
            if not isinstance(p, dict) or not p.get("name"):
                continue
            if str(p["name"]).startswith("说明-"):
                continue
            key = (p.get("type"), p.get("server"), p.get("port"))
            if key not in merged:
                merged[key] = p
    proxies = list(merged.values())
    print(f"[1/4] 合并后待测节点: {len(proxies)}")
    if not proxies:
        raise SystemExit("[FAIL] 无任何节点可测")

    # 2) 启动 mihomo 内核
    mihomo = find_mihomo()
    port = find_free_port()
    secret = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    test_cfg = {
        "mixed-port": port + 1,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "silent",
        "external-controller": f"127.0.0.1:{port}",
        "secret": secret,
        "proxies": proxies,
        "rules": ["MATCH,DIRECT"],
    }
    print(f"[2/4] 启动 mihomo (external-controller 127.0.0.1:{port})")
    with tempfile.TemporaryDirectory() as td:
        cfg_path = os.path.join(td, "config.yaml")
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(test_cfg, f, allow_unicode=False, sort_keys=False)
        proc = subprocess.Popen(
            [mihomo, "-d", td, "-f", cfg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ready = False
            for _ in range(120):
                try:
                    api_get(port, secret, "/version")
                    ready = True
                    break
                except Exception:
                    if proc.poll() is not None:
                        raise SystemExit("[FAIL] mihomo 进程提前退出")
                    time.sleep(0.5)
            if not ready:
                raise SystemExit("[FAIL] mihomo API 未就绪")

            # 3) 逐节点测试 generate_204
            proxies_map = api_get(port, secret, "/proxies")["proxies"]
            names = [
                n for n, info in proxies_map.items()
                if n not in SKIP_NAMES and info.get("type") not in GROUP_TYPES
            ]
            print(f"[3/4] 开始测试 {len(names)} 个节点 -> {TEST_URL}")
            ok = {}
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                futs = {ex.submit(test_node, port, secret, n): n for n in names}
                done = 0
                for fut in as_completed(futs):
                    name, delay = fut.result()
                    done += 1
                    if delay is not None:
                        ok[name] = delay
                    if done % 200 == 0 or done == len(names):
                        print(f"      进度 {done}/{len(names)}, 可用 {len(ok)}")
            print(f"      可用节点: {len(ok)}")
            if not ok:
                raise SystemExit("[FAIL] 全部节点测试失败(检查网络/节点质量),不生成 AIO")

            # 4) 生成 AIO:可用节点按延迟排序 + 说明节点 + 分组
            good = [p for p in proxies if p["name"] in ok]
            good.sort(key=lambda p: ok[p["name"]])
            good_names = [p["name"] for p in good]
            now = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 8 * 3600))
            fake_names = [
                f"说明-来源: AIO 精选(合并 {len(args.inputs)} 个来源)",
                f"说明-测试: {len(ok)}/{len(names)} 节点通过 generate_204",
                f"说明-更新时间: {now} (CST)",
                f"说明-作者: {AUTHOR}",
                f"说明-仓库: {REPO}",
            ]
            fakes = [fake_proxy(n) for n in fake_names]
            aio = {
                "mixed-port": 7890,
                "allow-lan": False,
                "mode": "rule",
                "log-level": "info",
                "ipv6": False,
                "external-controller": "127.0.0.1:9090",
                "proxies": fakes + good,
                "proxy-groups": [
                    {"name": "说明", "type": "select", "proxies": fake_names},
                    {"name": "🚀 节点选择", "type": "select", "proxies": good_names},
                    {
                        "name": "♻️ 自动选择",
                        "type": "url-test",
                        "url": TEST_URL,
                        "interval": 300,
                        "proxies": good_names,
                    },
                ],
                "rules": ["MATCH,🚀 节点选择"],
            }
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                yaml.safe_dump(aio, f, allow_unicode=False, default_flow_style=False, sort_keys=False)
            print(f"[4/4] AIO 已写入 {args.output}: {len(good)} 个可用节点")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
