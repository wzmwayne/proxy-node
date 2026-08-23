import re
import json
import time
import html
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

BASE_URL = "https://yoyapai.com"
CATEGORY_URL = f"{BASE_URL}/category/mianfeijiedian"

# Advanced regex for node subscription links from freenode.yoyapai.com
NODE_LINK_PATTERN = re.compile(
    r'https?://freenode\.yoyapai\.com/\d{4}/\d{2}/[^"\'<>\s]+?\.(?:yaml|txt)',
    re.IGNORECASE,
)


def fetch_page(url):
    """Fetch a page with proper headers."""
    print(f"  [GET] {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_article_list(page_html):
    """Parse category page and extract article titles, excerpts, and links."""
    soup = BeautifulSoup(page_html, "html.parser")
    articles = []

    for li in soup.select("ul.wp-block-post-template > li.wp-block-post"):
        title_tag = li.select_one("h2.wp-block-post-title a")
        excerpt_tag = li.select_one(".wp-block-post-excerpt__excerpt")

        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")
        excerpt = excerpt_tag.get_text(strip=True) if excerpt_tag else ""

        articles.append({
            "title": title,
            "link": link,
            "excerpt": excerpt,
        })

    return articles


def extract_node_links(article_html):
    """Extract freenode.yoyapai.com subscription links from article page HTML."""
    # Decode HTML entities first (&#47; -> /)
    decoded = html.unescape(article_html)
    links = NODE_LINK_PATTERN.findall(decoded)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    return unique


def main():
    print("=" * 60)
    print("yoyapai.com 免费节点抓取工具")
    print("=" * 60)

    # Step 1: Fetch category listing page
    print(f"\n[1/3] 获取分类页面: {CATEGORY_URL}")
    listing_html = fetch_page(CATEGORY_URL)

    # Step 2: Parse article list
    articles = parse_article_list(listing_html)
    print(f"  -> 解析到 {len(articles)} 篇文章\n")

    # Step 3: Visit each article and extract node links
    print("[2/3] 逐篇访问文章，提取节点订阅链接...\n")
    all_results = []

    for i, article in enumerate(articles, 1):
        print(f"--- 文章 {i}/{len(articles)} ---")
        print(f"  标题: {article['title']}")
        print(f"  链接: {article['link']}")
        print(f"  摘要: {article['excerpt'][:80]}...")

        try:
            article_html = fetch_page(article["link"])
            node_links = extract_node_links(article_html)
            article["node_links"] = node_links
            all_results.append(article)

            if node_links:
                print(f"  节点链接 ({len(node_links)}个):")
                for nl in node_links:
                    print(f"    -> {nl}")
            else:
                print("  未找到节点链接")
        except Exception as e:
            print(f"  [错误] {e}")
            article["node_links"] = []
            all_results.append(article)

        print()
        time.sleep(1)  # polite delay

    # Step 4: Summary + JSON output
    print("\n" + "=" * 60)
    print("[3/3] 抓取完成 - 汇总")
    print("=" * 60)

    total_links = sum(len(a.get("node_links", [])) for a in all_results)
    print(f"  文章总数: {len(all_results)}")
    print(f"  节点链接总数: {total_links}\n")

    for i, article in enumerate(all_results, 1):
        links = article.get("node_links", [])
        status = f"{len(links)}个链接" if links else "无链接"
        print(f"  {i}. {article['title']}")
        print(f"     {article['link']} [{status}]")
        for nl in links:
            print(f"       {nl}")
    print()

    # Write latest article node links to JSON for process_nodes.py
    if all_results:
        latest = all_results[0]
        yaml_link = ""
        txt_link = ""
        for nl in latest.get("node_links", []):
            if nl.endswith(".yaml"):
                yaml_link = nl
            elif nl.endswith(".txt"):
                txt_link = nl

        # Extract date from title (e.g. "7月14日" -> "07-14")
        title = latest["title"]
        date_match = re.search(r'(\d+)月(\d+)日', title)
        date_str = ""
        if date_match:
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            date_str = f"2026-{month:02d}-{day:02d}"

        data = {
            "title": title,
            "link": latest["link"],
            "date": date_str,
            "yaml": yaml_link,
            "txt": txt_link,
        }
        with open("latest_urls.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [OK] latest_urls.json 已生成")

        # Download the latest YAML to output/yoyapai/ (raw, sanitized later)
        import os
        out_dir = os.path.join("output", "yoyapai")
        os.makedirs(out_dir, exist_ok=True)

        if yaml_link:
            print(f"  [GET] {yaml_link}")
            resp = requests.get(yaml_link, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            with open(os.path.join(out_dir, "clash.yaml"), "wb") as f:
                f.write(resp.content)
            print(f"  [OK] clash.yaml ({len(resp.content)} bytes)")
        else:
            print("  [SKIP] 无 YAML 链接")


if __name__ == "__main__":
    main()
