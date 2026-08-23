#!/usr/bin/env python3
"""订阅来源清单(集中维护)。

SOURCES:    来源标识 -> (显示名称, 主页 URL),供 sanitize.py 说明节点使用
FETCH_URLS: 来源标识 -> 订阅文件 URL(yoyapai 由 scraper.py 抓取,不在此列)
"""
SOURCES = {
    "yoyapai": ("yoyapai.com", "https://yoyapai.com/category/mianfeijiedian"),
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
