#!/usr/bin/env python3
"""订阅来源清单(集中维护) + GitHub 下载镜像支持。

SOURCES:       来源标识 -> (显示名称, 主页 URL),供 sanitize.py 说明节点使用
FETCH_URLS:    来源标识 -> 固定订阅文件 URL(yoyapai 由 scraper.py 抓取,不在此列)
PAGE_SOURCES:  页面型来源(订阅地址每日变化)见 page_sources.py,由 scrape_page_sources.py 抓取
"""
import os

# 国内直连 GitHub 不稳:设置 GH_PROXY(例如 https://ghproxy.net)后,
# **抓取节点文件**时会自动走该镜像;节点测速不走镜像(必须直连测真实速度)。
GH_PROXY = os.environ.get("GH_PROXY", "").rstrip("/")
GITHUB_PREFIXES = (
    "https://raw.githubusercontent.com/",
    "https://github.com/",
    "https://gist.githubusercontent.com/",
    "https://objects.githubusercontent.com/",
    "https://codeload.github.com/",
)


def mirror_url(url: str) -> str:
    """把 GitHub 链接改写为镜像链接(未配置 GH_PROXY 时原样返回)。"""
    if GH_PROXY and url.startswith(GITHUB_PREFIXES):
        return f"{GH_PROXY}/{url}"
    return url


SOURCES = {
    "yoyapai": ("yoyapai.com", "https://yoyapai.com/category/mianfeijiedian"),
    # 页面型来源(订阅地址每日变化,由 scrape_page_sources.py 解析)
    "nodetoolbox": ("NodeToolBox", "https://nodetoolbox.net/free-nodes/"),
    "jichangg": ("机场e (jichangg.world)", "https://jichangg.world/mianfei/"),
    "au1rxx": ("Au1rxx/free-vpn-subscriptions", "https://github.com/Au1rxx/free-vpn-subscriptions"),
    "freesub": ("Ruk1ng001/freeSub", "https://github.com/Ruk1ng001/freeSub"),
    "ripaojiedian": ("ripaojiedian/freenode", "https://github.com/ripaojiedian/freenode"),
    "passcro": ("zhangkaiitugithub/passcro", "https://github.com/zhangkaiitugithub/passcro"),
    "anaer": ("anaer.github.io/Sub", "https://anaer.github.io/Sub/proxies.yaml"),
    "xiaoji235": ("xiaoji235/airport-free", "https://github.com/xiaoji235/airport-free"),
}

FETCH_URLS = {
    "au1rxx": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/clash.yaml",
    "freesub": "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml",
    "ripaojiedian": "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash",
    "passcro": "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml",
    "anaer": "https://anaer.github.io/Sub/proxies.yaml",
    "xiaoji235": "https://raw.githubusercontent.com/xiaoji235/airport-free/main/clash/clashnodecc.txt",
}
