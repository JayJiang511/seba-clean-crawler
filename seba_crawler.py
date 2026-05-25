#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
夜蝴蝶館 seba.tw 通用小说净化爬虫

功能：
1. 输入作品关键词，例如：禁咒師、司命書、妖異奇談抄
2. 自动搜索夜蝴蝶館 WordPress 分类
3. 显示匹配分类，例如：禁咒師 I / 禁咒師 II / 禁咒師 III ...
4. 选择分类后，自动抓取该分类下所有文章
5. 自动按链接 slug 自然排序
6. 自动合并分页章节：（一）（二）（三）、（上）（下）
7. 最终章节标题只取“第X章（一）/ 楔子（上）/ 补遗页”正文开头的真正标题
8. 自动清除广告、链接、菜单、赞助、上一篇/下一篇等杂项
9. 输出合并 TXT + 分章 TXT 文件夹

安装依赖：
    pip install requests beautifulsoup4 lxml

可选增强简繁转换：
    pip install opencc-python-reimplemented

运行：
    python seba_universal_clean_crawler.py

也可以直接指定：
    python seba_universal_clean_crawler.py --term 禁咒師
    python seba_universal_clean_crawler.py --category https://seba.tw/category/fantasy-novel/incantation/incantation-2/

多选：
    在分类列表输入 1,2,3 或 1-4 或 all
    也可以命令行传多个分类链接：
    python seba_universal_clean_crawler.py --category 链接1 链接2 链接3

输出模式：
    选择完分类后可选择：只要合并TXT / 只要分章文件夹 / 两者都要
    也可以命令行指定：
    python seba_universal_clean_crawler.py --term 禁咒师 --mode merged
    python seba_universal_clean_crawler.py --term 禁咒师 --mode split
    python seba_universal_clean_crawler.py --term 禁咒师 --mode both
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://seba.tw"
SLEEP_SECONDS = 1.0
MAX_PAGES = 500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

CHINESE_NUM = r"[一二三四五六七八九十百零〇]+"
PART_MARK = r"[上下一二三四五六七八九十百零〇]+"

STOP_KEYWORDS = [
    "感謝您",
    "若您願意支持blog的持續營運",
    "小額贊助說明",
    "感謝贊助我們的網站運作費用",
    "歡迎餵食",
    "詳情請見說明",
    "Posted in",
    "上一篇",
    "下一篇",
    "發佈留言",
    "留言",
    "搜尋",
    "近期文章",
    "近期留言",
    "分類",
    "標籤",
    "友情推薦",
    "個人誌賣貨便",
    "電子書讀墨",
    "文章搜尋",
    "文章分類",
    "認真寫作小夥伴",
    "我們需要乾爹",
    "海外朋友Paypal贊助",
    "蝴蝶館小市集",
]

REMOVE_LINES = {
    "夜蝴蝶館",
    "- 夜蝴蝶館",
    "Skip to content",
    "Menu",
    "只有故事和故事相關的事",
    "奇幻長篇",
    "近期連載",
    "長篇小說",
    "同人小說",
    "出版消息與公告",
    "啾仔",
}

AD_PATTERNS = [
    r"－\s*感謝您\s*❤?\s*若您願意支持blog的持續營運.*?詳情請見說明",
    r"感謝您\s*❤?\s*若您願意支持blog的持續營運.*?詳情請見說明",
    r"若您願意支持blog的持續營運.*?詳情請見說明",
    r"←?歡迎餵食.*?詳情請見說明",
    r"←?歡迎餵食（這是快速打賞連結，金額可自訂）",
    r"感謝贊助我們的網站運作費用！不管金額大小對我們而言都有莫大的鼓勵。",
]

