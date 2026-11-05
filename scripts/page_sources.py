#!/usr/bin/env python3
"""页面型来源解析器:订阅地址每天变化,需要先解析栏目/文章页再拿到下载地址。

与 sources.py 的 FETCH_URLS(固定订阅地址)互补:
  - nodetoolbox: 索引页 https://nodetoolbox.net/free-nodes/
                  -> 最新文章 /free-nodes/YYYY-MM-DD/
                  -> https://nodesub.nodetoolbox.net/YYYY/MM/nodetoolbox-YYYYMMDD.yaml
  - jichangg:    文章页 https://jichangg.world/mianfei/
                  -> 内嵌 https://sub.jichange.world/free/YYYYMMDD/clash.yaml
                 (2026-11 实测: 该站停在 2026-10-08,且 sub.jichange.world 已 NXDOMAIN,
                  解析不到可下载地址时抛 SourceUnavailable,由调用方跳过)

每个来源实现 discover() -> dict:
    {"sub_url": 订阅地址, "date": 内容日期, "detail": 说明文字}
没有可用地址时抛 SourceUnavailable(带原因)。
"""
import re
import socket
import time
from datetime import date, timedelta
from urllib.parse import urlparse

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
TIMEOUT = 60
RETRIES = 2


class SourceUnavailable(RuntimeError):
    """页面解析不到可用订阅(站点停更/订阅域名失效/结构变化)。"""


def fetch_text(url, timeout=TIMEOUT):
    """带重试的 GET,返回解码后的文本。"""
    last = None
    for i in range(RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as e:  # noqa: BLE001 - 统一转成 SourceUnavailable
            last = e
            if i < RETRIES:
                time.sleep(1 + i)
    raise SourceUnavailable(f"请求失败 {url}: {last}")


def host_resolves(url):
    """订阅域名是否能解析(DNS 挂掉时给出明确原因)。"""
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# NodeToolBox: 索引页 -> 每日文章页 -> 每日订阅 yaml
# --------------------------------------------------------------------------
NODETOOLBOX_INDEX = "https://nodetoolbox.net/free-nodes/"
NODETOOLBOX_SUB_RE = re.compile(r'https://nodesub\.nodetoolbox\.net/[^"\'\s<>]+\.ya?ml')
NODETOOLBOX_DAY_RE = re.compile(r'/free-nodes/(\d{4}-\d{2}-\d{2})/')


def _nodetoolbox_days(index_html):
    days = sorted(set(NODETOOLBOX_DAY_RE.findall(index_html)), reverse=True)
    return days


def _nodetoolbox_extract(daily_html):
    """每日文章页里的 Clash 订阅地址;优先 <a class=node-sub-url>,其次任意 nodesub 链接。"""
    m = re.search(
        r'<a[^>]+class="[^"]*node-sub-url[^"]*"[^>]+href="(https://nodesub\.[^"]+\.ya?ml)"',
        daily_html, re.I)
    if m:
        return m.group(1)
    m = re.search(NODETOOLBOX_SUB_RE, daily_html)
    if m:
        return m.group(0)
    return None


def _nodetoolbox_discover():
    index = fetch_text(NODETOOLBOX_INDEX)
    days = _nodetoolbox_days(index)
    # 索引页可能缓存滞后:再按今天/昨天补两个候选
    today = date.today()
    for d in (today, today - timedelta(days=1)):
        if d.isoformat() not in days:
            days.append(d.isoformat())
    errors = []
    for day in days[:4]:
        url = f"{NODETOOLBOX_INDEX}{day}/"
        try:
            daily = fetch_text(url)
        except SourceUnavailable as e:
            errors.append(str(e))
            continue
        sub_url = _nodetoolbox_extract(daily)
        if sub_url:
            return {"sub_url": sub_url, "date": day, "detail": f"每日文章 {url}"}
        errors.append(f"{url} 中没有找到 .yaml 订阅链接")
    raise SourceUnavailable("; ".join(errors[-2:]) or "索引页没有每日文章")


# --------------------------------------------------------------------------
# 机场e / jichangg.world: 文章页内嵌按日期命名的订阅地址
# --------------------------------------------------------------------------
JICHANGG_PAGE = "https://jichangg.world/mianfei/"
JICHANGG_SUB_RE = re.compile(
    r'https://sub\.jichang[a-z]*\.world/free/(\d{8})/([a-z0-9_]+\.ya?ml)', re.I)
JICHANGG_UPDATE_RE = re.compile(r'(?:最近更新|最后更新)[:：]?\s*(\d{4}-\d{2}-\d{2})')


def _jichangg_discover():
    html = fetch_text(JICHANGG_PAGE)
    hits = JICHANGG_SUB_RE.findall(html)
    if not hits:
        raise SourceUnavailable(f"{JICHANGG_PAGE} 中没有找到 .yaml 订阅链接(页面结构可能变化)")
    # 同一天有多个文件:优先 mihomo.yaml(Clash.Meta),其次 clash.yaml,再其次其它
    by_date = {}
    for ymd, fname in JICHANGG_SUB_RE.findall(html):
        by_date.setdefault(ymd, []).append(fname)
    newest = max(by_date)
    files = by_date[newest]
    prefer = next((f for f in ("mihomo.yaml", "clash.yaml") if f in files), files[0])
    sub_url = f"https://sub.jichange.world/free/{newest}/{prefer}"
    page_date = ""
    m = JICHANGG_UPDATE_RE.search(html)
    if m:
        page_date = m.group(1)
    if not host_resolves(sub_url):
        raise SourceUnavailable(
            f"订阅域名 {urlparse(sub_url).hostname} 无法解析(页面最后更新 {page_date or newest},"
            "站点可能已停止维护;该来源暂不更新)")
    if page_date and page_date < (date.today() - timedelta(days=7)).isoformat():
        raise SourceUnavailable(f"页面最后更新停留在 {page_date},已超过 7 天,该来源暂不更新")
    return {"sub_url": sub_url, "date": newest, "detail": f"页面更新 {page_date or newest}"}


# 注册表:来源标识必须与 sources.SOURCES 中的键一致(sanitize 需要)
PAGE_SOURCES = {
    "nodetoolbox": {
        "name": "NodeToolBox",
        "homepage": NODETOOLBOX_INDEX,
        "discover": _nodetoolbox_discover,
    },
    "jichangg": {
        "name": "机场e (jichangg.world)",
        "homepage": JICHANGG_PAGE,
        "discover": _jichangg_discover,
    },
}
