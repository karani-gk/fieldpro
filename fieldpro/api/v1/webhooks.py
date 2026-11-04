"""Callbacks from SMS and payment providers: /api/method/fieldpro.api.v1.webhooks.receive?source=payment

Open to guests (providers do not sign in) and trusted only through the signature."""

import frappe

from fieldpro.api.endpoint import api, ok
from fieldpro.services.callbacks import CallbackReceiver


@api(methods=["POST"], allow_guest=True)
def receive(source: str):
	body = frappe.request.get_data(as_text=True)
	signature = frappe.get_request_header("X-Fieldpro-Signature")
	return ok(CallbackReceiver().receive(source, body, signature))
