from __future__ import annotations

import hashlib
import logging
import socket
import time
import re
from typing import Iterable, Mapping, Optional, Sequence
from email.utils import parseaddr

from celery import shared_task, Task

from django.conf import settings
from django.core.cache import cache
from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_spaces_between_tags
from django.utils.text import slugify

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

class BaseRetryTask(Task):
    autoretry_for = (ConnectionError, socket.error, Exception)
    retry_backoff = True
    retry_jitter = True
    max_retries = 5
    acks_late = True
    reject_on_worker_lost = True
    soft_time_limit = 30
    time_limit = 60

def _make_idempotency_key(
    *, subject: str, to: Sequence[str], body: Optional[str] = None, html: Optional[str] = None
) -> str:
    digest = hashlib.sha256()
    digest.update(subject.encode("utf-8"))
    digest.update(",".join(sorted(set(to))).encode("utf-8"))
    if body:
        digest.update(body.encode("utf-8"))
    if html:
        digest.update(html.encode("utf-8"))
    return "mail:idemp:" + digest.hexdigest()

def _render_email(
    *,
    subject: str,
    body: Optional[str] = None,
    html: Optional[str] = None,
    template_txt: Optional[str] = None,
    template_html: Optional[str] = None,
    ctx: Optional[dict] = None,
):
    if template_txt:
        body = render_to_string(template_txt, ctx or {})
    if template_html:
        html = render_to_string(template_html, ctx or {})
        html = strip_spaces_between_tags(html.strip())

    if body is None and html is not None:
        body = strip_spaces_between_tags(html)
    if body is None:
        body = ""
    return subject, body, html

def _filter_valid_emails(recipients: Iterable[str]) -> list[str]:
    raw_list = [r.strip() for r in recipients if r and r.strip()]
    valid_emails = []
    for r in raw_list:
        name, addr = parseaddr(r)
        if EMAIL_REGEX.match(addr):
            valid_emails.append(addr)
        else:
            logger.warning(f"[Email Filter] Skipped invalid address: {r!r}")
    filtered_list = list(dict.fromkeys(valid_emails))
    logger.info(f"[Email Filter] Input: {raw_list} -> Valid: {filtered_list}")
    return filtered_list

@shared_task(bind=True, base=BaseRetryTask, rate_limit="30/m", queue="emails")
def send_email_task(
    self,
    *,
    subject: str,
    to: Iterable[str],
    from_email: Optional[str] = None,
    body: Optional[str] = None,
    html: Optional[str] = None,
    template_txt: Optional[str] = None,
    template_html: Optional[str] = None,
    ctx: Optional[dict] = None,
    headers: Optional[Mapping[str, str]] = None,
    attachments: Optional[Sequence[tuple[str, bytes, str]]] = None,
    idempotent_ttl: int = 60,
) -> dict:
    logger.info("### USING NEW EMAIL FILTER VERSION ###")

    subject, body, html = _render_email(
        subject=subject, body=body, html=html,
        template_txt=template_txt, template_html=template_html, ctx=ctx
    )

    recipients = _filter_valid_emails(to)
    if not recipients:
        logger.warning("send_email_task: no valid recipients after filtering")
        return {"sent": 0, "to": []}

    from_list = _filter_valid_emails([from_email] if from_email else [])
    if from_list:
        from_email_clean = from_list[0]
    else:
        safe_default = "no-reply@example.com"
        logger.warning(f"send_email_task: invalid from_email '{from_email}', using safe default '{safe_default}'")
        from_email_clean = safe_default

    headers_clean = dict(headers or {})
    if "Reply-To" in headers_clean:
        reply_to_filtered = _filter_valid_emails([headers_clean["Reply-To"]])
        if reply_to_filtered:
            headers_clean["Reply-To"] = reply_to_filtered[0]
        else:
            logger.warning(f"send_email_task: removed invalid Reply-To: {headers_clean['Reply-To']}")
            del headers_clean["Reply-To"]

    idem_key = _make_idempotency_key(subject=subject, to=recipients, body=body, html=html)
    if idempotent_ttl > 0 and not cache.add(idem_key, "1", timeout=idempotent_ttl):
        logger.info("send_email_task: deduplicated by idempotency key %s", idem_key)
        return {"sent": 0, "to": recipients, "deduplicated": True}

    connection = get_connection()
    msg = EmailMultiAlternatives(
        subject=subject,
        body=body or "",
        from_email=from_email_clean,
        to=recipients,
        headers=headers_clean,
        connection=connection,
    )
    if html:
        msg.attach_alternative(html, "text/html")
    if attachments:
        for filename, content, mimetype in attachments:
            msg.attach(filename, content, mimetype)

    sent = msg.send(fail_silently=False)
    meta = {
        "sent": int(sent),
        "to": recipients,
        "message_id": slugify(f"{subject}-{time.time()}")[:40],
    }
    logger.info("send_email_task: %s", meta)
    return meta

@shared_task(bind=True, base=BaseRetryTask, rate_limit="120/m", queue="emails")
def send_bulk_emails_task(
    self,
    *,
    subject: str,
    to_batches: Sequence[Sequence[str]],
    from_email: Optional[str] = None,
    body: Optional[str] = None,
    html: Optional[str] = None,
) -> dict:
    total = 0
    for batch in to_batches:
        res = send_email_task.apply_async(
            kwargs=dict(subject=subject, to=batch, from_email=from_email, body=body, html=html),
            queue="emails",
        )
        logger.debug("queued batch task_id=%s size=%d", res.id, len(batch))
        total += len(batch)
    return {"queued_recipients": total, "batches": len(to_batches)}
