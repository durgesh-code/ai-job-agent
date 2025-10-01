# src/notifier/emailer.py
import os
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict

def send_match_email(recipient: str, matches: List[Dict]):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM", user)

    if not (host and user and password and sender):
        raise RuntimeError("Email not configured via env vars.")

    lines = []
    for m in matches:
        lines.append(f"{m['title']} — {m.get('location','')}")
        lines.append(f"Score: {m['score']:.3f}")
        lines.append(f"Apply: {m['apply_url']}")
        lines.append(f"Reasons: {', '.join(m.get('reasons',[]))}")
        lines.append("")
    body = "\n".join(lines)
    msg = MIMEText(body)
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Job Matches Digest"

    server = smtplib.SMTP(host, port)
    server.starttls()
    server.login(user, password)
    server.sendmail(sender, [recipient], msg.as_string())
    server.quit()
