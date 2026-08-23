# proxy-node

免费 Clash 节点订阅聚合 - 每 4 小时自动抓取、清洗、更新

## 说明

本仓库通过 GitHub Actions **每 4 小时**(UTC 00/04/08/12/16/20,即北京时间 08/12/16/20/00/04 点)自动抓取多个免费节点来源,对每个来源的订阅文件做**清洗**(剔除含控制字符等无法被 Clash.Meta 解析的内容)后发布。

**不同来源的订阅文件相互独立、按来源目录分类存放,不会混淆。**

## 订阅链接

> **AIO 精选(推荐)**:全部来源的节点经 Clash.Meta (mihomo) 内核逐个测试 `https://www.gstatic.com/generate_204` 后,仅保留可用节点、按延迟排序合并而成,每 4 小时重新测试更新:

| 类型 | 直连 | ghproxy.net 镜像(国内网络) |
|------|------|------------------------------|
| **AIO 精选(合并全部来源)** | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/aio/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/aio/clash.yaml |

**单来源订阅(直连 + ghproxy 镜像)**:

| 来源 | 直连 | ghproxy.net 镜像 |
|------|------|-------------------|
| yoyapai.com | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/yoyapai/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/yoyapai/clash.yaml |
| Au1rxx/free-vpn-subscriptions | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/au1rxx/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/au1rxx/clash.yaml |
| Ruk1ng001/freeSub | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/freesub/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/freesub/clash.yaml |
| ripaojiedian/freenode | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/ripaojiedian/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/ripaojiedian/clash.yaml |
| zhangkaiitugithub/passcro | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/passcro/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/passcro/clash.yaml |
| anaer.github.io/Sub | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/anaer/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/anaer/clash.yaml |
| xiaoji235/airport-free | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/xiaoji235/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/xiaoji235/clash.yaml |

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
  freesub/  clash.yaml     # Ruk1ng001/freeSub 来源(清洗后)
  ripaojiedian/ clash.yaml # ripaojiedian/freenode 来源(清洗后)
  passcro/  clash.yaml     # zhangkaiitugithub/passcro 来源(清洗后)
  anaer/    clash.yaml     # anaer.github.io/Sub 来源(清洗后)
  xiaoji235/ clash.yaml    # xiaoji235/airport-free 来源(清洗后)
  aio/      clash.yaml     # AIO 精选(合并全部来源,经 mihomo 内核测试可用节点)
scripts/
  sources.py               # 来源清单(名称/主页/下载 URL,集中维护)
  scraper.py               # 抓取 yoyapai.com 文章并提取订阅链接
  fetch_sources.py         # 下载各来源的 clash.yaml
  sanitize.py              # 通用清洗脚本(控制字符 + 引用清理 + 双重校验)
  test_nodes.py            # mihomo 内核逐节点测试 generate_204 + 合并生成 AIO
latest_urls.json           # yoyapai 最新文章信息
.github/workflows/scrape.yml
```

## 本地运行

```bash
pip install requests beautifulsoup4 pyyaml
python scripts/scraper.py          # 抓取 yoyapai 并下载到 output/yoyapai/
python scripts/fetch_au1rxx.py     # 下载 au1rxx 到 output/au1rxx/
python scripts/sanitize.py output/yoyapai/clash.yaml output/yoyapai/clash.yaml.tmp --source yoyapai
python scripts/sanitize.py output/au1rxx/clash.yaml output/au1rxx/clash.yaml.tmp --source au1rxx
# 需要 mihomo 内核(MIHOMO_BIN 或 /usr/local/bin/mihomo):
python scripts/test_nodes.py output/yoyapai/clash.yaml output/au1rxx/clash.yaml -o output/aio/clash.yaml
```

## License

MIT
