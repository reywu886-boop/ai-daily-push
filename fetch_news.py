"""
AI 日报 - 热点新闻抓取模块
从多个来源抓取当日 AI 行业热点事件
支持 Kimi LLM 中文翻译
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
import time
import sys
import io
import os

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


# ---- Kimi 新闻翻译 ----

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_MODEL = "moonshot-v1-32k"
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

NEWS_TRANSLATE_PROMPT = """你是一位专业的科技新闻翻译和编辑。请将以下英文 AI 新闻翻译成中文。

要求：
1. 翻译要准确、流畅，符合中文科技新闻的行文风格
2. 公司名称保留英文（如 OpenAI、Google、Meta 等）
3. 专业术语可以中英对照（如 "大语言模型（LLM）"）
4. 如果描述太长，请精简到 2-3 句话的核心信息
5. 在翻译后，用一句话补充说明这条新闻对 AI 行业/产品的影响意义（以"💡 "开头）

请严格按以下格式输出每条新闻，用 "---" 分隔：
中文标题：xxx
中文描述：xxx
💡 xxx
---
"""


def translate_news_batch(news_items, max_retries=2):
    """用 Kimi 批量翻译新闻标题和描述"""
    if not KIMI_API_KEY or not news_items:
        return news_items
    
    # 构建输入
    input_parts = []
    for i, item in enumerate(news_items, 1):
        title = item.get("title", "")
        desc = item.get("description", "")
        input_parts.append(f"新闻 {i}:\nTitle: {title}\nDescription: {desc}")
    
    user_input = "\n\n".join(input_parts)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}",
    }
    
    payload = {
        "model": KIMI_MODEL,
        "messages": [
            {"role": "system", "content": NEWS_TRANSLATE_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.3,
        "max_tokens": 3000,
    }
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                KIMI_API_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            result_text = data["choices"][0]["message"]["content"]
            
            # 解析翻译结果
            blocks = re.split(r'\n---\n?', result_text)
            for i, block in enumerate(blocks):
                if i >= len(news_items):
                    break
                
                title_match = re.search(r'中文标题[：:]\s*(.+)', block)
                desc_match = re.search(r'中文描述[：:]\s*(.+)', block)
                insight_match = re.search(r'💡\s*(.+)', block)
                
                if title_match:
                    news_items[i]["title_zh"] = title_match.group(1).strip()
                if desc_match:
                    news_items[i]["desc_zh"] = desc_match.group(1).strip()
                if insight_match:
                    news_items[i]["insight"] = insight_match.group(1).strip()
            
            print(f"  ✓ 新闻翻译完成（{len(blocks)} 条）")
            return news_items
            
        except Exception as e:
            if attempt < max_retries:
                wait = 5 * (attempt + 1)
                print(f"  [WARN] 新闻翻译失败，{wait}s 后重试: {e}")
                time.sleep(wait)
            else:
                print(f"  [ERROR] 新闻翻译最终失败: {e}")
                return news_items
    
    return news_items


def format_news_report(news, max_items=5):
    """格式化热点新闻报告（含中文翻译）"""
    if not news:
        return "今日暂无重大 AI 热点。"
    
    # 按重要度排序
    scored = [(score_news(item), item) for item in news]
    scored.sort(key=lambda x: -x[0])
    
    top_news = [item for _, item in scored[:max_items]]
    
    # 用 Kimi 批量翻译
    if KIMI_API_KEY:
        print("  → 调用 Kimi 翻译新闻...")
        top_news = translate_news_batch(top_news)
    
    lines = []
    for i, item in enumerate(top_news, 1):
        title = item.get("title", "")
        title_zh = item.get("title_zh", "")
        desc = item.get("description", "")
        desc_zh = item.get("desc_zh", "")
        insight = item.get("insight", "")
        link = item.get("link", "")
        source = item.get("source", "")
        
        # 中文标题优先，英文标题作为副标题
        if title_zh:
            lines.append(f"**{i}. {title_zh}**")
            lines.append(f"- *原文：{title}*")
        else:
            lines.append(f"**{i}. {title}**")
        
        # 中文描述优先
        if desc_zh:
            lines.append(f"- {desc_zh}")
        elif desc:
            lines.append(f"- {desc[:200]}")
        
        # 行业影响点评
        if insight:
            lines.append(f"- 💡 {insight}")
        
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
