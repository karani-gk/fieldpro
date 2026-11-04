"""Webhooks in: SMS delivery reports and payment notifications from outside providers.

An open URL that changes data must prove who is calling and must not act twice:
- The signature (same scheme as our outgoing webhooks) proves the provider sent it. A request
  older than five minutes is refused, so a captured request cannot be replayed later.
- Each event is stored under a unique key (source:event_id) before it is acted on. Providers
  retry until they get a 2xx; the retry hits the unique key and is answered "duplicate".
"""

import hmac
import json
import time

import frappe
from frappe import _

from fieldpro.api.errors import Invalid, Unauthorized
from fieldpro.services.partner_webhooks import sign
from fieldpro.services.realtime import JobBroadcast
from fieldpro.settings import AppSettings

SOURCES = ("sms", "payment")
TOLERANCE_SECONDS = 300


class CallbackReceiver:
	def __init__(self, settings: AppSettings | None = None, clock=time.time):
		self.settings = settings or AppSettings()
		self.clock = clock

	def receive(self, source: str, body: str, signature: str | None) -> dict:
		if source not in SOURCES:
			raise Invalid(_("Unknown callback source."), fields={"source": "invalid"})
		self.verify(body, signature)
		try:
			event = json.loads(body)
			event_id = str(event["id"])
		except ValueError, KeyError, TypeError:
			raise Invalid(_("The body must be JSON with an id."), fields={"body": "invalid"})
		key = f"{source}:{event_id}"
		if frappe.db.exists("Callback Event", {"event_key": key}):
			return {"status": "duplicate"}
		doc = frappe.get_doc(
			{
				"doctype": "Callback Event",
				"source": source,
				"event_id": event_id,
				"event_key": key,
				"event_type": event.get("type"),
				"payload": body,
			}
		)
		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			# Two copies arrived at once; the other request is handling it.
			return {"status": "duplicate"}
		self._process(doc, event)
		return {"status": doc.status.lower()}

	def verify(self, body: str, header: str | None) -> None:
		secret = self.settings.inbound_webhook_secret
		if not secret:
			raise Unauthorized(_("Callbacks are not set up on this site."))
		parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
		try:
			timestamp = int(parts["t"])
		except KeyError, ValueError:
			raise Unauthorized(_("Missing or malformed signature."))
		if abs(self.clock() - timestamp) > TOLERANCE_SECONDS:
			raise Unauthorized(_("The signature has expired."))
		if not hmac.compare_digest(parts.get("v1", ""), sign(secret, timestamp, body)):
			raise Unauthorized(_("The signature does not match."))

	def _process(self, doc, event: dict) -> None:
		handler = {"payment.received": self._payment_received}.get(event.get("type"))
		if not handler:
			doc.db_set({"status": "Ignored", "result": "No action for this event type."})
			return
		doc.db_set({"status": "Processed", "result": handler(event)})

	@staticmethod
	def _payment_received(event: dict) -> str:
		job = (event.get("data") or {}).get("job")
		if not job or not frappe.db.exists("Service Job", job):
			return f"No job {job!r}; nothing changed."
		frappe.db.set_value("Service Job", job, "payment_status", "Paid")
		JobBroadcast().publish(job)
		return f"Job {job} marked paid."