# 简体 -> 繁体常用转换。
# 优先使用 opencc；如果没安装，则使用内置最小映射，足够覆盖“禁咒师/司命书/妖异奇谈抄”等常见搜索。
S2T_FALLBACK_MAP = str.maketrans({
    "师": "師",
    "书": "書",
    "异": "異",
    "谈": "談",
    "录": "錄",
    "与": "與",
    "殁": "歿",
    "世": "世",
    "长": "長",
    "篇": "篇",
    "说": "說",
    "话": "話",
    "网": "網",
    "爱": "愛",
    "灵": "靈",
    "猫": "貓",
    "风": "風",
    "云": "雲",
    "龙": "龍",
    "凤": "鳳",
    "药": "藥",
    "双": "雙",
    "学": "學",
    "旧": "舊",
    "梦": "夢",
    "无": "無",
    "尽": "盡",
    "间": "間",
    "抢": "搶",
    "战": "戰",
    "编": "編",
    "辑": "輯",
    "点": "點",
    "轮": "輪",
    "边": "邊",
    "缘": "緣",
    "记": "記",
    "馆": "館",
    "蝴": "蝴",
    "蝶": "蝶",
    "宫": "宮",
    "县": "縣",
    "台": "臺",
    "复": "復",
    "万": "萬",
    "归": "歸",
    "尘": "塵",
    "剑": "劍",
    "杀": "殺",
    "欢": "歡",
    "续": "續",
    "卷": "卷",
    "叁": "參",
    "肆": "肆",
    "陆": "陸",
    "柒": "柒",
    "捌": "捌",
    "玖": "玖",
    "拾": "拾",
})


COMMON_ALIAS_MAP = {
    # 手动别名：左边是用户可能输入，右边是站内常见繁体标题关键词
    "禁咒师": "禁咒師",
    "禁咒師": "禁咒師",
    "司命书": "司命書",
    "司命書": "司命書",
    "妖异奇谈抄": "妖異奇談抄",
    "妖異奇談抄": "妖異奇談抄",
    "殁世录": "歿世錄",
    "歿世錄": "歿世錄",
    "长春": "長春",
    "无尽的旅程": "無盡的旅程",
    "不停穿越": "不停穿越",
    "网络女作家之死": "網路女作家之死",
    "网路女作家之死": "網路女作家之死",
}


def simple_s2t(text: str) -> str:
    """
    简体转繁体。
    有 opencc 就用 opencc；没有也能靠内置映射跑。
    """
    text = clean_text(text)

    if not text:
        return text

    if text in COMMON_ALIAS_MAP:
        return COMMON_ALIAS_MAP[text]

    try:
        from opencc import OpenCC  # type: ignore
        return OpenCC("s2t").convert(text)
    except Exception:
        return text.translate(S2T_FALLBACK_MAP)


def build_search_terms(term: str) -> list[str]:
    """
    生成搜索词候选。
    例如输入：禁咒师
    返回：["禁咒师", "禁咒師"]
    """
    term = clean_text(term)
    terms = []

    def add(x: str):
        x = clean_text(x)
        if x and x not in terms:
            terms.append(x)

    add(term)

    if term in COMMON_ALIAS_MAP:
        add(COMMON_ALIAS_MAP[term])

    add(simple_s2t(term))

    # 去掉空格版本也试一下
    add(term.replace(" ", ""))
    add(simple_s2t(term.replace(" ", "")))

    return terms


@dataclass
class Category:
    name: str
    link: str
    count: int | None = None
    id: int | None = None


@dataclass
class PostItem:
    title: str
    link: str
    content_html: str | None = None
    id: int | None = None


def request_get(url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", 30)
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_ad_blocks(text: str) -> str:
    for pattern in AD_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.S)

    text = re.sub(r"\n\s*❤\s*\n", "\n", text)
    text = re.sub(r"\n\s*－\s*\n(?=\n|$)", "\n", text)
    return clean_text(text)


def safe_filename(name: str) -> str:
    name = clean_text(name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:100] or "未命名"


def natural_key_from_url(url: str):
    """
    按 URL slug 自然排序。
    例如：
    incantation-2
    incantation-2-2
    incantation-2-3
    ...
    """
    path = urlparse(url).path.strip("/")
    slug = path.split("/")[-1]

    parts = re.split(r"(\d+)", slug)
    key = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return key


ROMAN_MAP = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
}

FULLWIDTH_ROMAN_MAP = {
    "Ⅰ": 1,
    "Ⅱ": 2,
    "Ⅲ": 3,
    "Ⅳ": 4,
    "Ⅴ": 5,
    "Ⅵ": 6,
    "Ⅶ": 7,
    "Ⅷ": 8,
    "Ⅸ": 9,
    "Ⅹ": 10,
}

CHINESE_NUM_MAP_SIMPLE = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "壹": 1,
    "貳": 2,
    "參": 3,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陸": 6,
    "陆": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
    "拾": 10,
}


