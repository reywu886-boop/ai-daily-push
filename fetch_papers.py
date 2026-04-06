"""
AI 日报 - 论文抓取模块
从 Hugging Face Daily Papers 和 Papers With Code 抓取当日最新论文
支持中文翻译 + 产品经理视角解读
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import re
import time
import sys
import io
import hashlib
import urllib.parse

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


def translate_to_chinese(text, max_retries=2):
    """使用 Google Translate 免费接口翻译英文到中文"""
    if not text or len(text.strip()) < 5:
        return text
    
    # 截断过长文本
    if len(text) > 3000:
        text = text[:3000] + "..."
    
    for attempt in range(max_retries + 1):
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": text,
            }
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            # 拼接翻译结果
            translated = "".join(item[0] for item in result[0] if item[0])
            return translated
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
            else:
                print(f"[WARN] 翻译失败: {e}")
                return None
    return None


def generate_pm_insight(paper):
    """
    为 AI 产品经理生成论文核心解读
    基于论文标题、摘要、分类等信息，用通俗语言解释：
    1. 这篇论文解决了什么问题
    2. 核心方法/思路是什么
    3. 对产品/行业有什么启示
    """
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "")
    abstract_lower = abstract.lower()
    categories = paper.get("categories", [])
    
    # ---- 提取关键信号 ----
    signals = []
    
    # 问题类型识别
    problem_patterns = {
        "benchmark|evaluat|assessment": "提出了新的评测基准",
        "generat|synthes|creat": "关于内容生成技术",
        "edit|manipulat|transform": "关于内容编辑/操控技术",
        "understand|recogni|detect|perceiv": "关于AI理解/识别能力",
        "accelerat|efficien|fast|compress|lightweight": "关于提升模型效率",
        "safe|align|bias|toxic|hallucin": "关于AI安全与可靠性",
        "agent|tool.use|planning|reasoning": "关于AI Agent自主能力",
        "retriev|rag|knowledge|ground": "关于知识检索增强",
        "train|fine.tun|pretrain|reinforc": "关于模型训练方法",
        "multi.modal|vision.language|cross.modal": "关于多模态能力",
        "video|temporal|motion|dynamic": "关于视频/动态内容",
        "3d|spatial|scene|reconstruct|nerf|gaussian": "关于3D/空间理解",
        "diffusion|denois|score.match": "基于扩散模型技术",
        "robot|embod|navigation|manipulat": "关于具身智能/机器人",
    }
    
    for pattern, desc in problem_patterns.items():
        if re.search(pattern, title + " " + abstract_lower):
            signals.append(desc)
    
    # ---- 构建解读 ----
    insight_parts = []
    
    # 解决什么问题
    if abstract:
        # 提取第一句作为问题描述
        first_sentences = re.split(r'(?<=[.!?])\s+', abstract)
        if first_sentences:
            problem_sentence = first_sentences[0]
            insight_parts.append(f"**解决的问题**：{problem_sentence}")
    
    # 核心思路（从摘要中提取 "we propose/introduce/present" 后面的内容）
    approach_patterns = [
        r'[Ww]e (?:propose|introduce|present|develop|design)\s+(.{30,200}?)(?:\.|,\s*which)',
        r'[Tt]his (?:paper|work|study) (?:proposes|introduces|presents)\s+(.{30,200}?)(?:\.|,\s*which)',
        r'[Oo]ur (?:method|approach|framework|system|model),?\s+(?:called|named|dubbed)?\s*\w*,?\s*(.{30,200}?)(?:\.|,\s*which)',
    ]
    
    approach_found = False
    for pat in approach_patterns:
        match = re.search(pat, abstract)
        if match:
            insight_parts.append(f"**核心思路**：{match.group(1).strip()}")
            approach_found = True
            break
    
    if not approach_found and len(signals) > 0:
        insight_parts.append(f"**技术方向**：{'; '.join(signals[:3])}")
    
    # 产品启示
    pm_angles = []
    
    if any(kw in abstract_lower for kw in ["video generat", "video edit", "video diffus"]):
        pm_angles.append("视频生成/编辑类产品可关注此方向的技术进展，评估是否可用于自动化视频制作流程")
    if any(kw in abstract_lower for kw in ["multimodal", "vision-language", "image-text"]):
        pm_angles.append("多模态技术的突破意味着产品可以更好地理解图文混合内容，提升搜索、推荐和内容审核能力")
    if any(kw in abstract_lower for kw in ["agent", "tool use", "planning"]):
        pm_angles.append("Agent 能力的增强意味着 AI 助手可以完成更复杂的多步骤任务，减少人工干预")
    if any(kw in abstract_lower for kw in ["efficien", "fast", "lightweight", "compress"]):
        pm_angles.append("效率提升意味着更低的推理成本和更快的响应速度，有助于降低产品运营成本")
    if any(kw in abstract_lower for kw in ["safe", "alignment", "hallucin", "bias"]):
        pm_angles.append("安全与对齐研究直接关系到产品的可靠性和合规性，是落地应用的关键保障")
    if any(kw in abstract_lower for kw in ["benchmark", "evaluat"]):
        pm_angles.append("新的评测基准有助于选型时量化比较不同模型的能力，为技术选型提供依据")
    if any(kw in abstract_lower for kw in ["rag", "retriev", "knowledge"]):
        pm_angles.append("检索增强技术可直接应用于知识库问答、文档分析等企业级 AI 产品")
    if any(kw in abstract_lower for kw in ["3d", "gaussian", "nerf", "scene"]):
        pm_angles.append("3D 技术进展可关注在数字人、虚拟场景、游戏内容自动生成等方向的产品化机会")
    if any(kw in abstract_lower for kw in ["robot", "embod", "navigation"]):
        pm_angles.append("具身智能研究推动机器人从实验室走向产品化，关注人机交互和场景适配")
    if any(kw in abstract_lower for kw in ["diffusion", "image generat"]):
        pm_angles.append("图像生成技术持续迭代，关注生成质量、可控性和商业化落地场景")
    
    if not pm_angles:
        pm_angles.append("该研究展示了 AI 前沿技术的新进展，可持续关注其后续开源和应用落地情况")
    
    insight_parts.append(f"**产品启示**：{pm_angles[0]}")
    
    return "\n".join(insight_parts)


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
    
    print("  → 开始翻译论文标题和摘要...")
    
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
            
            # 翻译标题
            title_zh = translate_to_chinese(title)
            if title_zh and title_zh != title:
                lines.append(f"**{idx}. {title}**")
                lines.append(f"**📌 {title_zh}**")
            else:
                lines.append(f"**{idx}. {title}**")
            
            author_line = f"- **作者**：{authors}"
            if institutions:
                author_line += f" | **机构**：{institutions}"
            lines.append(author_line)
            
            if abstract:
                # 英文摘要（取前3句）
                sentences = re.split(r'(?<=[.!?])\s+', abstract)
                summary_en = " ".join(sentences[:3])
                if len(summary_en) > 400:
                    summary_en = summary_en[:400] + "..."
                lines.append(f"- **摘要**：{summary_en}")
                
                # 中文翻译摘要
                abstract_zh = translate_to_chinese(summary_en)
                if abstract_zh:
                    lines.append(f"- **中文摘要**：{abstract_zh}")
                
                time.sleep(0.5)  # 翻译 API 间隔
            
            # 产品经理解读
            pm_insight = generate_pm_insight(p)
            if pm_insight:
                lines.append(f"- 💡 **PM 解读**：")
                for insight_line in pm_insight.split("\n"):
                    lines.append(f"  - {insight_line}")
            
            if link:
                lines.append(f"- **链接**：{link}")
            elif arxiv_id:
                lines.append(f"- **链接**：https://arxiv.org/abs/{arxiv_id}")
            
            if likes:
                lines.append(f"- 🔥 {likes} 赞")
            
            lines.append("")
            idx += 1
            print(f"    ✓ 论文 {idx-1} 翻译+解读完成")
    
    return "\n".join(lines)


if __name__ == "__main__":
    papers = collect_papers()
    report = format_papers_report(papers)
    print("\n" + "=" * 60)
    print(report)
