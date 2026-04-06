"""
AI 日报 - 主程序
每日定时运行，抓取论文和热点，通过邮件推送
"""

import os
import sys
import io
from datetime import datetime, timezone, timedelta

# 修复 Windows 终端编码问题
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fetch_papers import collect_papers, format_papers_report
from fetch_news import collect_news, format_news_report
from send_email import send_email, markdown_to_html


def generate_daily_report():
    """生成每日 AI 日报"""
    # 北京时间
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    date_str = now_beijing.strftime("%Y年%m月%d日")
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    weekday = weekday_map[now_beijing.weekday()]
    
    print(f"📅 生成 AI 日报: {date_str} ({weekday})")
    print("=" * 60)
    
    # 1. 抓取论文
    papers = collect_papers()
    papers_report = format_papers_report(papers, max_papers=10)
    
    # 2. 抓取热点
    serper_key = os.environ.get("SERPER_API_KEY")
    news = collect_news(serper_key)
    news_report = format_news_report(news, max_items=5)
    
    # 3. 组合报告
    report = f"""# 🤖 AI 日报 | {date_str}（{weekday}）

---

## 📚 第一部分：当日 AI 论文精选

> 来源：Hugging Face Daily Papers、Papers With Code、arXiv

{papers_report}

---

## 🔥 第二部分：AI 行业热点

> 来源：TechCrunch、The Verge、AIToolly 等

{news_report}

---

*以上为 {date_str} AI 日报，由 AI Daily Bot 自动生成推送。* 🚀
"""
    
    return report


def main():
    """主函数"""
    print("🚀 AI Daily Push 启动")
    print()
    
    # 生成报告
    report = generate_daily_report()
    
    print("\n" + "=" * 60)
    print("📝 报告生成完毕，准备发送...")
    print("=" * 60)
    
    # 发送邮件
    recipient = os.environ.get("RECIPIENT_EMAIL", "18868497748@163.com")
    sender = os.environ.get("SENDER_EMAIL")
    
    if not sender:
        print("\n⚠️  未配置发件邮箱，仅输出到控制台：")
        print(report)
        
        # 将报告保存为文件（GitHub Actions 可作为 artifact）
        output_dir = os.environ.get("GITHUB_WORKSPACE", ".")
        output_file = os.path.join(output_dir, "daily_report.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 报告已保存到: {output_file}")
        return
    
    # 北京时间日期
    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = datetime.now(beijing_tz)
    subject = f"🤖 AI 日报 | {now_beijing.strftime('%m月%d日')}"
    
    html_body = markdown_to_html(report)
    
    success = send_email(
        subject=subject,
        body_html=html_body,
        body_text=report,
        recipient_email=recipient,
    )
    
    if success:
        print("\n✅ 日报推送完成！")
    else:
        print("\n❌ 推送失败，报告内容如下：")
        print(report)
        sys.exit(1)


if __name__ == "__main__":
    main()
