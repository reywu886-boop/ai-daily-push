"""
AI 日报 - 论文抓取模块
从 Hugging Face Daily Papers 和 Papers With Code 抓取当日最新论文
支持 Kimi LLM 深度解读 + 中文翻译
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re
import time
import sys
import io
import os

# 修复 Windows 终端编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def fetch_hf_daily_papers():
    """从 Hugging Face Daily Papers 抓取当日论文列表"""
    url = "https://huggingface.co/papers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    papers = []
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 查找论文卡片
        article_tags = soup.find_all("article")
        for article in article_tags[:15]:  # 取前15篇候选
            paper = {}
            
            # 提取标题和链接
            title_tag = article.find("a", class_=re.compile("line-clamp"))
            if not title_tag:
                title_tag = article.find("h3")
                if title_tag:
                    a_tag = title_tag.find("a")
                    if a_tag:
                        title_tag = a_tag
            
            if title_tag:
                paper["title"] = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href.startswith("/papers/"):
                    paper["link"] = f"https://huggingface.co{href}"
                    paper["arxiv_id"] = href.split("/")[-1]
                elif href.startswith("http"):
                    paper["link"] = href
            
            # 提取点赞数
            like_tag = article.find(string=re.compile(r"\d+"))
            # 尝试找 SVG 附近的数字（点赞）
            for span in article.find_all("span"):
                text = span.get_text(strip=True)
                if text.isdigit():
                    paper["likes"] = int(text)
                    break
            
            if paper.get("title") and paper.get("link"):
                papers.append(paper)
        
    except Exception as e:
        print(f"[WARN] HF Daily Papers 抓取失败: {e}")
    
    return papers


def fetch_paper_detail(arxiv_id):
    """从 HuggingFace 论文页获取论文详情"""
    url = f"https://huggingface.co/papers/{arxiv_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    detail = {}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取摘要
        abstract_div = soup.find("div", class_=re.compile("abstract"))
        if not abstract_div:
            # 尝试其他方式找摘要
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 200:  # 摘要通常较长
                    detail["abstract"] = text
                    break
        else:
            detail["abstract"] = abstract_div.get_text(strip=True)
        
        # 提取作者
        author_section = soup.find("div", class_=re.compile("author"))
        if author_section:
            detail["authors"] = author_section.get_text(strip=True)
        
    except Exception as e:
        print(f"[WARN] 论文详情抓取失败 {arxiv_id}: {e}")
    
    return detail


def fetch_arxiv_abstract(arxiv_id, max_retries=2):
    """从 arXiv API 获取论文摘要和作者信息"""
    api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(api_url, timeout=45)
            if resp.status_code == 429:
                wait_time = 5 * (attempt + 1)
                print(f"    arXiv 限速，等待 {wait_time}s 后重试...")
                time.sleep(wait_time)
                continue
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "xml")
            
            entry = soup.find("entry")
            if entry:
                result = {}
                
                title = entry.find("title")
                if title:
                    result["title"] = title.get_text(strip=True)
                
                summary = entry.find("summary")
                if summary:
                    result["abstract"] = summary.get_text(strip=True)
                
                authors = entry.find_all("author")
                if authors:
                    author_names = [a.find("name").get_text(strip=True) for a in authors if a.find("name")]
                    result["authors"] = ", ".join(author_names)
                    result["author_count"] = len(author_names)
                
                # 提取机构（从 affiliation 标签）
                affiliations = set()
                for author in authors:
                    aff = author.find("affiliation")
                    if aff:
                        affiliations.add(aff.get_text(strip=True))
                if affiliations:
                    result["institutions"] = ", ".join(affiliations)
                
                # 提取分类
                categories = entry.find_all("category")
                if categories:
                    result["categories"] = [c.get("term", "") for c in categories]
                
                # 提取日期
                published = entry.find("published")
                if published:
                    result["published"] = published.get_text(strip=True)[:10]
                
                return result
        except Exception as e:
            if attempt < max_retries:
                print(f"    重试 {attempt + 1}/{max_retries}...")
                time.sleep(3)
            else:
                print(f"[WARN] arXiv API 查询失败 {arxiv_id}: {e}")
    
    return {}


def fetch_pwc_trending():
    """从 Papers With Code 抓取热门论文"""
    url = "https://paperswithcode.com/latest"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    papers = []
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 查找论文条目
        items = soup.find_all("div", class_=re.compile("paper-card|row.*infinite-item"))
        for item in items[:10]:
            paper = {}
            
            title_tag = item.find("a", class_=re.compile("paper-title"))
            if not title_tag:
                h1 = item.find("h1")
                if h1:
                    title_tag = h1.find("a")
            
            if title_tag:
                paper["title"] = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                if href:
                    paper["link"] = f"https://paperswithcode.com{href}" if href.startswith("/") else href
            
            if paper.get("title"):
                papers.append(paper)
    
    except Exception as e:
        print(f"[WARN] PwC Trending 抓取失败: {e}")
    
    return papers


def collect_papers():
    """汇总所有来源的论文，去重并按相关度排序"""
    print("📚 开始抓取论文...")
    
    # 1. HuggingFace Daily Papers
    print("  → 抓取 HuggingFace Daily Papers...")
    hf_papers = fetch_hf_daily_papers()
    print(f"  ✓ 获取 {len(hf_papers)} 篇")
    
    # 2. Papers With Code
    print("  → 抓取 Papers With Code Trending...")
    pwc_papers = fetch_pwc_trending()
    print(f"  ✓ 获取 {len(pwc_papers)} 篇")
    
    # 3. 获取详情（对 HF 论文补充 arXiv 信息）
    all_papers = []
    seen_titles = set()
    
    for p in hf_papers:
        if p["title"].lower() in seen_titles:
            continue
        seen_titles.add(p["title"].lower())
        
        arxiv_id = p.get("arxiv_id", "")
        if arxiv_id:
            print(f"  → 获取详情: {arxiv_id}...")
            arxiv_info = fetch_arxiv_abstract(arxiv_id)
            p.update(arxiv_info)
            time.sleep(3)  # arXiv API 建议间隔 3 秒
        
        p["source"] = "HuggingFace"
        all_papers.append(p)
    
    for p in pwc_papers:
        if p["title"].lower() in seen_titles:
            continue
        seen_titles.add(p["title"].lower())
        p["source"] = "PapersWithCode"
        all_papers.append(p)
    
    return all_papers


def classify_paper(paper):
    """根据标题和分类判断论文方向"""
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    categories = paper.get("categories", [])
    text = title + " " + abstract
    
    # 视频生成/理解
    if any(kw in text for kw in ["video generat", "video diffus", "video edit", "video world",
                                   "multi-shot video", "video agent", "video understand",
                                   "4d", "dynamic scene", "world model"]):
        return "🎬 视频生成与世界模型"
    
    # 多模态
    if any(kw in text for kw in ["multimodal", "multi-modal", "vision-language", "vision language",
                                   "vlm", "visual question", "visual reasoning",
                                   "image-text", "cross-modal"]):
        return "🎯 多模态理解与生成"
    
    # 图像生成/编辑
    if any(kw in text for kw in ["image generat", "image edit", "image restor", "diffusion",
                                   "gan", "face edit", "expression edit", "style transfer",
                                   "super resolution", "inpainting"]):
        return "🎨 图像生成与编辑"
    
    # Agent
    if any(kw in text for kw in ["agent", "gui", "computer use", "tool use", "planning"]):
        return "🤖 AI Agent"
    
    # LLM/NLP
    if any(kw in text for kw in ["language model", "llm", "reasoning", "rlhf", "instruction",
                                   "alignment", "self-distill", "fine-tun", "prompt"]):
        return "🧠 LLM 与训练"
    
    # RAG/检索
    if any(kw in text for kw in ["retrieval", "rag", "knowledge", "embedding"]):
        return "🔍 RAG 与检索"
    
    return "📄 其他方向"


def fetch_arxiv_html_content(arxiv_id, max_retries=2):
    """
    尝试从 arXiv HTML 版本获取论文正文的前几段（引言部分）
    这样可以给 LLM 更多上下文来生成深度解读
    """
    html_url = f"https://arxiv.org/html/{arxiv_id}v1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(html_url, headers=headers, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                
                # 提取正文段落（引言和方法部分）
                paragraphs = []
                for section in soup.find_all(["section", "div"]):
                    # 找到 Introduction 或前几个 section
                    heading = section.find(["h2", "h3", "h4"])
                    if heading:
                        heading_text = heading.get_text(strip=True).lower()
                        if any(kw in heading_text for kw in 
                               ["introduction", "related", "method", "approach", "overview"]):
                            for p in section.find_all("p"):
                                text = p.get_text(strip=True)
                                if len(text) > 50:
                                    paragraphs.append(text)
                                if len(paragraphs) >= 6:
                                    break
                    if len(paragraphs) >= 6:
                        break
                
                # 如果没找到 section，直接取前面的段落
                if not paragraphs:
                    for p in soup.find_all("p"):
                        text = p.get_text(strip=True)
                        if len(text) > 80:
                            paragraphs.append(text)
                        if len(paragraphs) >= 5:
                            break
                
                if paragraphs:
                    content = "\n\n".join(paragraphs)
                    # 限制长度，避免 token 过多
                    if len(content) > 4000:
                        content = content[:4000] + "..."
                    return content
            
            return None
            
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2)
            else:
                print(f"    [WARN] arXiv HTML 获取失败 {arxiv_id}: {e}")
                return None
    return None


# ---- Kimi LLM 深度解读 ----

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_MODEL = "moonshot-v1-32k"
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

ANALYSIS_PROMPT = """你是一位资深的 AI 行业分析师，你的读者是一位非技术出身但长期深度关注 AI 领域的产品经理。
她对 Transformer、Diffusion、RLHF、RAG、Agent、LoRA 等常见概念已有基本了解，不需要从零解释这些术语，但需要你在用到更细分的技术概念时做简短说明。

