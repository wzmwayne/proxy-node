# proxy-node

免费 Clash 节点订阅聚合 - 每 4 小时自动抓取、清洗、更新

## 说明

本仓库通过 GitHub Actions **每 4 小时**(UTC 00/04/08/12/16/20,即北京时间 08/12/16/20/00/04 点)自动抓取多个免费节点来源,对每个来源的订阅文件做**清洗**(剔除含控制字符等无法被 Clash.Meta 解析的内容)后发布。

**不同来源的订阅文件相互独立、按来源目录分类存放,不会混淆。**

## 订阅链接

> **国内网络镜像(ghproxy.net)**:无法直接访问 `raw.githubusercontent.com` 时使用:

| 来源 | ghproxy.net 镜像订阅链接 |
|------|--------------------------|
| yoyapai.com | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/yoyapai/clash.yaml |
| Au1rxx/free-vpn-subscriptions | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/au1rxx/clash.yaml |

**直连链接**:

| 来源 | 文件 | 订阅链接 |
|------|------|----------|
| yoyapai.com(免费节点分享) | `output/yoyapai/clash.yaml` | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml |
| Au1rxx/free-vpn-subscriptions | `output/au1rxx/clash.yaml` | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/au1rxx/clash.yaml |

> 仅提供 Clash (Mihomo) 格式。直接复制链接到 FlClash / Clash Verge Rev / Mihomo 的订阅导入框即可。

## 清洗规则

每个来源的 `clash.yaml` 在发布前都会经过 `scripts/sanitize.py` 处理:

- 按 go-yaml v3 的码点白名单检查**解码后**的每个字符串值(不只是字节扫描),丢弃含控制字符(U+0000-001F、U+007F-009F 等)的节点 —— 这是 FlClash 报 `yaml: control characters are not allowed` 的根因;
- 清理 `proxy-groups` 中指向已删除节点的失效引用;
- 输出为纯 ASCII YAML(非 ASCII 字符以 `\UXXXXXXXX` 转义,兼容所有 YAML 解析器);
- 写入前二次解析校验,任何残留违规即拒绝发布。

## 目录结构

```
output/
  yoyapai/  clash.yaml     # yoyapai.com 来源(清洗后)
  au1rxx/   clash.yaml     # Au1rxx/free-vpn-subscriptions 来源(清洗后)
scripts/
  scraper.py               # 抓取 yoyapai.com 文章并提取订阅链接
  fetch_au1rxx.py          # 下载 Au1rxx 来源的 clash.yaml
  sanitize.py              # 通用清洗脚本(控制字符 + 引用清理 + 双重校验)
latest_urls.json           # yoyapai 最新文章信息
.github/workflows/scrape.yml
```

## 本地运行

```bash
pip install requests beautifulsoup4 pyyaml
python scripts/scraper.py          # 抓取 yoyapai 并下载到 output/yoyapai/
python scripts/fetch_au1rxx.py     # 下载 au1rxx 到 output/au1rxx/
python scripts/sanitize.py output/yoyapai/clash.yaml output/yoyapai/clash.yaml.tmp
python scripts/sanitize.py output/au1rxx/clash.yaml output/au1rxx/clash.yaml.tmp
```

## License

MIT
