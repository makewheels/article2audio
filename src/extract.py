"""抓取网页并提取正文。"""
import re

import requests
import trafilatura

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_article(url: str) -> dict:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    html = resp.text

    meta = trafilatura.bare_extraction(html, url=url, include_comments=False)
    if not meta or not meta.text or len(meta.text.strip()) < 100:
        raise ValueError("正文提取失败或内容过短，请手动粘贴正文")

    title = (meta.title or "").strip()
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    return {"title": title or "未命名文章", "text": meta.text.strip()}
