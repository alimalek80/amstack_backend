"""Notify the site owner about a new contact message (email and Telegram).

Both channels are optional: they only run when configured through the
environment. Failures are logged and never affect the visitor's response.
"""

import json
import logging
import threading
from urllib import request as urlrequest

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def _clean_name(message):
    # Collapse whitespace and newlines so the name is safe in an email subject.
    return " ".join(message.name.split())[:80]


def _summary(message):
    budget = message.get_budget_display() or "-"
    return f"From: {_clean_name(message)} <{message.email}>\nBudget: {budget}\n\n{message.message}"


def _send_email(message):
    recipient = settings.CONTACT_NOTIFY_EMAIL
    if not recipient:
        return
    EmailMessage(
        subject=f"New contact message from {_clean_name(message)}",
        body=_summary(message),
        to=[recipient],
        reply_to=[message.email],
    ).send()


def _send_telegram(message):
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not (token and chat_id):
        return
    text = ("New contact message\n" + _summary(message))[:3500]
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urlrequest.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urlrequest.urlopen(req, timeout=5).close()


def _run(message):
    for send in (_send_email, _send_telegram):
        try:
            send(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Contact notification %s failed: %s", send.__name__, exc)


def notify_new_message(message):
    """Send notifications in a background thread so the request stays fast."""
    threading.Thread(target=_run, args=(message,), daemon=True).start()
