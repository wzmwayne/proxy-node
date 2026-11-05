#!/usr/bin/env python3
"""用 Clash.Meta (mihomo) 内核测试节点可达性与下载速度,合并生成 AIO 精选订阅。

用法:
  python scripts/test_nodes.py <cleaned1.yaml> [<cleaned2.yaml> ...] -o output/aio/clash.yaml

流程:
  1. 合并各来源清洗后的节点(按完整配置去重,忽略节点名);
  2. 启动 mihomo 内核(仅含待测节点 + MATCH,DIRECT);
  3. 可达性:通过 RESTful API 请求
     GET /proxies/{name}/delay?url=https://www.gstatic.com/generate_204
     丢弃不可用节点,保留延迟;
  4. 测速:对可达节点启动一批"出口绑定"监听器(listeners + proxy: 节点名),
     并发下载 20MB 测试文件,实测每个节点的 MB/s;
  5. 汇总:节点名统一加 "[x.xMB/s]" 标注,按 高速 -> 延迟 排序,生成
     "⚡ 高速节点(>阈值)" 独立分组 + 节点选择 + 自动选择;
  6. 注入说明节点,写出 AIO 精选订阅。

mihomo 二进制:环境变量 MIHOMO_BIN,否则自动探测 /usr/local/bin/mihomo、/tmp/mihomo、PATH。
"""
import argparse
import hashlib
import json
import os
import random
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from sanitize import SafeDumper, fake_proxy
from sources import SOURCES

TEST_URL = "https://www.gstatic.com/generate_204"

# 测速文件候选(按顺序探测直连可达性):
#   1. 本仓库 release:test 的 20MB 测速文件(CI 由 ensure_speedtest_asset.sh 保证存在)
#   2. Cloudflare 20MB 下载端点
# 两个文件都测,按权重(CF 0.6 / release 0.4)加权平均作为节点最终速度。
RELEASE_SPEED_URL = (
    "https://github.com/wzmwayne/proxy-node/releases/download/test/speedtest-20mb.bin"
)
SPEED_BYTES = 20_000_000


def default_speed_urls():
    return [
        RELEASE_SPEED_URL,
        f"https://speed.cloudflare.com/__down?bytes={SPEED_BYTES}",
    ]


SPEED_UA = "proxy-node-bot/1.0 (speedtest)"

# 多测速文件加权平均的默认权重(Cloudflare 权重更高,缺失的目标按剩余权重归一化)
SPEED_WEIGHTS = {"cloudflare": 0.6, "release": 0.4, "other": 0.5}


def weighted_rate(rates, weights=None):
    """按权重算加权平均速度(即节点最终速度);缺失的目标按剩余权重归一化。"""
    w = dict(SPEED_WEIGHTS if weights is None else weights)
    num = den = 0.0
    for tag, rate in rates.items():
        weight = float(w.get(tag, w.get("other", 0.5)))
        num += weight * rate
        den += weight
    return (num / den) if den > 0 else None

GROUP_TYPES = {
    "Selector", "URLTest", "Fallback", "Relay", "LoadBalance", "Compatible",
    "Pass", "ShadowTLS", "Reject", "Direct",
}
SKIP_NAMES = {"GLOBAL", "DIRECT", "REJECT", "PASS"}
AUTHOR = "wzmwayne"
REPO = "https://github.com/wzmwayne/proxy-node"

# AIO 节点名标注:重新生成时可重复运行(先剥掉旧标注)
ANNOTATION_RE = None


def _annotation_re():
    import re

    global ANNOTATION_RE
    if ANNOTATION_RE is None:
        ANNOTATION_RE = re.compile(r"^\[(?:\d+(?:\.\d+)?\s*MB/s|测速失败|未测速)\]\s+")
    return ANNOTATION_RE


def strip_annotation(name: str) -> str:
    return _annotation_re().sub("", str(name), count=1)


def find_free_ports(n):
    """一次性申请 n 个空闲端口(先全部占用再统一释放,尽量避免重复)。"""
    socks, ports = [], []
    for _ in range(n):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        socks.append(s)
        ports.append(s.getsockname()[1])
    for s in socks:
        s.close()
    return ports


