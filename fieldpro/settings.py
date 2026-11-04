"""The one accessor for Fieldpro Settings. Code never reads the Single directly, so tests can pass
their own values and a missing setting has one documented default."""

import json

import frappe
from frappe.utils import flt

DEFAULT_APPROVAL_THRESHOLD = 20000


class AppSettings:
	def __init__(self, doc=None):
		self._doc = doc

	@property
	def doc(self):
		if self._doc is None:
			self._doc = frappe.get_cached_doc("Fieldpro Settings")
		return self._doc

	@property
	def company(self) -> str | None:
		return self.doc.company or frappe.defaults.get_global_default("company")

	@property
	def currency(self) -> str:
		company = self.company
		return (company and frappe.get_cached_value("Company", company, "default_currency")) or "KES"

	@property
	def approval_threshold(self) -> float:
		# 0 is a real setting ("approve every job"), so only a blank value falls back.
		value = self.doc.approval_threshold
		return DEFAULT_APPROVAL_THRESHOLD if value is None else flt(value)

	@property
	def labour_item(self) -> str | None:
		return self.doc.labour_item

	@property
	def labour_rate(self) -> float:
		return flt(self.doc.labour_rate)

	@property
	def push_enabled(self) -> bool:
		return bool(self.doc.push_enabled)

	@property
	def fcm_service_account(self) -> dict | None:
		raw = self._password("fcm_service_account")
		return json.loads(raw) if raw else None

	@property
	def partner_webhook_url(self) -> str | None:
		return self.doc.partner_webhook_url or None

	@property
	def partner_webhook_secret(self) -> str | None:
		return self._password("partner_webhook_secret")

	@property
	def inbound_webhook_secret(self) -> str | None:
		return self._password("inbound_webhook_secret")

	def _password(self, fieldname: str) -> str | None:
		return self.doc.get_password(fieldname, raise_exception=False) or None
