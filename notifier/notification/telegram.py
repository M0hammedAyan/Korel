"""Telegram notification helpers for KORAL Notifier."""
import logging
import httpx

logger = logging.getLogger(__name__)


def format_telegram_message(data: dict) -> str:
    """Format a notification dict into a Telegram-friendly message."""
    def esc(text: str) -> str:
        """Escape special MarkdownV2 characters."""
        for ch in r"\_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    severity = esc(data.get("severity", "unknown").upper())
    incident_id = esc(data.get("incident_id", "N/A"))
    root_cause = esc(data.get("root_cause", "Unknown"))
    status = esc(data.get("status", "unknown"))
    message = esc(data.get("message", ""))
    pods = data.get("affected_pods", [])
    pods_str = esc(", ".join(pods[:5]) if pods else "none")

    lines = [
        f"🚨 *KORAL Alert — {severity}*",
        f"",
        f"*Incident:* `{incident_id}`",
        f"*Root Cause:* {root_cause}",
        f"*Status:* {status}",
        f"*Affected Pods:* {pods_str}",
        f"",
        f"_{message}_",
    ]
    return "\n".join(lines)


async def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API."""
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token or chat_id not configured")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info(f"Telegram message sent to chat {chat_id}")
                return True
            else:
                logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False
