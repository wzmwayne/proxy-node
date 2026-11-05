# 声明

本项目已于 **2026-11-05 恢复维护**（此前因学业原因暂缓更新并把仓库设为归档，现解除归档）。

- 仓库已解除**归档（只读）**，恢复每 4 小时自动抓取、清洗、实测与发布；
- 停更期间 `output/*` 曾被替换为「通知假节点」（用于在客户端展示公告），现所有订阅已恢复为真实节点；
- 项目说明文档保留在本 README 下方（自「proxy-node」起）。

## 为什么关注 keepandroidopen.org

安卓正在从「开放安装」走向受控分发：侧载限制、开发者验证、平台签名垄断，
会直接压缩个人开发者与普通用户的空间。这与项目是否更新无关，值得持续关注。

<https://keepandroidopen.org>

## 许可

放弃所有权利（Unlicense / 公有领域），可自由取用、修改与再分发，详见 [LICENSE](LICENSE)。

---

# proxy-node

免费 Clash 节点订阅聚合 —— 每 4 小时自动抓取、清洗、**真内核实测(可达性 + 20MB 测速)**、更新。

## 说明

本仓库通过 GitHub Actions **每 4 小时**(UTC 00/04/08/12/16/20,即北京时间 08/12/16/20/00/04 点)自动抓取多个免费节点来源,对每个来源的订阅文件做**清洗**后发布,并用 Clash.Meta (mihomo) 内核**逐个节点实测**生成 **AIO 精选**;同时把全部来源节点**直接去重合并**生成一份 **AIO 不精选**。

**不同来源的订阅文件相互独立、按来源目录分类存放,不会混淆。**

## 订阅链接

> **AIO 精选(推荐)**:全部来源的节点先测 `https://www.gstatic.com/generate_204` 判可达,再对可达节点**真实下载 20MB 文件测速**;每个节点名都带 `[x.xMB/s]` 标注,并生成多个分组标签页:

| 标签页 | 内容 |
|--------|------|
| `说明` | 来源数 / 延迟通过数 / 测速统计 / 更新时间 / 作者 |
| `⚡ 高速节点(>2MB/s)` | 实测速度 > 2MB/s 的节点(第一梯队) |
| `🏅 优质节点` | 1~2MB/s 且延迟 ≤ 1500ms(**与高速互斥**,两组不重叠) |
| `🚀 节点选择(全部精选)` | 全部通过延迟 + 测速的节点(默认出口) |
| `♻️ 自动选择` | 全部精选节点,url-test 自动选优 |
| `📦 <来源>` | **每个来源一个精选标签页**,只放该来源通过测试的节点 |

| 类型 | 直连 | ghproxy.net 镜像(国内网络) |
|------|------|------------------------------|
| **AIO 精选(推荐,实测过滤)** | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/aio/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/aio/clash.yaml |
| **AIO 不精选(直接合并全部节点)** | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/aio-all/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/aio-all/clash.yaml |

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
| NodeToolBox（每日文章页解析） | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/nodetoolbox/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/nodetoolbox/clash.yaml |
| 机场e（jichangg.world） | https://raw.githubusercontent.com/wzmwayne/proxy-node/main/output/jichangg/clash.yaml | https://ghproxy.net/github.com/wzmwayne/proxy-node/raw/main/output/jichangg/clash.yaml |

> 仅提供 Clash (Mihomo) 格式。直接复制链接到 FlClash / Clash Verge Rev / Mihomo 的订阅导入框即可。

**两种 AIO 怎么选**:

| 订阅 | 内容 | 适合 |
|------|------|------|
| `output/aio/clash.yaml`(精选) | 只保留延迟/测速通过的节点,节点名带 `[x.xMB/s]` 标注,含高速/优质/各来源分组 | 大多数用户,开箱即用 |
| `output/aio-all/clash.yaml`(不精选) | **不做延迟/带宽测试**,把所有来源节点直接去重合并,节点名不改、不含速度标注 | 想自己在客户端里测速/自选、或想看全量节点的用户 |

