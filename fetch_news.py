"""
AI 日报 - 热点新闻抓取模块
从多个来源抓取当日 AI 行业热点事件
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import time
import sys
import io

# 修复 Windows 终端编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def fetch_ai_news_aitoolly():
    """从 AIToolly 抓取当日 AI 新闻"""
    today = datetime.utcnow()
    # 尝试今天和昨天
    dates = [today.strftime("%Y-%m-%d"), (today - timedelta(days=1)).strftime("%Y-%m-%d")]
    
    news = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    for date_str in dates:
        url = f"https://aitoolly.com/ai-news/{date_str}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # 查找新闻条目
                articles = soup.find_all("article")
                if not articles:
                    articles = soup.find_all("div", class_=re.compile("news|article|card"))
                
                for article in articles[:20]:
                    item = {}
                    
                    title_tag = article.find(["h2", "h3", "h4"])
                    if title_tag:
                        a_tag = title_tag.find("a")
                        if a_tag:
                            item["title"] = a_tag.get_text(strip=True)
                            href = a_tag.get("href", "")
                            item["link"] = href if href.startswith("http") else f"https://aitoolly.com{href}"
                        else:
                            item["title"] = title_tag.get_text(strip=True)
                    
                    # 提取描述
                    desc_tag = article.find("p")
                    if desc_tag:
                        item["description"] = desc_tag.get_text(strip=True)
                    
                    item["date"] = date_str
                    
                    if item.get("title"):
                        news.append(item)
                        
        except Exception as e:
            print(f"[WARN] AIToolly 抓取失败 ({date_str}): {e}")
    
    return news


def fetch_ai_news_llmstats():
    """从 LLM Stats 抓取 AI 新闻"""
    url = "https://llm-stats.com/ai-news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    news = []
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 查找新闻条目
        for item_div in soup.find_all(["article", "div"], class_=re.compile("news|item|card"))[:15]:
            item = {}
            
            title_tag = item_div.find(["h2", "h3", "h4", "a"])
            if title_tag:
                item["title"] = title_tag.get_text(strip=True)
                if title_tag.name == "a":
                    item["link"] = title_tag.get("href", "")
            
            desc_tag = item_div.find("p")
            if desc_tag:
                item["description"] = desc_tag.get_text(strip=True)
            
            item["source"] = "LLM Stats"
            
            if item.get("title") and len(item["title"]) > 10:
                news.append(item)
                
    except Exception as e:
        print(f"[WARN] LLM Stats 抓取失败: {e}")
    
    return news


def fetch_tech_news_rss():
    """从 RSS 源抓取科技/AI 新闻"""
    rss_feeds = [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/features"),
        ("AI News", "https://www.artificialintelligence-news.com/feed/"),
    ]
    
    news = []
    today = datetime.utcnow()
    cutoff = today - timedelta(days=2)
    
    for source_name, feed_url in rss_feeds:
        try:
            resp = requests.get(feed_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "xml")
            
            items = soup.find_all("item")[:10]
            for item in items:
                title = item.find("title")
                link = item.find("link")
                desc = item.find("description")
                pub_date = item.find("pubDate")
                
                entry = {
                    "source": source_name,
                    "title": title.get_text(strip=True) if title else "",
                    "link": link.get_text(strip=True) if link else "",
                    "description": "",
                }
                
                if desc:
                    # 清理 HTML 标签
                    desc_text = BeautifulSoup(desc.get_text(), "html.parser").get_text(strip=True)
                    entry["description"] = desc_text[:200]
                
                # AI 相关过滤
                text = (entry["title"] + " " + entry["description"]).lower()
                ai_keywords = ["ai", "artificial intelligence", "machine learning", "llm",
                             "chatgpt", "openai", "anthropic", "google", "meta", "model",
                             "neural", "deep learning", "agent", "robot"]
                
                if any(kw in text for kw in ai_keywords) and entry["title"]:
                    news.append(entry)
                    
        except Exception as e:
            print(f"[WARN] RSS 抓取失败 ({source_name}): {e}")
    
    return news


def web_search_ai_news(serper_api_key):
    """使用 Serper API 搜索最新 AI 新闻（备用方案）"""
    if not serper_api_key:
        return []
    
    today = datetime.utcnow()
    query = f"AI news today {today.strftime('%B %d %Y')} model release announcement trending"
    
    try:
        resp = requests.post(
            "https://google.serper.dev/news",
            json={"q": query, "num": 10},
            headers={"X-API-KEY": serper_api_key},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        
        news = []
        for item in data.get("news", []):
            news.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "description": item.get("snippet", ""),
                "source": item.get("source", "Web Search"),
                "date": item.get("date", ""),
            })
        return news
        
    except Exception as e:
        print(f"[WARN] Serper 搜索失败: {e}")
        return []


def collect_news(serper_api_key=None):
    """汇总所有来源的新闻，去重"""
    print("🔥 开始抓取 AI 热点新闻...")
    
    all_news = []
    seen_titles = set()
    
    # 1. AIToolly
    print("  → 抓取 AIToolly...")
    aitoolly_news = fetch_ai_news_aitoolly()
    print(f"  ✓ 获取 {len(aitoolly_news)} 条")
    
    # 2. RSS 源
    print("  → 抓取 RSS 新闻源...")
    rss_news = fetch_tech_news_rss()
    print(f"  ✓ 获取 {len(rss_news)} 条")
    
    # 3. Serper 搜索（可选）
    if serper_api_key:
        print("  → 搜索引擎补充...")
        search_news = web_search_ai_news(serper_api_key)
        print(f"  ✓ 获取 {len(search_news)} 条")
    else:
        search_news = []
    
    # 去重合并
    for item in aitoolly_news + rss_news + search_news:
        title_key = item.get("title", "").lower().strip()
        if title_key and title_key not in seen_titles and len(title_key) > 10:
            seen_titles.add(title_key)
            all_news.append(item)
    
    return all_news


def score_news(item):
    """给新闻打分，越高越重要"""
    score = 0
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    
    # 重大公司
    major_companies = ["openai", "google", "anthropic", "meta", "apple", "nvidia",
                       "microsoft", "xai", "deepseek", "mistral"]
    for company in major_companies:
        if company in text:
            score += 3
    
    # 重大事件类型
    if any(kw in text for kw in ["launch", "release", "announc", "发布", "推出"]):
        score += 2
    if any(kw in text for kw in ["funding", "acqui", "billion", "融资", "收购"]):
        score += 2
    if any(kw in text for kw in ["breakthrough", "state-of-the-art", "sota", "突破"]):
        score += 2
    if any(kw in text for kw in ["open source", "开源"]):
        score += 1
    
    # 负面权重
    if any(kw in text for kw in ["opinion", "editorial", "评论"]):
        score -= 1
    
    return score


def format_news_report(news, max_items=5):
    """格式化热点新闻报告"""
    if not news:
        return "今日暂无重大 AI 热点。"
    
    # 按重要度排序
    scored = [(score_news(item), item) for item in news]
    scored.sort(key=lambda x: -x[0])
    
    lines = []
    for i, (score, item) in enumerate(scored[:max_items], 1):
        title = item.get("title", "")
        desc = item.get("description", "")
        link = item.get("link", "")
        source = item.get("source", "")
        
        lines.append(f"**{i}. {title}**")
        if desc:
            lines.append(f"- {desc[:200]}")
        if link:
            lines.append(f"- 🔗 {link}")
        if source:
            lines.append(f"- 来源：{source}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import os
    serper_key = os.environ.get("SERPER_API_KEY")
    news = collect_news(serper_key)
    report = format_news_report(news)
    print("\n" + "=" * 60)
    print(report)
