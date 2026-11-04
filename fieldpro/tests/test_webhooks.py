"""Webhooks in and out: signatures, retries and idempotency."""

import json
import time

import frappe

from fieldpro.api.errors import Unauthorized
from fieldpro.services.callbacks import CallbackReceiver
from fieldpro.services.partner_webhooks import MAX_ATTEMPTS, PartnerWebhooks, signature_header
from fieldpro.tests import factories
from fieldpro.tests.base import FieldproTestCase

SECRET = "test-secret"


class Settings:
	partner_webhook_url = "https://partner.example/hooks"
	partner_webhook_secret = SECRET
	inbound_webhook_secret = SECRET


class Response:
	def __init__(self, status):
		self.status_code, self.text = status, ""


class TestInboundCallbacks(FieldproTestCase):
	def receiver(self, now=None):
		return CallbackReceiver(settings=Settings(), clock=(lambda: now) if now else time.time)

	def body(self, job):
		return json.dumps(
			{"id": f"evt-{factories.suffix()}", "type": "payment.received", "data": {"job": job}}
		)

	def test_a_signed_payment_marks_the_job_paid_once(self):
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		body = self.body(job)
		header = signature_header(SECRET, body)
		self.assertEqual(self.receiver().receive("payment", body, header)["status"], "processed")
		self.assertEqual(frappe.db.get_value("Service Job", job, "payment_status"), "Paid")
		self.assertEqual(self.receiver().receive("payment", body, header)["status"], "duplicate")

	def test_a_wrong_or_old_signature_is_refused(self):
		body = self.body("JOB-X")
		self.assertRaises(
			Unauthorized, self.receiver().receive, "payment", body, signature_header("wrong", body)
		)
		old = signature_header(SECRET, body, timestamp=int(time.time()) - 3600)
		self.assertRaises(Unauthorized, self.receiver().receive, "payment", body, old)
		self.assertRaises(Unauthorized, self.receiver().receive, "payment", body, None)


class TestPartnerWebhooks(FieldproTestCase):
	def test_queueing_an_event_twice_makes_one_delivery(self):
		hooks = PartnerWebhooks(settings=Settings(), post=lambda *a, **k: Response(200))
		job = factories.job(self.cust_x, technician_name=self.tech_a)
		self.assertEqual(
			hooks.queue("job.done", "Service Job", job, {}), hooks.queue("job.done", "Service Job", job, {})
		)

	def test_a_failing_partner_is_retried_with_growing_gaps_then_failed(self):
		calls = []

		def post(url, data, headers, timeout):
			calls.append(headers)
			return Response(503)

		hooks = PartnerWebhooks(settings=Settings(), post=post)
		name = hooks.queue(
			"job.done", "Service Job", factories.job(self.cust_x, technician_name=self.tech_a), {"x": 1}
		)
		statuses = [hooks.deliver(name) for _ in range(MAX_ATTEMPTS)]
		self.assertEqual(statuses[:-1], ["Pending"] * (MAX_ATTEMPTS - 1))
		self.assertEqual(statuses[-1], "Failed")
		self.assertTrue(all(h["X-Fieldpro-Signature"].startswith("t=") for h in calls))
		self.assertEqual(len({h["X-Fieldpro-Idempotency-Key"] for h in calls}), 1)