请阅读以下论文信息，然后写一份解读报告。

要求：
1. 先给出论文标题的中文翻译
2. 用一句话概括这篇论文在做什么（不超过30字）
3. 写 3-5 段的深度解读，包括：
   - **研究背景**：这篇论文要解决的是什么问题？为什么这个问题重要？当前方案的痛点在哪？
   - **核心方法**：论文提出了什么新方法/框架/思路？用通俗但准确的语言解释其核心创新点。如果涉及新概念，用类比或例子帮助理解。
   - **关键结果**：论文取得了什么效果？和现有方案相比提升了多少？有没有开源？
   - **产品经理视角**：这项研究对 AI 产品（尤其是视频生成、多模态、Agent、内容创作等方向）有什么启示？是否有近期产品化的可能？对竞品格局有何影响？
4. 语气：专业但不晦涩，像同事之间讨论技术趋势，不要用"本文"这种论文腔

格式要求（严格遵守）：
📌 **中文标题**：xxx
💡 **一句话概括**：xxx

**研究背景**
xxx

**核心方法**
xxx

**关键结果**
xxx

**产品启示**
xxx
"""


def call_kimi_api(prompt, content, max_retries=2):
    """调用 Kimi API 生成内容"""
    if not KIMI_API_KEY:
        return None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIMI_API_KEY}",
    }
    
    payload = {
        "model": KIMI_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
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
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < max_retries:
                wait = 5 * (attempt + 1)
                print(f"    [WARN] Kimi API 调用失败，{wait}s 后重试: {e}")
                time.sleep(wait)
            else:
                print(f"    [ERROR] Kimi API 调用最终失败: {e}")
                return None
    return None


def generate_deep_analysis(paper):
    """
    用 Kimi LLM 为论文生成深度解读报告
    会尝试获取论文正文（HTML版）来提供更丰富的上下文
    """
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    authors = paper.get("authors", "")
    institutions = paper.get("institutions", "")
    arxiv_id = paper.get("arxiv_id", "")
    categories = paper.get("categories", [])
    
    if not abstract:
        return None
    
    # 尝试获取论文正文（引言部分）
    extra_content = ""
    if arxiv_id:
        print(f"    → 尝试获取论文正文...")
        html_content = fetch_arxiv_html_content(arxiv_id)
        if html_content:
            extra_content = f"\n\n--- 论文正文节选（引言/方法）---\n{html_content}"
            print(f"    ✓ 获取到正文 {len(html_content)} 字符")
        else:
            print(f"    → 无 HTML 版本，使用摘要")
    
    # 构建输入
    user_input = f"""论文标题：{title}