def chinese_num_to_int(s: str) -> int | None:
    """
    处理简单中文数字：一、二、十、十一、二十、二十一、壹、貳、參...
    """
    s = clean_text(s)

    if not s:
        return None

    if s in CHINESE_NUM_MAP_SIMPLE:
        return CHINESE_NUM_MAP_SIMPLE[s]

    if "十" in s or "拾" in s:
        sep = "十" if "十" in s else "拾"
        left, _, right = s.partition(sep)
        tens = CHINESE_NUM_MAP_SIMPLE.get(left, 1) if left else 1
        ones = CHINESE_NUM_MAP_SIMPLE.get(right, 0) if right else 0
        return tens * 10 + ones

    return None


def volume_number_from_name(name: str) -> int:
    """
    从分类名提取卷号，用于“禁咒師 I / II / III”这种排序。
    找不到则给一个很大的值。
    """
    name = clean_text(name)

    # 半角罗马数字
    tokens = re.findall(r"\b[IVXLCDM]+\b", name.upper())
    if tokens:
        last = tokens[-1]
        if last in ROMAN_MAP:
            return ROMAN_MAP[last]

    # 全角罗马数字
    for ch in name:
        if ch in FULLWIDTH_ROMAN_MAP:
            return FULLWIDTH_ROMAN_MAP[ch]

    # 阿拉伯数字
    nums = re.findall(r"\d+", name)
    if nums:
        return int(nums[-1])

    # 中文卷号：卷壹、卷拾貳、第一部、第二部等
    m = re.search(r"(?:卷|第)([一二三四五六七八九十壹貳參叁肆伍陸陆柒捌玖拾〇零]+)(?:部|卷)?", name)
    if m:
        n = chinese_num_to_int(m.group(1))
        if n is not None:
            return n

    return 10_000


def category_sort_key(cat: Category, search_terms: list[str] | None = None):
    """
    分类显示顺序：
    1. 名称直接命中搜索词的排前
    2. 同系列按卷号/文件名自然顺序排：I, II, III...
    3. 最后按分类 URL slug 自然排序
    """
    search_terms = search_terms or []
    name = clean_text(cat.name)

    direct_hit = 0 if any(t and t in name for t in search_terms) else 1
    vol = volume_number_from_name(name)
    url_key = natural_key_from_url(cat.link)

    return (direct_hit, vol, url_key, len(name), name)


def find_categories_by_rest(term: str) -> list[Category]:
    url = f"{BASE_URL}/wp-json/wp/v2/categories?search={quote(term)}&per_page=100"
    try:
        r = request_get(url)
        data = r.json()
    except Exception:
        return []

    out = []
    for item in data:
        name = clean_text(item.get("name", ""))
        link = item.get("link", "")
        if not name or not link:
            continue
        out.append(Category(
            name=name,
            link=link,
            count=item.get("count"),
            id=item.get("id"),
        ))

    return out


def find_categories_by_search_page(term: str) -> list[Category]:
    """
    REST 搜不到分类时的兜底：
    用站内搜索页搜，然后从链接中抓 category 链接。
    """
    url = f"{BASE_URL}/?s={quote(term)}"
    try:
        r = request_get(url)
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    seen = set()
    out = []

    for a in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, a["href"])
        text = clean_text(a.get_text(" "))

        if "/category/" not in href:
            continue

        if term not in text and term not in href:
            continue

        key = href.rstrip("/")
        if key in seen:
            continue

        seen.add(key)
        out.append(Category(name=text or key.split("/")[-1], link=href, count=None, id=None))

    return out


def find_categories(term: str) -> list[Category]:
    """
    支持简体输入。
    会把用户输入扩展成多个搜索词，例如：
    禁咒师 -> 禁咒师 / 禁咒師
    """
    search_terms = build_search_terms(term)
    print(f"\n实际搜索关键词：{' / '.join(search_terms)}")

    by_link: dict[str, Category] = {}

    for t in search_terms:
        cats = find_categories_by_rest(t)
        fallback = find_categories_by_search_page(t)

        for c in cats + fallback:
            key = c.link.rstrip("/")
            if key not in by_link:
                by_link[key] = c

    result = list(by_link.values())

    result.sort(key=lambda c: category_sort_key(c, search_terms))

    return result