> 两者更新频率相同(每 4 小时一次)。**页面型来源**:NodeToolBox 与 机场e 的订阅地址按日期变化,由 `scripts/scrape_page_sources.py`
> 解析每日文章页后下载。其中 `jichangg.world` 站点自 2026-10 起其订阅域名(`sub.jichange.world`)
> 已无法解析(页面也停在 10-08),当前会自动跳过;站点恢复后无需改代码即可自动接入。

## AIO 精选怎么来的

1. **合并去重**:按完整节点配置(协议/服务器/端口/凭据)去重,忽略节点名;
2. **可达性**:内核 REST API 逐节点请求 `generate_204`(默认 5s 超时),不可达即淘汰;
3. **测速(两个测试文件都测 + 加权平均)**:对可达节点启动"出口绑定"监听器(`listeners` + `proxy: 节点名`),并发真实下载两个 20MB 测速文件——
   1. 本仓库 [release: test](https://github.com/wzmwayne/proxy-node/releases/tag/test) 的 `speedtest-20mb.bin`(不可压缩随机数据,权重 **0.4**);
   2. Cloudflare 的 `speed.cloudflare.com/__down?bytes=20000000`(权重 **0.6**,权重更高);

   **加权平均即为该节点的最终速度**(某个文件不可用时按剩余权重归一化,只有一个测到就用它;取不到有效数据则标 `[测速失败]`);
   每个节点在下载前会**先经同一条出口复测一次延时**(测速前测延时),该延时用于"优质节点"判定;
   速度取至少 0.2s 采样窗口的持续吞吐(`--speed-min-window`),瞬时突发不会被当成高速;
   已达标即提前结束以节省流量;代理截断响应(字节数很小且耗时极短)会被判为失败,避免虚假高速度;
4. **标注与分组**:每个节点名前缀 `[x.xMB/s]`(失败标 `[测速失败]`,未测标 `[未测速]`);生成 `⚡ 高速节点(>2MB/s)`、`🏅 优质节点`(与高速互斥)、`🚀 节点选择(全部精选)`、`♻️ 自动选择`,以及**每个来源各自的 `📦 <来源>` 精选标签页**(排序:高速 → 优质 → 其余按延迟);
5. **总耗时**约 5~8 分钟(取决于来源规模与节点存活率)。

## 清洗与发布门禁

每个来源的 `clash.yaml` 在发布前都会经过 `scripts/sanitize.py` 处理,并在**内核校验通过后**才替换线上文件:

- 按 go-yaml v3 的码点白名单检查**解码后**的每个字符串值,丢弃含控制字符的节点 —— 这是 FlClash 报 `yaml: control characters are not allowed` 的根因;
- 剔除上游错误页残留的垃圾顶层键(如 `error code: 520`);
- **名称唯一性**:重复节点名/组名、节点名与组名冲突自动改名或丢弃(否则 mihomo 直接拒绝加载整份配置:`proxy xxx is the duplicate name`);
- **悬空引用修复**:丢弃节点/分组后,同步清理 `group -> proxy`、`group -> group`、`rule -> 目标` 的失效引用(否则报 `proxy group[0]: xxx: 'yyy' not found`);
- 清理 `proxy-groups` 中指向已删除节点的失效引用;空分组自动补 `DIRECT`;
- 输出为纯 ASCII YAML(非 ASCII 以 `\uXXXX` 转义,兼容所有 YAML 解析器);
- 写入前二次解析校验 + `mihomo -t` 内核门禁,任一不过即**拒绝发布并保留上一版**(不会把坏配置推给用户);
- 抓取失败/中断的来源**不会被重新盖上"更新时间"**,旧文件原样保留,时间戳即真实新鲜度。

### 手动触发参数（workflow_dispatch）

Actions → 定时抓取清洗节点 → Run workflow,可选参数:

| 参数 | 默认 | 说明 |
|------|------|------|
| `dry_run` | false | 只生成不提交(调试用) |
| `test_latency` | true | 是否测延迟/可达性;false 时跳过延迟测试 |
| `test_bandwidth` | true | 是否测带宽(20MB 文件测速);false 时跳过测速 |

- **两个都 false**:AIO **直接合并**——不测延迟/带宽、不启动 mihomo 测试,只做去重/唯一名/分组,
  分组为 `说明` / `🚀 节点选择(全部精选)` / `♻️ 自动选择` / `📦 <来源>`,节点名不加速度标注;
- **只关延迟**:跳过独立延迟测试,测速时顺带记录延时;
- **只关带宽**:保留延迟过滤,AIO 节点名标注 `[未测速]`。

对应 CLI 参数:`--merge-only`(直接合并)、`--no-delay`、`--no-speed`。

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
  nodetoolbox/ clash.yaml  # NodeToolBox 来源(页面型,清洗后)
  jichangg/ clash.yaml     # 机场e 来源(页面型,站点恢复后自动接入)
  aio/      clash.yaml     # AIO 精选(合并全部来源,经内核可达性 + 测速)
  aio-all/  clash.yaml     # AIO 不精选(全部来源直接去重合并,不做测试)
scripts/
  sources.py               # 来源清单(名称/主页/下载 URL,集中维护)
  scraper.py               # 抓取 yoyapai.com 文章并下载最新订阅
  fetch_sources.py         # 下载固定订阅地址的来源到 output/<name>/clash.raw.yaml(暂存)
  page_sources.py          # 页面型来源解析器(nodetoolbox / jichangg)
  scrape_page_sources.py   # 抓取页面型来源的最新订阅(解析每日文章页)
  sanitize.py              # 清洗(控制字符/垃圾键/重名/悬空引用)+ 内核门禁
  test_nodes.py            # 内核可达性 + 20MB 测速 + 生成 AIO
  check_sources.py         # 校验 output/ 与来源清单一致(防孤儿目录)
  make_speedtest_file.py   # 生成 20MB 测速文件(随机不可压缩,可复现)
  ensure_speedtest_asset.sh # 确保 release:test 的测速文件存在(缺失自动重建)
  install_mihomo.sh        # 安装 mihomo 内核(SHA256 校验)+ 预热地理库
  mihomo.sha256            # 内核发行包校验和
latest_urls.json           # yoyapai 最新文章信息
requirements.txt           # Python 依赖(固定版本)
.github/workflows/scrape.yml
```

## 本地运行

```bash
pip install -r requirements.txt
bash scripts/install_mihomo.sh                 # 下载并校验 mihomo(可用 MIHOMO_BIN 覆盖)

python scripts/scraper.py                      # 抓 yoyapai -> output/yoyapai/clash.raw.yaml
python scripts/fetch_sources.py                # 抓固定订阅地址的来源 -> output/<name>/clash.raw.yaml
python scripts/scrape_page_sources.py -v       # 抓页面型来源(每日文章页解析),--dry-run 可先看解析结果

# 清洗单个来源(带内核门禁;--gate 需要 mihomo 与网络)
python scripts/sanitize.py output/yoyapai/clash.raw.yaml output/yoyapai/clash.yaml \
  --source yoyapai --gate --mihomo "$MIHOMO_BIN" --mihomo-dir .cache/geo

# 可达性 + 测速 + 生成 AIO
python scripts/test_nodes.py output/*/clash.yaml -o output/aio/clash.yaml \
  --concurrency 96 --speed-concurrency 48 --fast-threshold 2.0 -v

python scripts/check_sources.py                # 来源清单一致性
```

常用调参:`--no-speed` 跳过测速;`--no-delay` 跳过延迟测试;`--merge-only` 完全不测直接合并;
`--limit N` 只测前 N 个节点(调试);
`--speed-url` 自定义测速文件(逗号分隔可多个,全部会被测);
`--speed-weight-cloudflare` / `--speed-weight-release` 调整加权平均权重(默认 0.6 / 0.4);
`--speed-min-bytes` 截断判定阈值;`--speed-latency-timeout` 测速前延时复测超时;
`--speed-max-nodes N` 限制测速节点数;`--speed-timeout` / `--speed-bytes` 控制单节点测速开销。

### 测速文件(release: test)

测速文件由脚本确定性生成(20,000,000 字节随机数据,内容可复现),发布在 release `test`:

```bash
python scripts/make_speedtest_file.py -o speedtest-20mb.bin     # 生成
gh release create test speedtest-20mb.bin --title test          # 首次发布
gh release upload test speedtest-20mb.bin --clobber             # 重新发布

# 或一条命令确保资产存在(CI 每次运行都会执行,缺失时自动重建)
GH_TOKEN=xxx bash scripts/ensure_speedtest_asset.sh
```

工作流在测速前会调用 `ensure_speedtest_asset.sh` 检查该资产,缺失则自动重新生成并上传(失败也不影响整轮,会自动换用 Cloudflare 文件)。

### 国内加速(GH_PROXY)

国内直连 GitHub 不稳时,设置 `GH_PROXY` 让**抓取节点文件 / 下载内核**走镜像(实测可用 ghproxy.net):

```bash
export GH_PROXY=https://ghproxy.net
bash scripts/install_mihomo.sh      # 内核下载走镜像(仍校验 SHA256)
python scripts/fetch_sources.py     # 各来源订阅走镜像,失败自动回退直连
```

> **注意:节点测速不走镜像。** 测速必须让节点直连真实测试文件(本仓库 release 资产 + Cloudflare),
> 否则测到的是镜像链路速度而不是节点速度。CI 上不设置 `GH_PROXY`,全程直连。

## 国内本地使用（测"国内可用"的节点）

在**国内网络**的电脑/手机上直接跑，一条命令得到一份"国内视角"的订阅：

```bash
python scripts/local_test_cn.py             # 全流程：抓取(ghproxy) -> 清洗 -> 本机实测 -> AIO
python scripts/local_test_cn.py --no-fetch  # 跳过抓取，直接测仓库里已发布的 output/*/clash.yaml
                                            # （等价于"线上订阅在国内哪些可用"）
```

- GitHub 节点文件默认走 `GH_PROXY=https://ghproxy.net`，**不需要代理**；可用 `--gh-proxy` / `--no-gh-proxy` 覆盖；
- **节点测速始终直连**（release:test 的 20MB 文件 + Cloudflare 文件），不走镜像，否则测到的是镜像速度；
- 默认输出 `output/aio/clash-cn.yaml`（已 gitignore，不会提交），节点名带 `[x.xMB/s]`，说明节点会标注 `说明-测试网络: 国内本地网络`；
- 省流量/快速验证：`--limit 300`（只测前 300 个）+ `--speed-max-nodes 80`（只测速 80 个）；
- 想直接测某个订阅文件：`python scripts/local_test_cn.py --input 订阅.yaml`；
- 国内网络下很多免费节点到 GitHub/Cloudflare 的 20MB 文件本身就不通（会被判 `[测速失败]`），这是真实结果；
- **国内模式**：加 `--cn-speed` 会改用「国内镜像大文件 + Cloudflare」做测速目标（仍直连、不走 ghproxy），
  实测同一批节点到华为云镜像均值 2.0MB/s、到 Cloudflare 只有 0.2MB/s，国内模式更能反映"国内可用速度"：

  ```bash
  python scripts/local_test_cn.py --no-fetch --cn-speed --speed-max-nodes 200
  python scripts/local_test_cn.py --input 线上AIO.yaml --cn-speed      # 测线上订阅在国内的可用性
  ```

- 如需换/加测速文件：`--speed-url "https://你的文件,https://..."`（仍要求直连，不走镜像）；
- 需要内核时脚本会自动下载（走 ghproxy + SHA256 校验），也可用 `MIHOMO_BIN` 指定已有内核。

## 安全提示

- 所有节点均来自**第三方公开来源**,服务器不受本项目控制,请勿用于登录敏感账号或传输隐私数据;
- AIO 中相当比例的 `http` / `socks5` 节点为明文传输,仅建议用于公开内容访问;
- 本仓库只做格式清洗与可用性/速度实测,**不校验节点运营方的任何行为**。

## License

放弃所有权利（Unlicense / 公有领域）,可自由取用、修改与再分发,见 [LICENSE](LICENSE)。
