#!/usr/bin/env python3
"""国内（中国网络）本地测试入口 —— 一条命令测出"国内可用的节点"。

做三件事:
  1. 抓取:拉取各来源订阅(GitHub 上的节点文件走 ghproxy.net 镜像,无需代理;
     yoyapai 直连);抓取失败/无需要的来源自动跳过;
  2. 清洗:控制字符/重名/悬空引用修复(可选 mihomo -t 门禁);
  3. 实测:用 mihomo 内核在本机(国内网络)测可达性 + 20MB 文件测速,
     生成一份"国内视角"的 AIO 订阅(节点名带 [x.xMB/s] 标注)。

注意:
  * ghproxy 只用于"抓节点文件",节点测速始终直连真实测试文件
    (本仓库 release:test 的 speedtest-20mb.bin + Cloudflare),否则测到的是镜像速度;
  * 默认输出 output/aio/clash-cn.yaml(已 gitignore,不会提交到仓库),
    这是本机网络下的产物,不替代线上发布的 AIO。

常用:
  python scripts/local_test_cn.py                       # 全流程(推荐)
  python scripts/local_test_cn.py --no-fetch            # 跳过抓取,用已有 output/*/clash.yaml
  python scripts/local_test_cn.py --no-fetch --limit 300 --speed-max-nodes 80   # 少测一点省流量
  python scripts/local_test_cn.py --input foo.yaml      # 直接测某个订阅文件
  python scripts/local_test_cn.py --gate                # 额外做 mihomo -t 内核校验

环境变量:
  GH_PROXY        默认 https://ghproxy.net(可用 --gh-proxy/--no-gh-proxy 覆盖)
  MIHOMO_BIN      已有 mihomo 内核路径;不设置时会尝试自动下载(走 GH_PROXY)
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GH_PROXY = "https://ghproxy.net"
DEFAULT_OUTPUT = os.path.join("output", "aio", "clash-cn.yaml")
NET_LABEL = "国内本地网络"

# 国内模式(--cn-speed)的测速目标:国内镜像大文件 + Cloudflare。
# GitHub release 资产在国内多数节点上拉不动,国内模式用镜像文件替代它;
# 都是直连测试,不经过 ghproxy 之类的镜像代理。
CN_SPEED_URLS = [
    "https://mirrors.huaweicloud.com/ubuntu-releases/22.04/ubuntu-22.04.5-live-server-amd64.iso",
    "https://speed.cloudflare.com/__down?bytes=20000000",
]


def step(title):
    print()
    print("=" * 64)
    print(f"[{time.strftime('%H:%M:%S')}] {title}")
    print("=" * 64)


def run(cmd, env, check=False):
    print(f"$ {' '.join(cmd)}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    cost = time.time() - t0
    if proc.returncode != 0:
        msg = f"命令失败(退出码 {proc.returncode},耗时 {cost:.0f}s): {' '.join(cmd)}"
        if check:
            raise SystemExit(f"[FAIL] {msg}")
        print(f"  [WARN] {msg}")
    else:
        print(f"  [OK] 耗时 {cost:.0f}s")
    return proc.returncode


def ensure_mihomo(env):
    """优先用已有的 mihomo;没有再走 GH_PROXY 自动下载(带 SHA256 校验)。"""
    cached = sorted(glob.glob(os.path.expanduser("~/.cache/mihomo/mihomo-*")))
    for cand in [env.get("MIHOMO_BIN"), shutil.which("mihomo"), "/usr/local/bin/mihomo",
                 "/tmp/mihomo", os.path.join(ROOT, "mihomo"), *cached]:
        if cand and os.path.isfile(cand):
            print(f"[OK] 使用已有 mihomo 内核: {cand}")
            return cand
    print("[*] 未找到 mihomo 内核,尝试自动下载(ghproxy 镜像 + SHA256 校验)...")
    proc = subprocess.run(["bash", os.path.join("scripts", "install_mihomo.sh")],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    m = re.search(r"^MIHOMO_BIN=(.+)$", proc.stdout or "", re.MULTILINE)
    if m and os.path.isfile(m.group(1)):
        print(f"[OK] mihomo 已就绪: {m.group(1)}")
        return m.group(1)
    tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).splitlines()[-6:])
    raise SystemExit("[FAIL] 无法自动安装 mihomo,请手动安装后设置 MIHOMO_BIN\n" + tail)


def main():
    ap = argparse.ArgumentParser(
        description="国内本地测试:抓取(ghproxy) -> 清洗 -> 本机实测 -> 生成国内可用 AIO")
    ap.add_argument("--no-fetch", action="store_true", help="跳过抓取,直接用现有 output/*/clash.yaml")
    ap.add_argument("--input", nargs="*", default=None, help="直接指定要测的订阅文件(跳过抓取)")
    ap.add_argument("--gate", action="store_true", help="清洗时额外用 mihomo -t 校验")
    ap.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help=f"输出路径(默认 {DEFAULT_OUTPUT})")
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 个节点(省流量/快速验证)")
    ap.add_argument("--concurrency", type=int, default=128, help="可达性测试并发")
    ap.add_argument("--timeout-ms", type=int, default=4500, help="单节点延迟测试超时")
    ap.add_argument("--speed-concurrency", type=int, default=32, help="测速并发(国内家宽建议 16~48)")
    ap.add_argument("--speed-max-nodes", type=int, default=0, help="最多测速多少个节点(0=全部可达)")
    ap.add_argument("--speed-bytes", type=int, default=20_000_000, help="单文件测速上限字节")
    ap.add_argument("--speed-timeout", type=float, default=5.0, help="单节点单文件测速超时(秒)")
    ap.add_argument("--speed-latency-timeout", type=float, default=6.0,
                    help="测速前延时复测超时(秒,国内家宽建议 5~8)")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个节点的测速明细")
    ap.add_argument("--speed-url", default="", help="自定义测速文件(逗号分隔,默认 release:test + Cloudflare)")
    ap.add_argument("--cn-speed", action="store_true",
                    help="国内模式:用国内镜像大文件替代 GitHub release 文件做测速目标(直连,不走镜像代理)")
    ap.add_argument("--fast-threshold", type=float, default=2.0, help="高速节点阈值(MB/s)")
    ap.add_argument("--quality-min-speed", type=float, default=1.0, help="优质节点最低速度(MB/s)")
    ap.add_argument("--quality-max-delay", type=int, default=1500, help="优质节点最高延迟(ms)")
    ap.add_argument("--gh-proxy", default=None, help=f"GitHub 镜像(默认 {DEFAULT_GH_PROXY})")
    ap.add_argument("--no-gh-proxy", action="store_true", help="禁用镜像,直连 GitHub")
    ap.add_argument("--keep-raw", action="store_true", help="保留下载的 clash.raw.yaml")
    args = ap.parse_args()

    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "scripts")
    env["PYTHONUNBUFFERED"] = "1"
    if args.no_gh_proxy:
        env.pop("GH_PROXY", None)
    else:
        env.setdefault("GH_PROXY", args.gh_proxy or DEFAULT_GH_PROXY)

    print("=" * 64)
    print("  国内本地测试（中国网络视角）")
    print("=" * 64)
    print(f"  GH_PROXY(仅抓取节点文件) : {env.get('GH_PROXY') or '(未启用,直连)'}")
    print("  节点测速                   : 直连 release:test 20MB 文件 + Cloudflare(不走镜像)")
    print(f"  输出                       : {args.output}")

    mihomo = ensure_mihomo(env)
    env["MIHOMO_BIN"] = mihomo

    # ---------- 1) 抓取 ----------
    inputs = None
    if args.input:
        inputs = args.input
        print(f"[*] 使用指定的 {len(inputs)} 个输入文件,跳过抓取")
    elif not args.no_fetch:
        step("1/3 抓取 yoyapai.com(直连)")
        run([sys.executable, "scripts/scraper.py"], env)
        if env.get("GH_PROXY"):
            print(f"  [INFO] GitHub 来源将经镜像抓取: {env['GH_PROXY']}")
        else:
            print("  [INFO] 未启用镜像,直连 GitHub")
        step("1/3 抓取其它来源")
        run([sys.executable, "scripts/fetch_sources.py"], env)
        step("1/3 抓取页面型来源(每日文章页解析)")
        run([sys.executable, "scripts/scrape_page_sources.py"], env)

    # ---------- 2) 清洗 ----------
    raw_files = sorted(glob.glob(os.path.join(ROOT, "output", "*", "clash.raw.yaml")))
    if raw_files:
        step("2/3 清洗抓取到的来源")
        for raw in raw_files:
            src = os.path.basename(os.path.dirname(raw))
            dst = os.path.join(ROOT, "output", src, "clash.yaml")
            cmd = [sys.executable, "scripts/sanitize.py", raw, dst, "--source", src]
            if args.gate:
                cmd += ["--gate", "--mihomo", mihomo]
            run(cmd, env)
        if not args.keep_raw:
            for raw in raw_files:
                try:
                    os.unlink(raw)
                except OSError:
                    pass
    else:
        print("[*] 没有 clash.raw.yaml 需要清洗")

    # ---------- 3) 实测 ----------
    if inputs is None:
        inputs = sorted(
            p for p in glob.glob(os.path.join(ROOT, "output", "*", "clash.yaml"))
            if os.path.basename(os.path.dirname(p)) not in ("aio", "aio-all")
        )
    inputs = [p for p in inputs if os.path.isfile(p)]
    if not inputs:
        raise SystemExit("[FAIL] 没有可测的订阅文件(output/*/clash.yaml 为空),请先抓取")
    print(f"[*] 待测来源 {len(inputs)} 个: {[os.path.basename(os.path.dirname(p)) for p in inputs]}")

    step("3/3 可达性 + 20MB 文件测速(本机网络直连)")
    cmd = [sys.executable, "scripts/test_nodes.py", *inputs,
           "-o", args.output, "--mihomo", mihomo,
           "--concurrency", str(args.concurrency),
           "--timeout-ms", str(args.timeout_ms),
           "--speed-concurrency", str(args.speed_concurrency),
           "--speed-timeout", str(args.speed_timeout),
           "--speed-latency-timeout", str(args.speed_latency_timeout),
           "--speed-bytes", str(args.speed_bytes),
           "--fast-threshold", str(args.fast_threshold),
           "--quality-min-speed", str(args.quality_min_speed),
           "--quality-max-delay", str(args.quality_max_delay),
           "--net-label", NET_LABEL]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    if args.speed_max_nodes:
        cmd += ["--speed-max-nodes", str(args.speed_max_nodes)]
    if args.verbose:
        cmd += ["-v"]
    if args.speed_url:
        cmd += ["--speed-url", args.speed_url]
    elif args.cn_speed:
        cmd += ["--speed-url", ",".join(CN_SPEED_URLS)]
        print(f"  [INFO] 国内模式测速文件: {CN_SPEED_URLS}")
    if run(cmd, env) != 0:
        raise SystemExit("[FAIL] AIO 生成失败,请查看上面的日志")

    # ---------- 汇总 ----------
    out_path = args.output if os.path.isabs(args.output) else os.path.join(ROOT, args.output)
    print()
    print("=" * 64)
    print("  完成:国内可用节点已生成")
    print("=" * 64)
    print(f"  文件: {out_path}")
    try:
        import yaml

        with open(out_path, encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        names = [p["name"] for p in d.get("proxies", []) if not p["name"].startswith("说明-")]
        fast = sum(1 for n in names if n.startswith("[") and "MB/s" in n[:12]
                   and float(n[1:n.index("MB/s")]) > args.fast_threshold)
        tested = sum(1 for n in names if n.startswith("[") and "MB/s" in n[:12])
        print(f"  精选节点 {len(names)} 个（有速度 {tested} 个,高速 >{args.fast_threshold:g}MB/s {fast} 个）")
        for g in d.get("proxy-groups", []):
            print(f"    - {g['name']}: {len(g['proxies'])}")
    except Exception as e:  # 统计失败不影响产物
        print(f"  (统计失败: {e})")
    print()
    print("  导入方式:把上面的文件复制到手机,FlClash/Clash Verge 里选“从文件导入”即可。")
    print("  想直接测线上订阅: python scripts/local_test_cn.py --input <订阅文件或已保存的 yaml>")


if __name__ == "__main__":
    main()