def parse_multi_choice(choice: str, max_num: int) -> list[int]:
    """
    支持：
    1
    1,2,3
    1 2 3
    1-4
    all / a / 全部
    """
    choice = clean_text(choice).lower()

    if choice in {"all", "a", "全部", "全选", "全選"}:
        return list(range(1, max_num + 1))

    result: list[int] = []

    parts = re.split(r"[,，\s]+", choice)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part or "～" in part or "~" in part:
            m = re.fullmatch(r"(\d+)\s*[-~～]\s*(\d+)", part)
            if not m:
                continue

            start = int(m.group(1))
            end = int(m.group(2))

            if start > end:
                start, end = end, start

            for n in range(start, end + 1):
                if 1 <= n <= max_num and n not in result:
                    result.append(n)

        elif part.isdigit():
            n = int(part)
            if 1 <= n <= max_num and n not in result:
                result.append(n)

    return result


def choose_categories(term: str | None, category_urls: list[str] | None) -> list[Category]:
    """
    多选分类。
    - 如果传入 --category 多个链接，直接返回多个分类
    - 否则输入关键词后显示分类列表，可输入：1,2,3 / 1-4 / all
    """
    if category_urls:
        cats = []
        for url in category_urls:
            name = url.rstrip("/").split("/")[-1]
            cats.append(Category(name=name, link=url, id=None))
        return cats

    if not term:
        term = input("请输入作品关键词，例如 禁咒師 / 司命書 / 妖異奇談抄：").strip()

    if not term:
        raise SystemExit("没有输入关键词。")

    categories = find_categories(term)

    if not categories:
        print(f"没有找到分类：{term}")
        print("你可以直接运行：python seba_universal_clean_crawler.py --category 分类链接")
        raise SystemExit(1)

    print("\n找到以下分类：")
    for idx, cat in enumerate(categories, start=1):
        count_info = f" / {cat.count} 篇" if cat.count is not None else ""
        print(f"{idx:02d}. {cat.name}{count_info}")
        print(f"    {cat.link}")

    print("\n可输入：")
    print("  1          抓取第 1 个")
    print("  1,2,3      抓取多个")
    print("  1-4        抓取范围")
    print("  all        抓取全部")

    while True:
        choice = input("\n请输入要抓取的分类编号：").strip()
        numbers = parse_multi_choice(choice, len(categories))

        if numbers:
            return [categories[n - 1] for n in numbers]

        print("编号不正确，请重新输入。")


def get_category_id_from_link(category_url: str) -> int | None:
    """
    如果用户直接给分类链接，尝试通过 REST categories 列表找到对应 id。
    """
    try:
        # 获取所有分类可能很多，这里分页拿
        page = 1
        while page <= 20:
            url = f"{BASE_URL}/wp-json/wp/v2/categories?per_page=100&page={page}"
            r = request_get(url)
            data = r.json()
            if not data:
                break

            for item in data:
                link = item.get("link", "").rstrip("/")
                if link == category_url.rstrip("/"):
                    return item.get("id")

            total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
            if page >= total_pages:
                break
            page += 1
    except Exception:
        return None

    return None


def collect_posts_by_rest(category: Category) -> list[PostItem]:
    cat_id = category.id or get_category_id_from_link(category.link)
    if not cat_id:
        return []

    posts: list[PostItem] = []
    page = 1

    while page <= 50:
        url = (
            f"{BASE_URL}/wp-json/wp/v2/posts"
            f"?categories={cat_id}&per_page=100&page={page}&orderby=date&order=asc"
        )

        try:
            r = request_get(url)
        except Exception as e:
            # WordPress 页数超过时会报 rest_post_invalid_page_number
            break

        try:
            data = r.json()
        except json.JSONDecodeError:
            break

        if not data:
            break

        for item in data:
            title = clean_text(BeautifulSoup(item.get("title", {}).get("rendered", ""), "html.parser").get_text(" "))
            link = item.get("link", "")
            content_html = item.get("content", {}).get("rendered", "")

            if not title or not link:
                continue

            posts.append(PostItem(
                title=title,
                link=link,
                content_html=content_html,
                id=item.get("id"),
            ))

        total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break

        page += 1

    posts = dedupe_posts(posts)
    posts.sort(key=lambda p: natural_key_from_url(p.link))
    return posts


