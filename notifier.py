import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import requests
from config import get_email_defaults, get_env


def send_email_alert(subject: str, body: str, to_email: str,
                     from_email: Optional[str] = None,
                     app_password: Optional[str] = None) -> None:
    if from_email is None or app_password is None:
        from_email, app_password = get_email_defaults()
    if from_email == "your_email@gmail.com" or app_password == "your_app_password":
        print("[Email disabled] Configure from_email and app_password to enable alerts.")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        return
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        print("Email sent")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_slack_alert(subject: str, body: str, webhook_url: Optional[str] = None) -> None:
    if webhook_url is None:
        webhook_url = get_env('BMS_SLACK_WEBHOOK_URL')
    if not webhook_url:
        print("[Slack disabled] Set BMS_SLACK_WEBHOOK_URL or pass webhook_url")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        return
    try:
        payload = {"text": f"*{subject}*\n{body}"}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code >= 300:
            print(f"Slack webhook failed: {resp.status_code} {resp.text}")
        else:
            print("Slack notification sent")
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")


def send_slack_api_alert(subject: str, body: str,
                         token: Optional[str] = None,
                         channel: Optional[str] = None) -> None:
    if token is None:
        token = get_env('BMS_SLACK_BOT_TOKEN')
    if channel is None:
        channel = get_env('BMS_SLACK_CHANNEL')
    if not token or not channel:
        print("[Slack API disabled] Set BMS_SLACK_BOT_TOKEN and BMS_SLACK_CHANNEL or pass token/channel")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        return
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-type": "application/json; charset=utf-8"}
        payload = {"channel": channel, "text": f"*{subject}*\n{body}"}
        resp = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=payload, timeout=10)
        data = resp.json()
        if not data.get('ok'):
            print(f"Slack API error: {data}")
        else:
            print("Slack API notification sent")
    except Exception as e:
        print(f"Failed to send Slack API notification: {e}")

def notify(subject: str, body: str,
           email: Optional[str] = None,
           use_slack: bool = False,
           slack_webhook: Optional[str] = None,
           slack_token: Optional[str] = None,
           slack_channel: Optional[str] = None) -> None:
    if email:
        send_email_alert(subject, body, email)
    if slack_token or slack_channel or get_env('BMS_SLACK_BOT_TOKEN'):
        send_slack_api_alert(subject, body, token=slack_token, channel=slack_channel)
    elif use_slack or slack_webhook or get_env('BMS_SLACK_WEBHOOK_URL'):
        send_slack_alert(subject, body, webhook_url=slack_webhook)