作者：{authors}
机构：{institutions}
分类：{', '.join(categories) if categories else 'N/A'}
arXiv ID：{arxiv_id}

摘要（Abstract）：
{abstract}{extra_content}"""

    print(f"    → 调用 Kimi 生成深度解读...")
    analysis = call_kimi_api(ANALYSIS_PROMPT, user_input)
    
    if analysis:
        print(f"    ✓ 解读生成完成（{len(analysis)} 字符）")
    
    return analysis


def generate_fallback_analysis(paper):
    """当 Kimi API 不可用时的备用解读（简化版翻译+摘要）"""
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    
    if not abstract:
        return "暂无摘要信息。"
    
    # 用 Google Translate 做基础翻译
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        # 翻译标题
        params = {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": title}
        resp = requests.get(url, params=params, timeout=15)
        title_zh = "".join(item[0] for item in resp.json()[0] if item[0])
        
        # 翻译摘要
        short_abstract = abstract[:1500]
        params["q"] = short_abstract
        resp = requests.get(url, params=params, timeout=15)
        abstract_zh = "".join(item[0] for item in resp.json()[0] if item[0])
        
        return f"📌 **中文标题**：{title_zh}\n\n**摘要翻译**：{abstract_zh}\n\n*（注：LLM 深度解读暂不可用，显示翻译版摘要）*"
    except Exception:
        return f"摘要：{abstract[:500]}..."


def format_papers_report(papers, max_papers=10):
    """格式化论文报告"""
    if not papers:
        return "今日暂无符合条件的新论文。"
    
    # 分类
    categorized = {}
    for p in papers[:max_papers]:
        cat = classify_paper(p)
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(p)
    
    # 定义方向优先级
    priority = [
        "🎯 多模态理解与生成",
        "🎬 视频生成与世界模型",
        "🎨 图像生成与编辑",
        "🤖 AI Agent",
        "🧠 LLM 与训练",
        "🔍 RAG 与检索",
        "📄 其他方向",
    ]
    
    lines = []
    idx = 1
    
    has_kimi = bool(KIMI_API_KEY)
    if has_kimi:
        print("  → Kimi API 可用，将生成深度解读...")
    else:
        print("  → [WARN] 未配置 KIMI_API_KEY，使用备用翻译模式")
    
    for cat in priority:
        if cat not in categorized:
            continue
        lines.append(f"\n### {cat}\n")
        
        for p in categorized[cat]:
            title = p.get("title", "未知标题")
            authors = p.get("authors", "作者信息待补充")
            if len(authors) > 80:
                authors = authors[:80] + "..."
            institutions = p.get("institutions", "")
            abstract = p.get("abstract", "")
            link = p.get("link", "")
            likes = p.get("likes", 0)
            arxiv_id = p.get("arxiv_id", "")
            
            print(f"\n  📄 处理论文 {idx}: {title[:60]}...")
            
            # 标题
            lines.append(f"**{idx}. {title}**")
            
            # 作者和机构
            author_line = f"- **作者**：{authors}"
            if institutions:
                author_line += f" | **机构**：{institutions}"
            lines.append(author_line)
            
            # 深度解读（核心改动）
            if has_kimi and abstract:
                analysis = generate_deep_analysis(p)
                if analysis:
                    lines.append("")
                    lines.append(analysis)
                    lines.append("")
                else:
                    # Kimi 失败，用备用方案
                    fallback = generate_fallback_analysis(p)
                    lines.append(f"\n{fallback}\n")
                
                # 控制 API 调用频率
                time.sleep(2)
            elif abstract:
                fallback = generate_fallback_analysis(p)
                lines.append(f"\n{fallback}\n")
            
            # 链接
            if link:
                lines.append(f"- 🔗 **论文链接**：{link}")
            elif arxiv_id:
                lines.append(f"- 🔗 **论文链接**：https://arxiv.org/abs/{arxiv_id}")
            
            if likes:
                lines.append(f"- 🔥 {likes} 赞")
            
            lines.append("")
            lines.append("---")
            lines.append("")
            idx += 1
    
    return "\n".join(lines)


if __name__ == "__main__":
    papers = collect_papers()
    report = format_papers_report(papers)
    print("\n" + "=" * 60)
    print(report)