def collect_posts_by_archive(category_url: str) -> list[PostItem]:
    """
    REST 失败时，从分类归档页抓文章链接。
    """
    posts: list[PostItem] = []
    seen = set()

    page = 1
    while page <= 100:
        if page == 1:
            url = category_url
        else:
            url = category_url.rstrip("/") + f"/page/{page}/"

        try:
            r = request_get(url)
        except Exception:
            break

        soup = BeautifulSoup(r.text, "html.parser")

        found = 0
        for a in soup.select("article h1 a, article h2 a, h1.entry-title a, h2.entry-title a"):
            href = urljoin(BASE_URL, a.get("href", ""))
            title = clean_text(a.get_text(" "))

            if not href or not title:
                continue

            key = href.rstrip("/")
            if key in seen:
                continue

            seen.add(key)
            found += 1
            posts.append(PostItem(title=title, link=href, content_html=None))

        if found == 0:
            break

        # 找下一页；没有就停止
        next_link = None
        for a in soup.find_all("a", href=True):
            txt = clean_text(a.get_text(" "))
            if "下一頁" in txt or "下一页" in txt or "Older" in txt or "Next" in txt:
                next_link = urljoin(BASE_URL, a["href"])
                break

        if not next_link:
            break

        page += 1

    posts = dedupe_posts(posts)
    posts.sort(key=lambda p: natural_key_from_url(p.link))
    return posts


def dedupe_posts(posts: Iterable[PostItem]) -> list[PostItem]:
    seen = set()
    out = []

    for p in posts:
        key = p.link.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(p)

    return out


def get_post_html(post: PostItem) -> tuple[str, str]:
    """
    返回 page_title, content_html。
    优先用 REST content；没有时抓单篇页面。
    """
    if post.content_html:
        return post.title, post.content_html

    r = request_get(post.link)
    soup = BeautifulSoup(r.text, "html.parser")

    h1 = soup.find("h1")
    page_title = clean_text(h1.get_text(" ")) if h1 else post.title

    article = (
        soup.select_one("article")
        or soup.select_one("main article")
        or soup.select_one("main")
        or soup.select_one("#content article")
        or soup.select_one("#content")
    )

    if not article:
        raise RuntimeError(f"找不到文章区域：{post.link}")

    for tag in article.select(
        "script, style, noscript, iframe, nav, footer, form, "
        ".post-navigation, .navigation, .nav-links, .sharedaddy, "
        ".jp-relatedposts, .comments-area, .comment-respond, "
        ".entry-footer, .post-meta, .meta, .tags-links, .cat-links"
    ):
        tag.decompose()

    return page_title, str(article)


def get_logic_label_from_page_title(page_title: str) -> str:
    """
    用网页标题判断逻辑章节。
    通用做法：
    - 删除末尾分页标记：（一）（二）（上）（下）
    - 如果含“第X章”，用“第X章”作为逻辑分组
    - 如果含“楔子”，用“楔子”
    - 如果含“補遺”，保留为独立逻辑组
    - 否则用去掉分页后的网页标题自身
    """
    title = clean_text(page_title)
    title_no_part = re.sub(rf"（{PART_MARK}）", "", title)
    title_no_part = clean_text(title_no_part)

    if "楔子" in title_no_part:
        return extract_prefix_context(title_no_part, "楔子")

    m = re.search(rf"(第{CHINESE_NUM}章)\s*(補遺)?", title_no_part)
    if m:
        label = m.group(1)
        if m.group(2):
            label += " 補遺"
        return label

    return title_no_part


def extract_prefix_context(title: str, keyword: str) -> str:
    # 对楔子一般直接用“楔子”；不带系列前缀
    return keyword


def get_part_mark_from_page_title(page_title: str) -> str | None:
    m = re.search(rf"（({PART_MARK})）", page_title)
    if m:
        return m.group(1)
    return None


def is_title_source_page(page_title: str, logic_label: str) -> bool:
    """
    允许提取最终标题的页面：
    - 楔子（上）或无分页楔子
    - 第X章（一）或无分页章页面
    - 第X章 補遺页面
    """
    mark = get_part_mark_from_page_title(page_title)

    if logic_label == "楔子":
        return mark in {"上", None}

    if logic_label.endswith("補遺"):
        return True

    if re.fullmatch(rf"第{CHINESE_NUM}章", logic_label):
        return mark in {"一", None}

    # 非“第X章”结构的单篇文章，直接用自己的标题源
    return mark in {"一", "上", None}


