"""Webhooks out: telling a partner's system (their accounting, their CRM) that something happened.

Three things make a webhook trustworthy:
- A signature. The body is signed with a shared secret (HMAC-SHA256 over "timestamp.body"), so
  the partner knows it came from us and was not changed. The timestamp stops replays.
- Retries. Their server will be down sometimes. Each delivery is a row (Partner Delivery) that is
  retried with growing gaps - 1, 2, 4, 8, 16 minutes - then marked Failed for a person to see.
- An idempotency key. A retry after a timeout may arrive twice; the partner drops the second
  one by its key. We make one row per event, so we never invent a second key for the same event.
"""

import hashlib
import hmac
import json
import time

import frappe
import requests
from frappe.utils import add_to_date, now_datetime

from fieldpro.settings import AppSettings

MAX_ATTEMPTS = 6
TIMEOUT_SECONDS = 10


def sign(secret: str, timestamp: int, body: str) -> str:
	return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def signature_header(secret: str, body: str, timestamp: int | None = None) -> str:
	timestamp = timestamp or int(time.time())
	return f"t={timestamp},v1={sign(secret, timestamp, body)}"


class PartnerWebhooks:
	def __init__(self, settings: AppSettings | None = None, post=requests.post):
		self.settings = settings or AppSettings()
		self.post = post

	def queue(self, event: str, doctype: str, name: str, payload: dict) -> str | None:
		"""One delivery per event: queueing the same event again returns the existing row."""
		if not self.settings.partner_webhook_url:
			return None
		key = f"{event}:{name}"
		existing = frappe.db.get_value("Partner Delivery", {"idempotency_key": key}, "name")
		if existing:
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "Partner Delivery",
				"event": event,
				"idempotency_key": key,
				"reference_doctype": doctype,
				"reference_name": name,
				"payload": json.dumps({"event": event, "id": key, "data": payload}, sort_keys=True),
				"status": "Pending",
				"next_attempt_at": now_datetime(),
			}
		).insert(ignore_permissions=True)
		frappe.enqueue(
			"fieldpro.services.partner_webhooks.deliver", delivery=doc.name, enqueue_after_commit=True
		)
		return doc.name

	def deliver(self, name: str) -> str:
		doc = frappe.get_doc("Partner Delivery", name, for_update=True)
		if doc.status != "Pending":
			return doc.status
		url, secret = self.settings.partner_webhook_url, self.settings.partner_webhook_secret
		if not (url and secret):
			return doc.status
		headers = {
			"Content-Type": "application/json",
			"X-Fieldpro-Event": doc.event,
			"X-Fieldpro-Idempotency-Key": doc.idempotency_key,
			"X-Fieldpro-Signature": signature_header(secret, doc.payload),
		}
		doc.attempts += 1
		try:
			response = self.post(url, data=doc.payload, headers=headers, timeout=TIMEOUT_SECONDS)
			doc.last_status_code = response.status_code
			doc.last_response = (response.text or "")[:1000]
			delivered = 200 <= response.status_code < 300
		except requests.RequestException as exc:
			doc.last_status_code = 0
			doc.last_response = str(exc)[:1000]
			delivered = False
		if delivered:
			doc.status = "Sent"
		elif doc.attempts >= MAX_ATTEMPTS:
			doc.status = "Failed"
		else:
			doc.next_attempt_at = add_to_date(now_datetime(), minutes=2 ** (doc.attempts - 1))
		doc.save(ignore_permissions=True)
		return doc.status

	def retry_due(self) -> int:
		due = frappe.get_all(
			"Partner Delivery",
			filters={"status": "Pending", "next_attempt_at": ["<=", now_datetime()]},
			pluck="name",
			limit_page_length=100,
		)
		for name in due:
			self.deliver(name)
			frappe.db.commit()  # each delivery stands alone: one failure must not undo the others
		return len(due)


def deliver(delivery: str) -> None:
	"""Background job entry point (queue())."""
	PartnerWebhooks().deliver(delivery)


def retry_due() -> None:
	"""Scheduler entry point (hooks.py, every 5 minutes)."""
	PartnerWebhooks().retry_due()
