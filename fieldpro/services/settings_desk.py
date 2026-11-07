"""The manager app's settings screen: the Fieldpro Settings a manager changes in day-to-day work.

Only the everyday settings come here. The push key, webhook secrets and activation stay in Desk:
a browser screen that never receives a secret cannot leak one. Saving goes through the Single's
own save(), so the DocType's permissions (Field Manager may write) and validation still apply.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from fieldpro.api.errors import Forbidden, Invalid
from fieldpro.services.dispatch import ManagerOnly
from fieldpro.settings import AppSettings

SETTINGS_DOCTYPE = "Fieldpro Settings"
EDITABLE_SETTINGS = (
	"approval_threshold",
	"labour_item",
	"labour_rate",
	"sign_in_code_channel",
	"keep_managers_in_desk",
)
LABOUR_ITEM_LIMIT = 50


class SettingsDesk(ManagerOnly):
	def read(self) -> dict:
		settings = AppSettings(frappe.get_doc(SETTINGS_DOCTYPE))
		return {
			"company": settings.company,
			"currency": settings.currency,
			"approval_threshold": settings.approval_threshold,
			"labour_item": settings.labour_item or "",
			"labour_rate": settings.labour_rate,
			"sign_in_code_channel": settings.sign_in_code_channel,
			"keep_managers_in_desk": not settings.open_manager_app,
			"can_edit": bool(frappe.has_permission(SETTINGS_DOCTYPE, "write", user=self.profile.user)),
			"choices": {
				"sign_in_code_channel": self._channels(),
				"labour_item": self._labour_items(),
			},
		}

	def update(self, changes: dict) -> None:
		unknown = sorted(set(changes) - set(EDITABLE_SETTINGS))
		if unknown:
			raise Invalid(
				_("These cannot be changed here: {0}").format(", ".join(unknown)),
				fields={f: "not editable" for f in unknown},
			)
		clean = {name: self._clean(name, value) for name, value in changes.items()}
		doc = frappe.get_doc(SETTINGS_DOCTYPE)
		if not doc.has_permission("write"):
			raise Forbidden(_("You may read the settings but not change them."))
		doc.update(clean)
		doc.save()

	def _clean(self, name: str, value):
		"""One setting's value, checked here so the manager sees which field is wrong."""
		cleaners = {
			"approval_threshold": self._amount,
			"labour_rate": self._amount,
			"labour_item": self._labour_item,
			"sign_in_code_channel": self._channel,
			"keep_managers_in_desk": lambda _name, v: cint(bool(v)),
		}
		return cleaners[name](name, value)

	@staticmethod
	def _amount(name: str, value) -> float:
		if value in (None, "") or flt(value) < 0:
			raise Invalid(_("Enter 0 or more."), fields={name: "invalid"})
		return flt(value)

	def _channel(self, name: str, value) -> str:
		if value not in self._channels():
			raise Invalid(_("Choose Email or SMS."), fields={name: "invalid"})
		return value

	@staticmethod
	def _labour_item(name: str, value) -> str | None:
		"""A service (non-stock) item, or blank to bill no hours."""
		if value and not frappe.db.exists("Item", {"name": value, "is_stock_item": 0, "disabled": 0}):
			raise Invalid(_("Choose a service item that is not kept in stock."), fields={name: "invalid"})
		return value or None

	@staticmethod
	def _channels() -> list[str]:
		field = frappe.get_meta(SETTINGS_DOCTYPE).get_field("sign_in_code_channel")
		return [o for o in (field.options or "").split("\n") if o]

	@staticmethod
	def _labour_items() -> list[dict]:
		# get_all: a field manager may have no read permission on Item, yet choosing the labour item
		# is a setting they own. Only code and name leave, and only to managers.
		rows = frappe.get_all(
			"Item",
			fields=["name", "item_name"],
			filters={"is_stock_item": 0, "disabled": 0},
			order_by="item_name asc",
			limit_page_length=LABOUR_ITEM_LIMIT,
		)
		return [{"id": r.name, "name": r.item_name} for r in rows]