def is_plain_chapter_number(line: str) -> bool:
    return bool(re.fullmatch(rf"第{CHINESE_NUM}章", clean_text(line)))


def is_any_heading_line(line: str) -> bool:
    line = clean_text(line)

    if line == "楔子":
        return True

    if re.fullmatch(r"楔子\s+.+", line):
        return True

    if re.fullmatch(rf"第{CHINESE_NUM}章", line):
        return True

    if re.fullmatch(rf"第{CHINESE_NUM}章\s*補遺", line):
        return True

    if re.fullmatch(rf"第{CHINESE_NUM}章補遺", line):
        return True

    if re.fullmatch(rf"第{CHINESE_NUM}章\s+.+", line):
        return True

    return False


def looks_like_title_tail(line: str) -> bool:
    line = clean_text(line)

    if not line:
        return False

    if is_any_heading_line(line):
        return False

    if any(k in line for k in STOP_KEYWORDS):
        return False

    if line.startswith("「") or line.startswith("『"):
        return False

    return len(line) <= 40


def html_to_clean_lines(content_html: str, page_title: str | None = None) -> list[str]:
    soup = BeautifulSoup(content_html, "html.parser")

    for tag in soup.select(
        "script, style, noscript, iframe, nav, footer, form, "
        ".post-navigation, .navigation, .nav-links, .sharedaddy, "
        ".jp-relatedposts, .comments-area, .comment-respond, "
        ".entry-footer, .post-meta, .meta, .tags-links, .cat-links"
    ):
        tag.decompose()

    text = clean_text(soup.get_text("\n"))
    raw_lines = [clean_text(x) for x in text.splitlines() if clean_text(x)]

    lines = []
    for line in raw_lines:
        if page_title and line == page_title:
            continue

        if line in REMOVE_LINES:
            continue

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
            continue

        if any(keyword in line for keyword in STOP_KEYWORDS):
            break

        if line.startswith("http://") or line.startswith("https://"):
            continue

        if line.startswith("原文："):
            continue

        if line in {"---", "* * *"}:
            continue

        lines.append(line)

    return lines


def extract_final_title_from_source_page(logic_label: str, page_title: str, lines: list[str]) -> tuple[str | None, set[int]]:
    """
    从标题源页面正文开头提取最终标题。
    重点：如果第X章（一）下面是“第二章 xxx（續）”，也保留为最终标题。
    """
    consumed: set[int] = set()
    window = lines[:12]

    if logic_label == "楔子":
        for idx, line in enumerate(window):
            line = clean_text(line)

            if line.startswith("楔子") and line != "楔子":
                consumed.add(idx)
                return line, consumed

            if line == "楔子":
                consumed.add(idx)
                if idx + 1 < len(window) and looks_like_title_tail(window[idx + 1]):
                    consumed.add(idx + 1)
                    return f"楔子 {clean_text(window[idx + 1])}", consumed
                return "楔子", consumed

        return None, consumed

    if logic_label.endswith("補遺"):
        for idx, line in enumerate(window):
            line = clean_text(line)
            if re.fullmatch(rf"第{CHINESE_NUM}章\s*補遺", line) or re.fullmatch(rf"第{CHINESE_NUM}章補遺", line):
                consumed.add(idx)
                return re.sub(r"(章)(補遺)", r"\1 補遺", line), consumed
        return logic_label, consumed

    # 第X章类
    if re.fullmatch(rf"第{CHINESE_NUM}章", logic_label):
        for idx, line in enumerate(window):
            line = clean_text(line)

            # 一整行标题：第二章 啟程前往九天之上（續）
            if line.startswith(logic_label + " "):
                consumed.add(idx)
                return line, consumed

            # 分两行标题
            if line == logic_label:
                consumed.add(idx)
                if idx + 1 < len(window) and looks_like_title_tail(window[idx + 1]):
                    consumed.add(idx + 1)
                    return f"{logic_label} {clean_text(window[idx + 1])}", consumed
                return logic_label, consumed

        return None, consumed

    # 非第X章结构：如果正文第一行像标题，用它；否则用网页标题清理分页
    if window:
        first = clean_text(window[0])
        if first and len(first) <= 60 and not first.startswith("「"):
            consumed.add(0)
            return first, consumed

    fallback = re.sub(rf"（{PART_MARK}）", "", page_title)
    return clean_text(fallback), consumed


