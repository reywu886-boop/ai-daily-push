"""
AI 日报 - 邮件推送模块
通过 SMTP 发送邮件到用户邮箱
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os


def send_email(subject, body_html, body_text=None,
               smtp_server=None, smtp_port=None,
               sender_email=None, sender_password=None,
               recipient_email=None):
    """
    发送邮件
    
    参数优先从函数参数获取，其次从环境变量获取
    """
    smtp_server = smtp_server or os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(smtp_port or os.environ.get("SMTP_PORT", "587"))
    sender_email = sender_email or os.environ.get("SENDER_EMAIL")
    sender_password = sender_password or os.environ.get("SENDER_PASSWORD")
    recipient_email = recipient_email or os.environ.get("RECIPIENT_EMAIL")
    
    if not all([sender_email, sender_password, recipient_email]):
        print("[ERROR] 邮件配置不完整，请设置环境变量：")
        print("  SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"AI Daily Bot <{sender_email}>"
        msg["To"] = recipient_email
        
        # 纯文本版本
        if body_text:
            text_part = MIMEText(body_text, "plain", "utf-8")
            msg.attach(text_part)
        
        # HTML 版本
        html_part = MIMEText(body_html, "html", "utf-8")
        msg.attach(html_part)
        
        # 连接并发送
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        server.quit()
        
        print(f"✅ 邮件发送成功 → {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        return False


def markdown_to_html(md_text):
    """简易 Markdown 转 HTML（不依赖额外库）"""
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<br>")
            continue
        
        # 标题
        if stripped.startswith("# "):
            html_lines.append(f'<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px;">{stripped[2:]}</h1>')
            continue
        if stripped.startswith("## "):
            html_lines.append(f'<h2 style="color:#333;margin-top:24px;">{stripped[3:]}</h2>')
            continue
        if stripped.startswith("### "):
            html_lines.append(f'<h3 style="color:#555;margin-top:16px;">{stripped[4:]}</h3>')
            continue
        
        # 加粗
        stripped = _process_bold(stripped)
        
        # 链接
        stripped = _process_links(stripped)
        
        # 列表项
        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{stripped[2:]}</li>")
            continue
        
        # 分隔线
        if stripped.startswith("---"):
            html_lines.append('<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">')
            continue
        
        # 引用
        if stripped.startswith("> "):
            html_lines.append(f'<blockquote style="border-left:3px solid #ccc;padding-left:12px;color:#666;">{stripped[2:]}</blockquote>')
            continue
        
        # 普通段落
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{stripped}</p>")
    
    if in_list:
        html_lines.append("</ul>")
    
    body = "\n".join(html_lines)
    
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#333;line-height:1.6;">
{body}
<hr style="border:none;border-top:1px solid #ddd;margin:24px 0;">
<p style="color:#999;font-size:12px;text-align:center;">
  🤖 本邮件由 AI Daily Bot 自动生成 | {datetime.utcnow().strftime("%Y-%m-%d")}
</p>
</body>
</html>"""


def _process_bold(text):
    """处理 **加粗** 语法"""
    import re
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


def _process_links(text):
    """处理 [text](url) 语法"""
    import re
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#1a73e8;">\1</a>', text)


if __name__ == "__main__":
    # 测试
    test_md = """# 🤖 AI 日报测试

## 📚 论文精选

### 🎬 视频生成

**1. Test Paper Title**
- **作者**：Test Author | **机构**：Test Lab
- **摘要**：This is a test abstract.
- **链接**：https://example.com

---

## 🔥 热点事件

**1. Test News**
- Description here
- 🔗 https://example.com
"""
    
    html = markdown_to_html(test_md)
    print(html)