def find_mihomo(explicit=None):
    cands = [explicit, os.environ.get("MIHOMO_BIN"), "/usr/local/bin/mihomo", "/tmp/mihomo"]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    which = shutil.which("mihomo")
    if which:
        return which
    raise SystemExit("[FAIL] 未找到 mihomo 内核(设置 MIHOMO_BIN 或用 --mihomo 指定)")


def api_get(port, secret, path, timeout=10):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    req.add_header("Authorization", f"Bearer {secret}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


class Core:
    """一个 mihomo 测试内核进程。"""

    def __init__(self, mihomo, proxies, rules, listeners=None, keep_dir=False):
        self.mihomo = mihomo
        self.proxies = proxies
        self.rules = rules
        self.listeners = listeners or []
        self.secret = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        self.ctrl_port = find_free_ports(1)[0]
        self.td = tempfile.mkdtemp(prefix="pnode-")
        self.keep_dir = keep_dir
        self.proc = None

    @staticmethod
    def port_open(port, timeout=0.5):
        s = socket.socket()
        s.settimeout(timeout)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()

    def start(self, wait=60.0, wait_ports=None):
        cfg = {
            "mixed-port": find_free_ports(1)[0],
            "allow-lan": False,
            "mode": "rule",
            "log-level": "silent",
            "external-controller": f"127.0.0.1:{self.ctrl_port}",
            "secret": self.secret,
            "proxies": self.proxies,
            "rules": self.rules,
        }
        if self.listeners:
            cfg["listeners"] = self.listeners
        cfg_path = os.path.join(self.td, "config.yaml")
        import yaml

        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, Dumper=SafeDumper, allow_unicode=False, sort_keys=False)
        self.proc = subprocess.Popen(
            [self.mihomo, "-d", self.td, "-f", cfg_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + wait
        ready = False
        while time.monotonic() < deadline:
            try:
                api_get(self.ctrl_port, self.secret, "/version", timeout=3)
                ready = True
                break
            except Exception:
                if self.proc.poll() is not None:
                    raise SystemExit("[FAIL] mihomo 进程提前退出(配置无法加载?)")
                time.sleep(0.2)
        if not ready:
            self.stop()
            raise SystemExit("[FAIL] mihomo API 未就绪")
        # API 就绪 ≠ listener 已绑定(实测相差约 0.2s),等端口真正可连再返回
        if wait_ports:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if all(self.port_open(p) for p in wait_ports):
                    break
                time.sleep(0.1)
        return self

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if not self.keep_dir:
            shutil.rmtree(self.td, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def test_delay(port, secret, name, timeout_ms=5000):
    q = urllib.parse.quote(name, safe="")
    url_q = urllib.parse.quote(TEST_URL, safe="")
    try:
        data = api_get(port, secret, f"/proxies/{q}/delay?timeout={timeout_ms}&url={url_q}")
        return name, data.get("delay")
    except Exception:
        return name, None


def probe_direct(url, timeout=15):
    """探测测试文件能否从 runner 直连下载(避免内核/节点背锅)。"""
    req = urllib.request.Request(url, headers={"User-Agent": SPEED_UA, "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(65536)
        return True
    except Exception:
        return False


def pick_speed_urls(candidates, timeout=15):
    """返回所有直连可达的测速文件(自建 release 文件 + Cloudflare 等都测)。"""
    return [u for u in candidates if probe_direct(u, timeout=timeout)]


def measure_speed(port, url, max_bytes, timeout, early_bytes, early_rate,
                  min_bytes=1_000_000, min_window=0.2):
    """经 127.0.0.1:port 下载 url,返回 (MB/s, 字节数, 秒数, 失败原因)。

    只有"读到 >= min_bytes"或"确实读满 timeout 仍在传"才算有效速度;
    代理截断响应(字节数很小、耗时极短)一律判失败,避免出现虚假高速度。
    提前结束还需要至少 min_window 秒的采样窗口,避免把瞬时突发当成持续速度。
    HTTP 429(Cloudflare 限速)重试一次。
    """
    min_valid = min(min_bytes, max_bytes)
    err = None
    for attempt in (1, 2):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({
            "http": f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }))
        req = urllib.request.Request(url, headers={"User-Agent": SPEED_UA,
                                                   "Accept-Encoding": "identity"})
        total, t0, t_first = 0, time.monotonic(), None
        try:
            with opener.open(req, timeout=timeout) as r:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    now = time.monotonic()
                    if t_first is None:
                        t_first = now
                    raw_el = now - t_first          # 真实采样窗口(不含建连)
                    el = max(raw_el, 0.3)           # 速率估算下限,避免分母过小
                    if total >= max_bytes:
                        break
                    if (total >= early_bytes and raw_el >= min_window
                            and total / el / 1e6 >= early_rate):
                        break  # 采样窗口足够且明显超过阈值,提前结束省流量
                    if now - t0 >= timeout:
                        break
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code == 429 and attempt == 1:
                time.sleep(1.0)
                continue
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:120]

        elapsed = time.monotonic() - t0
        if total == 0:
            return 0.0, 0, elapsed, err or "no data"
        el = time.monotonic() - (t_first or t0)
        if total < min_valid:
            if elapsed < timeout * 0.9:
                # 很快结束却只有一点点数据 = 响应被代理/CDN 截断,不能算速度
                return 0.0, total, el, (f"传输被截断({total/1e6:.2f}MB/{elapsed:.1f}s)"
                                        + (f" {err}" if err else ""))
            # 数据量不足且耗时很长 = 链路很慢:按整段耗时(含建连)保守计算,
            # 否则"慢握手 + 小响应体"会被算成虚假高速度
            return total / max(elapsed, 0.001) / 1e6, total, elapsed, err or "数据量不足"
        return total / max(el, 0.001) / 1e6, total, el, err
    return 0.0, 0, 0.0, err


def probe_latency(port, url, timeout=5.0):
    """经 127.0.0.1:port 请求 url,返回毫秒延迟(失败返回 None)。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({
        "http": f"http://127.0.0.1:{port}",
        "https": f"http://127.0.0.1:{port}",
    }))
    req = urllib.request.Request(url, headers={"User-Agent": SPEED_UA})
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as r:
            r.read(64)
        return (time.monotonic() - t0) * 1000
    except Exception:
        return None


def measure_node(port, urls, args, weights=None):
    """先测延时再测速:返回 (加权平均 MB/s, {文件: MB/s}, 明细, 延时 ms)。"""
    lat = probe_latency(port, TEST_URL, getattr(args, "speed_latency_timeout", 5.0))
    if lat is None and getattr(args, "speed_require_latency", False):
        return 0.0, {}, "延时复测失败,跳过测速", None
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(urls))) as ex:
        futs = {
            ex.submit(measure_speed, port, url, args.speed_bytes, args.speed_timeout,
                      args.speed_early_bytes, args.speed_early_rate,
                      getattr(args, "speed_min_bytes", 1_000_000),
                      getattr(args, "speed_min_window", 0.2)): url
            for url in urls
        }
        for fut in as_completed(futs):
            url = futs[fut]
            try:
                results[url] = fut.result()
            except Exception as e:  # 单文件异常不影响其它文件
                results[url] = (0.0, 0, 0.0, str(e)[:80])

    rates, details = {}, []
    for url in urls:
        rate, nbytes, secs, err = results[url]
        tag = "release" if "proxy-node" in url else ("cloudflare" if "cloudflare" in url else "other")
        if nbytes:
            rates[tag] = rate
            details.append(f"{tag} {rate:.1f}MB/s {nbytes/1e6:.1f}MB {secs:.1f}s")
        else:
            details.append(f"{tag} 失败({err or 'no data'})")
    avg = weighted_rate(rates, weights)
    detail = "; ".join(details)
    if lat is not None:
        detail = f"延时 {lat:.0f}ms | " + detail
    return (avg if avg is not None else 0.0), rates, detail, lat


def load_inputs(inputs):
    """合并各来源节点(按完整配置去重),并记录每个节点来自哪个来源。"""
    import yaml

    merged, seen_cfg, per_source, dup_names, src_of_name = {}, set(), {}, 0, {}
    for inp in inputs:
        src = os.path.basename(os.path.dirname(os.path.abspath(inp)))
        with open(inp, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        n = 0
        for p in d.get("proxies", []):
            if not isinstance(p, dict) or not p.get("name") or not p.get("server"):
                continue
            if str(p["name"]).startswith("说明-"):
                continue
            key = hashlib.sha1(
                json.dumps({k: v for k, v in p.items() if k != "name"},
                           sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            if key in seen_cfg:
                continue
            seen_cfg.add(key)
            name = str(p["name"])
            if name in merged:
                dup_names += 1
                i = 2
                while f"{name} #{i}" in merged:
                    i += 1
                name = f"{name} #{i}"
                p = dict(p, name=name)
            merged[name] = p
            src_of_name[name] = src
            n += 1
        per_source[inp] = n
    return list(merged.values()), per_source, dup_names, src_of_name


def build_aio(good, speeds, tested, threshold, n_inputs, speed_label, speed_enabled,
              src_of_name, quality_min_speed, quality_max_delay, target_summary="",
              tested_names=None, net_label="", delay_tested=True):
    tested_names = tested_names or set()
    """good: [(proxy, delay)];speeds: {name: MB/s or None};src_of_name: {name: 来源标识}

    生成分组:
      说明 / ⚡ 高速节点 / 🏅 优质节点 / 🚀 节点选择(全部精选) / ♻️ 自动选择 /
      📦 <来源> 各来源精选(仅保留测速后的存活节点)
    """
    fast, quality_only, rest = [], [], []
    for p, delay in good:
        rate = speeds.get(p["name"])
        is_fast = rate is not None and rate > threshold
        is_quality = (rate is not None and rate >= quality_min_speed
                      and (delay is None or delay <= quality_max_delay))
        if is_fast:
            fast.append((p, delay, rate))
        elif is_quality:
            quality_only.append((p, delay, rate))
        else:
            rest.append((p, delay, rate))
    fast.sort(key=lambda x: -x[2])
    quality_only.sort(key=lambda x: (-x[2], x[1] if x[1] is not None else 10 ** 9))
    rest.sort(key=lambda x: (x[1] is None, x[1] or 0))
    quality = quality_only                 # 与"高速"互斥,两组不重叠
    ordered = fast + quality_only + rest   # 全部精选:高速 -> 优质 -> 其余按延迟

    def annotate(p, rate):
        base = strip_annotation(p["name"])
        if not speed_enabled or p["name"] not in tested_names:
            tag = "[未测速]"          # 本轮没有对它做测速(例如受 --speed-max-nodes 限制)
        elif rate is None:
            tag = "[测速失败]"
        else:
            tag = f"[{rate:.1f}MB/s]"
        return dict(p, name=f"{tag} {base}")

    annotated = [annotate(p, r) for p, _, r in ordered]
    names = [p["name"] for p in annotated]
    name_of = {id(p): a["name"] for (p, _, _), a in zip(ordered, annotated)}
    fast_names = [name_of[id(p)] for p, _, _ in fast]
    quality_names = [name_of[id(p)] for p, _, _ in quality]

    now = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 8 * 3600))
    fake_names = [f"说明-来源: AIO 精选(合并 {n_inputs} 个来源)"]
    if net_label:
        fake_names.append(f"说明-测试网络: {net_label}")
    if delay_tested:
        fake_names.append(f"说明-延迟测试: {len(good)}/{tested} 节点通过 generate_204")
    else:
        fake_names.append("说明-延迟测试: 本次跳过(手动参数),优质节点仅按速度判定")
    if speed_enabled:
        fake_names.append(
            f"说明-测速: {len(fast)} 个节点 > {threshold:g} MB/s({speed_label}实测)"
        )
        fake_names.append(f"说明-测速覆盖: {len(tested_names)}/{len(good)} 个可达节点")
        if target_summary:
            fake_names.append(f"说明-测速分项: {target_summary}")
        fake_names.append(
            f"说明-优质节点: {quality_min_speed:g}~{threshold:g} MB/s 且延迟 ≤ "
            f"{quality_max_delay} ms(与高速互斥,共 {len(quality)} 个)"
        )
    else:
        fake_names.append("说明-测速: 本次跳过(测试文件不可达)")
    fake_names += [
        f"说明-更新时间: {now} (CST)",
        f"说明-作者: {AUTHOR}",
        f"说明-仓库: {REPO}",
    ]

    groups = [{"name": "说明", "type": "select", "proxies": fake_names}]
    groups.append({
        "name": f"⚡ 高速节点(>{threshold:g}MB/s)",
        "type": "select",
        "proxies": fast_names or ["DIRECT"],
    })
    groups.append({"name": "🏅 优质节点", "type": "select", "proxies": quality_names or ["DIRECT"]})
    groups.append({"name": "🚀 节点选择(全部精选)", "type": "select", "proxies": names})
    groups.append({
        "name": "♻️ 自动选择",
        "type": "url-test",
        "url": TEST_URL,
        "interval": 300,
        "proxies": names,
    })

    # 每个来源一个标签页(仅含该来源通过延迟+测速的精选节点)
    per_src = {}
    for p, _, _ in ordered:
        src = src_of_name.get(p["name"], "")
        if src:
            per_src.setdefault(src, []).append(name_of[id(p)])
    for src, members in per_src.items():
        label = SOURCES.get(src, (src, ""))[0]
        groups.append({"name": f"📦 {label}", "type": "select", "proxies": members})
    src_stat = {SOURCES.get(s, (s, ""))[0]: len(m) for s, m in per_src.items()}

    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": "127.0.0.1:9090",
        "proxies": [fake_proxy(n) for n in fake_names] + annotated,
        "proxy-groups": groups,
        "rules": ["MATCH,🚀 节点选择(全部精选)"],
    }, len(fast), len(quality), src_stat


def build_merge_only(proxies, n_inputs, src_of_name, net_label=""):
    """不测延迟/带宽,直接把各来源节点合并成 AIO(仅去重、名唯一、分组)。

    用于手动触发 workflow 时关闭"测延迟/测带宽"的场景。
    """
    items = [(src_of_name.get(p["name"], ""), p) for p in proxies]
    items.sort(key=lambda sp: (sp[0], sp[1]["name"]))
    ordered, used, src_of_new = [], set(), {}
    for src, p in items:
        name = strip_annotation(p["name"])
        if name in used:
            i = 2
            while f"{name} #{i}" in used:
                i += 1
            name = f"{name} #{i}"
        used.add(name)
        ordered.append(dict(p, name=name))
        src_of_new[name] = src
    names = [p["name"] for p in ordered]

    now = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 8 * 3600))
    fake_names = [f"说明-来源: AIO 不精选(合并 {n_inputs} 个来源)"]
    if net_label:
        fake_names.append(f"说明-测试网络: {net_label}")
    fake_names.append("说明-测试: 本次未测延迟/带宽,直接合并(不精选)")
    fake_names += [
        f"说明-更新时间: {now} (CST)",
        f"说明-作者: {AUTHOR}",
        f"说明-仓库: {REPO}",
    ]

    groups = [{"name": "说明", "type": "select", "proxies": fake_names}]
    groups.append({"name": "🚀 节点选择(全部)", "type": "select", "proxies": names})
    groups.append({
        "name": "♻️ 自动选择",
        "type": "url-test",
        "url": TEST_URL,
        "interval": 300,
        "proxies": names,
    })
    per_src = {}
    for p in ordered:
        src = src_of_new.get(p["name"], "")
        if src:
            per_src.setdefault(src, []).append(p["name"])
    for src, members in per_src.items():
        label = SOURCES.get(src, (src, ""))[0]
        groups.append({"name": f"📦 {label}", "type": "select", "proxies": members})
    src_stat = {SOURCES.get(s, (s, ""))[0]: len(m) for s, m in per_src.items()}

    aio = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": "127.0.0.1:9090",
        "proxies": [fake_proxy(n) for n in fake_names] + ordered,
        "proxy-groups": groups,
        "rules": ["MATCH,🚀 节点选择(全部)"],
    }
    return aio, src_stat


def write_aio(aio, output):
    """写 AIO 文件(先写临时文件再原子替换)。"""
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    import yaml

    tmp = output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(aio, f, Dumper=SafeDumper, allow_unicode=False,
                  default_flow_style=False, sort_keys=False)
    os.replace(tmp, output)


def run_speed_batch(mihomo, batch, speed_urls, args, ports, weights=None):
    """对一批节点启动绑定出口的监听器,并发对**每个测速文件**测速。

    返回 {name: (加权平均MB/s or None, {文件标签: MB/s}, 延时ms or None)}。
    """
    listeners = [
        {"name": f"spd-{i}", "type": "mixed", "port": ports[i],
         "listen": "127.0.0.1", "proxy": p["name"]}
        for i, p in enumerate(batch)
    ]
    out = {}
    core = Core(mihomo, batch, ["MATCH,DIRECT"], listeners=listeners)
    try:
        core.start(wait=30, wait_ports=ports)
    except SystemExit as e:
        core.stop()
        print(f"      [WARN] 测速内核启动失败,跳过本批 {len(batch)} 个节点: {e}")
        return {p["name"]: (None, {}, None) for p in batch}
    try:
        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            futs = {ex.submit(measure_node, ports[i], speed_urls, args, weights): p["name"]
                    for i, p in enumerate(batch)}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    best, rates, detail, lat = fut.result()
                except Exception as e:  # 单个节点异常不影响整批
                    best, rates, detail, lat = 0.0, {}, str(e)[:80], None
                out[name] = (best if rates else None, rates, lat)
                if args.verbose:
                    print(f"        {name[:34]:34s} 加权 {best:6.2f} MB/s | {detail}")
    finally:
        core.stop()
    return out


def main():
    ap = argparse.ArgumentParser(description="mihomo 内核节点可达性 + 下载测速 + AIO 合并")
    ap.add_argument("inputs", nargs="+", help="清洗后的各来源 clash.yaml")
    ap.add_argument("-o", "--output", required=True, help="输出 AIO clash.yaml")
    ap.add_argument("--mihomo", default=None, help="mihomo 内核路径(默认 MIHOMO_BIN 或自动探测)")
    ap.add_argument("--concurrency", type=int, default=96, help="可达性(延迟)测试并发")
    ap.add_argument("--timeout-ms", type=int, default=4500, help="单节点延迟测试超时")
    ap.add_argument("--limit", type=int, default=0, help="只测试前 N 个节点(调试用,0=全部)")
    ap.add_argument("--no-delay", action="store_true", help="跳过延迟/可达性测试(所有节点视为可用)")
    ap.add_argument("--no-speed", action="store_true", help="跳过测速阶段")
    ap.add_argument("--merge-only", action="store_true",
                    help="完全不测试,直接把各来源节点合并成 AIO(不等同于 --no-delay --no-speed)")
    ap.add_argument("--speed-url", default=os.environ.get("SPEED_TEST_URL", ""),
                    help="测速文件 URL(逗号分隔可多个,默认 20MB Cloudflare 文件)")
    ap.add_argument("--speed-concurrency", type=int, default=96, help="测速并发(同时下载的节点数)")
    ap.add_argument("--speed-bytes", type=int, default=20_000_000, help="单个节点最大下载字节数")
    ap.add_argument("--speed-timeout", type=float, default=6.0, help="单个节点测速超时(秒,每个测试文件单独计时)")
    ap.add_argument("--speed-early-bytes", type=int, default=2_000_000,
                    help="已下载该字节数且速率已达标则提前结束(省流量)")
    ap.add_argument("--speed-early-rate", type=float, default=3.0, help="提前结束速率阈值(MB/s)")
    ap.add_argument("--speed-latency-timeout", type=float, default=3.0,
                    help="测速前延时复测超时(秒)")
    ap.add_argument("--skip-speed-on-latency-fail", action="store_true",
                    help="延时复测失败时跳过测速(默认不跳过,保证每个可达节点都被真实测速)")
    ap.add_argument("--speed-min-bytes", type=int, default=1_000_000,
                    help="有效测速的最小字节数,低于此值且耗时很短视为被截断,判为失败")
    ap.add_argument("--speed-min-window", type=float, default=0.2,
                    help="提前结束所需的最小采样窗口(秒),避免瞬时突发被当成持续速度")
    ap.add_argument("--speed-max-nodes", type=int, default=0, help="最多测速多少个节点(0=全部可达节点)")
    ap.add_argument("--fast-threshold", type=float, default=2.0, help="高速节点阈值(MB/s)")
    ap.add_argument("--net-label", default="", help="测试网络标注(写入说明节点,如'国内本地网络')")
    ap.add_argument("--speed-weight-cloudflare", type=float, default=SPEED_WEIGHTS["cloudflare"],
                    help="Cloudflare 测速文件权重(默认 0.6,高于 release 文件)")
    ap.add_argument("--speed-weight-release", type=float, default=SPEED_WEIGHTS["release"],
                    help="自建 release 测速文件权重(默认 0.4)")
    ap.add_argument("--quality-min-speed", type=float, default=1.0, help="优质节点最低速度(MB/s)")
    ap.add_argument("--quality-max-delay", type=int, default=1500, help="优质节点最高延迟(ms)")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个节点的测速明细")
    ap.add_argument("--keep-temp", action="store_true", help="保留内核临时目录(调试)")
    args = ap.parse_args()
    args.speed_require_latency = args.skip_speed_on_latency_fail

    t_start = time.monotonic()
    speed_urls = [u.strip() for u in (args.speed_url or ",".join(default_speed_urls())).split(",") if u.strip()]

    # 1) 合并去重
    proxies, per_source, dup_names, src_of_name = load_inputs(args.inputs)
    if args.limit:
        proxies = proxies[:args.limit]
    print(f"[1/5] 合并 {len(args.inputs)} 个来源,去重后待测节点: {len(proxies)}"
          f"(重名自动加后缀 {dup_names} 个)")
    for src, n in per_source.items():
        print(f"        {os.path.basename(os.path.dirname(src)):16s} +{n}")
    if not proxies:
        raise SystemExit("[FAIL] 无任何节点可测")

    # 1.5) 直接合并模式(不测延迟/带宽)
    if args.merge_only:
        print("[1.5/5] 直接合并模式: 跳过延迟与测速,仅合并去重/分组")
        aio, src_stat = build_merge_only(proxies, len(args.inputs), src_of_name, args.net_label)
        write_aio(aio, args.output)
        print(f"[5/5] AIO 已写入 {args.output}: {len(proxies)} 个节点"
              f"({len(aio['proxy-groups'])} 个分组),耗时 {time.monotonic()-t_start:.0f}s")
        for label, n in src_stat.items():
            print(f"        📦 {label}: {n} 个节点")
        return

    mihomo = find_mihomo(args.mihomo)

    # 2) 可达性(延迟)测试
    if args.no_delay:
        ok = {p["name"]: None for p in proxies}
        total = len(proxies)
        print(f"[2/5] 延迟测试: 已跳过(--no-delay),{total} 个节点全部视为可用")
    else:
        with Core(mihomo, proxies, ["MATCH,DIRECT"], keep_dir=args.keep_temp) as core:
            pmap = {}
            for _ in range(10):
                try:
                    pmap = api_get(core.ctrl_port, core.secret, "/proxies")["proxies"]
                except Exception:
                    pmap = {}
                if pmap:
                    break
                time.sleep(0.5)
            names = [n for n, info in pmap.items()
                     if n not in SKIP_NAMES and info.get("type") not in GROUP_TYPES]
            if not names:
                raise SystemExit("[FAIL] 内核未返回任何可测节点")
            total = len(names)
            print(f"[2/5] 可达性测试: {total} 个节点 -> generate_204(并发 {args.concurrency})")
            ok, done, interval = {}, 0, max(1, total // 20)
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                futs = {ex.submit(test_delay, core.ctrl_port, core.secret, n, args.timeout_ms): n for n in names}
                for fut in as_completed(futs):
                    name, delay = fut.result()
                    done += 1
                    if delay is not None:
                        ok[name] = delay
                    if done % interval == 0 or done == total:
                        print(f"        进度 {done}/{total} 可用 {len(ok)} "
                              f"({time.monotonic()-t_start:.0f}s)", flush=True)
            print(f"        可达节点: {len(ok)}/{total}")
            if not ok:
                raise SystemExit("[FAIL] 全部节点不可达,不生成 AIO")

    # 3) 测速
    by_name = {p["name"]: p for p in proxies}
    candidates = sorted(ok, key=lambda n: (ok[n] is None, ok[n] or 0))
    if args.speed_max_nodes:
        candidates = candidates[:args.speed_max_nodes]
    speeds = {n: None for n in ok}
    delays = {n: ok[n] for n in ok}
    speed_tested = set()
    speed_enabled = False
    speed_label = "测试文件"
    target_stats = {}
    target_summary = ""
    if args.no_speed:
        print("[3/5] 测速: 已跳过(--no-speed)")
    else:
        print(f"[3/5] 测速文件探测(全部可达的都测): {speed_urls}")
        active_urls = pick_speed_urls(speed_urls)
        if not active_urls:
            print("        [WARN] 测试文件直连不可达,跳过测速(节点名标注为 [未测速])")
        else:
            speed_enabled = True
            speed_label = f"{args.speed_bytes // 1000000}MB 文件"
            batches = [candidates[i:i + args.speed_concurrency]
                       for i in range(0, len(candidates), args.speed_concurrency)]
            print(f"        测速文件 {len(active_urls)} 个: {active_urls}")
            print(f"        测速 {len(candidates)} 个节点,分 {len(batches)} 批,"
                  f"每批 {args.speed_concurrency} 并发,单文件上限 "
                  f"{args.speed_bytes/1e6:.0f}MB/{args.speed_timeout:g}s")
            weights = {"cloudflare": args.speed_weight_cloudflare,
                       "release": args.speed_weight_release}
            print(f"        权重(加权平均): cloudflare {weights['cloudflare']:g} / "
                  f"release {weights['release']:g}")
            for bi, batch in enumerate(batches, 1):
                ports = find_free_ports(len(batch))
                res = run_speed_batch(mihomo, [by_name[n] for n in batch], active_urls,
                                      args, ports, weights)
                for n, (best, rates, lat) in res.items():
                    speeds[n] = best
                    speed_tested.add(n)
                    if lat is not None:
                        delays[n] = lat  # 测速前复测的延时,用于优质判定
                    for tag, rate in rates.items():
                        target_stats.setdefault(tag, []).append(rate)
                got = sum(1 for v, _, _ in res.values() if v is not None)
                fast_n = sum(1 for v, _, _ in res.values() if v is not None and v > args.fast_threshold)
                print(f"        批次 {bi}/{len(batches)}: 测速成功 {got}/{len(batch)},"
                      f"高速 {fast_n} ({time.monotonic()-t_start:.0f}s)", flush=True)
            if target_stats:
                target_summary = ", ".join(
                    f"{tag}(w={weights.get(tag, 0.5):g}) {sum(v)/len(v):.1f}MB/s/{len(v)}个"
                    for tag, v in sorted(target_stats.items()))
                print(f"        各测速文件平均速度: {target_summary}")

    # 4) 排序 / 分组 / 标注(延时用测速前复测的新鲜值)
    good = [(by_name[n], delays[n]) for n in ok]
    aio, n_fast, n_quality, src_stat = build_aio(
        good, speeds, total, args.fast_threshold, len(args.inputs),
        speed_label, speed_enabled, src_of_name,
        args.quality_min_speed, args.quality_max_delay, target_summary,
        tested_names=speed_tested, net_label=args.net_label,
        delay_tested=not args.no_delay,
    )
    print(f"[4/5] 生成 AIO: 全部精选 {len(good)} 个,"
          f"高速(>{args.fast_threshold:g}MB/s) {n_fast} 个,优质 {n_quality} 个")
    for label, n in src_stat.items():
        print(f"        📦 {label}: {n} 个精选节点")

    # 5) 写出
    write_aio(aio, args.output)
    n_groups = len(aio["proxy-groups"])
    print(f"[5/5] AIO 已写入 {args.output}: {len(good)} 个可用节点"
          f"(高速 {n_fast} 个 / 优质 {n_quality} 个 / {n_groups} 个分组),"
          f"耗时 {time.monotonic()-t_start:.0f}s")


if __name__ == "__main__":
    main()