def remove_inline_headings(lines: list[str], consumed_title_indexes: set[int]) -> list[str]:
    cleaned = []

    for idx, line in enumerate(lines):
        line = clean_text(line)

        if not line:
            continue

        if idx in consumed_title_indexes:
            continue

        if is_any_heading_line(line):
            continue

        cleaned.append(line)

    return cleaned


def crawl_posts(posts: list[PostItem], work_name: str) -> OrderedDict:
    chapters: OrderedDict[str, dict] = OrderedDict()

    for idx, post in enumerate(posts, start=1):
        print(f"\n[{idx}/{len(posts)}] 正在处理：{post.title}")
        print(f"链接：{post.link}")

        try:
            page_title, content_html = get_post_html(post)
            logic_label = get_logic_label_from_page_title(page_title)
            part_mark = get_part_mark_from_page_title(page_title)
            lines = html_to_clean_lines(content_html, page_title=page_title)

            title_from_page = None
            consumed_indexes: set[int] = set()

            if logic_label not in chapters and is_title_source_page(page_title, logic_label):
                title_from_page, consumed_indexes = extract_final_title_from_source_page(
                    logic_label=logic_label,
                    page_title=page_title,
                    lines=lines,
                )

            if logic_label not in chapters:
                final_title = title_from_page or re.sub(rf"（{PART_MARK}）", "", page_title).strip()
                chapters[logic_label] = {"title": final_title, "parts": []}
            else:
                final_title = chapters[logic_label]["title"]

            body_lines = remove_inline_headings(lines, consumed_indexes)
            body = clean_text(remove_ad_blocks("\n\n".join(body_lines)))

            if body:
                chapters[logic_label]["parts"].append(body)

            print(f"网页标题：{page_title}")
            print(f"逻辑章节：{logic_label}")
            print(f"分页标记：{part_mark}")
            print(f"输出标题：{final_title}")
            print(f"正文长度：{len(body)}")

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            print(f"失败：{post.link}")
            print(e)

    return chapters


def save_outputs(chapters: OrderedDict, output_name: str, output_mode: str = "both"):
    """
    output_mode:
    - merged: 只输出合并 TXT
    - split: 只输出分章 TXT 文件夹
    - both: 两者都输出
    """
    output_mode = output_mode.lower().strip()

    if output_mode not in {"merged", "split", "both"}:
        output_mode = "both"

    out_dir = Path(f"{output_name}_分章TXT")
    out_file = Path(f"{output_name}.txt")

    output_parts = []
    chapter_texts = []

    for idx, (logic_label, data) in enumerate(chapters.items(), start=1):
        title = data["title"]
        parts = data["parts"]

        full_body = clean_text(remove_ad_blocks("\n\n".join(parts)))
        chapter_text = f"{title}\n\n{full_body}".strip()
        output_parts.append(chapter_text)
        chapter_texts.append((idx, title, chapter_text))

    final_text = clean_text(remove_ad_blocks("\n\n\n".join(output_parts)))

    if output_mode in {"split", "both"}:
        out_dir.mkdir(exist_ok=True)

        # 清理旧文件，避免混入上次结果
        for old_file in out_dir.glob("*.txt"):
            old_file.unlink()

        for idx, title, chapter_text in chapter_texts:
            chapter_file = out_dir / f"{idx:02d}_{safe_filename(title)}.txt"
            chapter_file.write_text(chapter_text, encoding="utf-8")

    if output_mode in {"merged", "both"}:
        out_file.write_text(final_text, encoding="utf-8")

    print("\n=========================")
    print("完成")
    print("=========================")
    print(f"总章节数：{len(chapters)}")

    if output_mode in {"merged", "both"}:
        print(f"合并 TXT：{out_file.resolve()}")

    if output_mode in {"split", "both"}:
        print(f"分章目录：{out_dir.resolve()}")

    check_keywords = [
        "原文：",
        "https://",
        "---",
        "感謝您",
        "blog",
        "贊助",
        "歡迎餵食",
        "詳情請見說明",
        "Posted in",
        "上一篇",
        "下一篇",
        "- 夜蝴蝶館",
        "Skip to content",
        "Menu",
    ]

    print("\n残留检查：")
    for keyword in check_keywords:
        print(f"{keyword}: {final_text.count(keyword)}")

    print("\n孤立章节标题检查：")
    bad = []
    for line in final_text.splitlines():
        s = clean_text(line)
        if re.fullmatch(rf"第{CHINESE_NUM}章", s) or s == "楔子":
            bad.append(s)

    if bad:
        for item in bad[:30]:
            print(f"疑似残留：{item}")
        if len(bad) > 30:
            print(f"... 还有 {len(bad) - 30} 个")
    else:
        print("未发现孤立章节标题。")


def build_output_name(category: Category) -> str:
    name = safe_filename(category.name)
    # 更好看一点：禁咒師 II -> 禁咒師_II_净化版
    name = name.replace(" ", "_")
    return f"{name}_净化版"


def choose_output_mode(mode_arg: str | None) -> str:
    """
    选择输出模式。
    """
    aliases = {
        "1": "merged",
        "txt": "merged",
        "merged": "merged",
        "合并": "merged",
        "合集": "merged",
        "集合": "merged",

        "2": "split",
        "split": "split",
        "folder": "split",
        "分章": "split",
        "文件夹": "split",
        "資料夾": "split",

        "3": "both",
        "both": "both",
        "all": "both",
        "全部": "both",
        "都要": "both",
    }

    if mode_arg:
        key = clean_text(mode_arg).lower()
        return aliases.get(key, "both")

    print("\n请选择输出方式：")
    print("  1. 只输出合并 TXT")
    print("  2. 只输出分章 TXT 文件夹")
    print("  3. 两者都输出")
    choice = input("请输入 1 / 2 / 3，直接回车默认 3：").strip()

    if not choice:
        return "both"

    return aliases.get(clean_text(choice).lower(), "both")


def main():
    parser = argparse.ArgumentParser(description="夜蝴蝶館 seba.tw 通用小说净化爬虫")
    parser.add_argument("--term", help="作品关键词，例如：禁咒師")
    parser.add_argument(
        "--category",
        nargs="+",
        help="直接指定一个或多个分类链接，例如：--category 链接1 链接2",
    )
    parser.add_argument(
        "--output",
        help="输出文件名前缀。多选时不建议使用；使用后会自动追加序号避免覆盖。",
    )
    parser.add_argument(
        "--mode",
        choices=["merged", "split", "both", "txt", "folder"],
        help="输出模式：merged=只合并TXT，split=只分章文件夹，both=两者都要。",
    )
    args = parser.parse_args()

    categories = choose_categories(args.term, args.category)

    print("\n已选择以下分类：")
    for idx, category in enumerate(categories, start=1):
        print(f"{idx:02d}. {category.name}")
        print(f"    {category.link}")

    output_mode = choose_output_mode(args.mode)

    confirm = input("\n开始批量抓取并净化？输入 y 回车继续：").strip().lower()
    if confirm not in {"y", "yes", "是"}:
        print("已取消。")
        return

    total = len(categories)

    for idx, category in enumerate(categories, start=1):
        print("\n" + "=" * 70)
        print(f"开始处理 [{idx}/{total}]：{category.name}")
        print("=" * 70)

        posts = collect_posts_by_rest(category)
        if not posts:
            print("\nREST 获取文章失败，改用分类页面抓取...")
            posts = collect_posts_by_archive(category.link)

        if not posts:
            print(f"没有收集到文章链接，跳过：{category.name}")
            continue

        print(f"\n共收集到 {len(posts)} 篇文章。")
        print("前 10 篇预览：")
        for p in posts[:10]:
            print(f"- {p.title} | {p.link}")

        chapters = crawl_posts(posts, work_name=category.name)

        if args.output:
            if total == 1:
                output_name = args.output
            else:
                output_name = f"{args.output}_{idx:02d}_{safe_filename(category.name).replace(' ', '_')}"
        else:
            output_name = build_output_name(category)

        save_outputs(chapters, output_name, output_mode=output_mode)

    print("\n全部任务完成。")


if __name__ == "__main__":
    main()
