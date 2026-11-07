"""The manager app's customers screen: who the customers are, their open work, and what they owe.

A field manager books jobs for customers but may have no read permission on Customer (ERPNext
gives it to sales roles), so the list uses get_all behind ManagerOnly, as the booking picker
does, and sends only contact details a dispatcher needs. What a customer owes is accounts data:
it is filled in only for managers who may read Sales Invoices, and None for everyone else.

Adding a customer is different: it creates a Customer, so ERPNext's own create permission
decides (Sales User has it). ERPNext itself makes the primary Contact from the phone and email,
and the primary Address from the street and city, as Desk's quick entry does.
"""

import frappe
from frappe import _
from frappe.utils import cstr, flt, validate_email_address

from fieldpro.api import shapes
from fieldpro.api.errors import Forbidden, Invalid
from fieldpro.services.dispatch import ManagerOnly
from fieldpro.services.job_rules import CLOSED_STATES
from fieldpro.settings import AppSettings

CUSTOMER_LIMIT = 50


class CustomerDirectory(ManagerOnly):
	def search(self, text: str | None = None, limit: int = CUSTOMER_LIMIT) -> list[dict]:
		like = f"%{(text or '').strip()}%"
		rows = frappe.get_all(
			"Customer",
			fields=["name", "customer_name", "mobile_no", "email_id"],
			filters={"disabled": 0},
			or_filters=[["name", "like", like], ["customer_name", "like", like]],
			order_by="customer_name asc",
			limit_page_length=limit,
		)
		return self._rows(rows)

	def form(self) -> dict:
		"""What the New customer dialog needs: may this manager add one, and the choices."""
		return {
			"can_add": self._can_add(),
			"customer_types": self._options("customer_type"),
			"customer_groups": self._leaves("Customer Group"),
			"territories": self._leaves("Territory"),
			"defaults": {
				"customer_type": "Company",
				"customer_group": self._default("customer_group", "Customer Group"),
				"territory": self._default("territory", "Territory"),
			},
		}

	def add(
		self,
		*,
		customer_name: str,
		customer_type: str = "Company",
		customer_group: str | None = None,
		territory: str | None = None,
		mobile_no: str | None = None,
		email: str | None = None,
		address_line1: str | None = None,
		city: str | None = None,
	) -> dict:
		"""A new customer, with ERPNext's primary contact and address when given. Returns its row."""
		if not self._can_add():
			raise Forbidden(_("Adding customers needs a sales role (Sales User). Ask your administrator."))
		doc = frappe.new_doc("Customer")
		doc.update(
			{
				"customer_name": self._new_name(customer_name),
				"customer_type": self._choice("customer_type", customer_type, self._options("customer_type")),
				"customer_group": self._link("customer_group", "Customer Group", customer_group),
				"territory": self._link("territory", "Territory", territory),
				"mobile_no": cstr(mobile_no).strip(),
				"email_id": self._email(email),
			}
		)
		if cstr(address_line1).strip():
			if not cstr(city).strip():
				raise Invalid(_("Add the town or city for the address."), fields={"city": "required"})
			# ERPNext's make_address needs a country: the company's.
			doc.update(
				{"address_line1": address_line1.strip(), "city": city.strip(), "country": self._country()}
			)
		doc.insert()
		return self._rows([frappe._dict(doc.as_dict())])[0]

	def _rows(self, rows: list) -> list[dict]:
		names = [r.name for r in rows]
		open_jobs = self._open_jobs(names)
		owed = self._owed(names)
		currency = AppSettings().currency
		return [
			{
				"id": r.name,
				"name": r.customer_name,
				"mobile_no": r.mobile_no or "",
				"email": r.email_id or "",
				"open_jobs": open_jobs.get(r.name, 0),
				"owed": None if owed is None else shapes.money(owed.get(r.name, 0), currency),
			}
			for r in rows
		]

	def _can_add(self) -> bool:
		return bool(frappe.has_permission("Customer", "create", user=self.profile.user))

	@staticmethod
	def _new_name(value: str | None) -> str:
		name = cstr(value).strip()
		if not name:
			raise Invalid(_("Enter the customer's name."), fields={"customer_name": "required"})
		# ERPNext would quietly name a second "Wanjiku Clinic" "Wanjiku Clinic - 1": say so instead.
		if frappe.db.exists("Customer", {"customer_name": name}):
			raise Invalid(
				_("{0} is already a customer.").format(name), fields={"customer_name": "already exists"}
			)
		return name

	@staticmethod
	def _choice(field: str, value: str, options: list[str]) -> str:
		if value not in options:
			raise Invalid(_("Choose one of: {0}.").format(", ".join(options)), fields={field: "invalid"})
		return value

	def _link(self, field: str, doctype: str, value: str | None) -> str | None:
		"""A group or territory that is not itself a group, or the default when blank."""
		if not value:
			return self._default(field, doctype)
		return self._choice(field, value, self._leaves(doctype))

	@staticmethod
	def _email(value: str | None) -> str:
		email = cstr(value).strip()
		if email and not validate_email_address(email):
			raise Invalid(_("That is not an email address."), fields={"email": "invalid"})
		return email

	@staticmethod
	def _options(field: str) -> list[str]:
		options = frappe.get_meta("Customer").get_field(field).options or ""
		return [o for o in options.split("\n") if o]

	@staticmethod
	def _leaves(doctype: str) -> list[str]:
		# get_all: like the customer list, these are names a manager may need without read access.
		return frappe.get_all(doctype, filters={"is_group": 0}, pluck="name", order_by="name asc")

	def _default(self, field: str, doctype: str) -> str | None:
		"""Selling Settings' default, else the only or first choice."""
		value = frappe.db.get_single_value("Selling Settings", field)
		leaves = self._leaves(doctype)
		return value if value in leaves else (leaves[0] if leaves else None)

	@staticmethod
	def _country() -> str | None:
		company = AppSettings().company
		return (company and frappe.get_cached_value("Company", company, "country")) or None

	@staticmethod
	def _open_jobs(customers: list[str]) -> dict[str, int]:
		if not customers:
			return {}
		rows = frappe.get_list(
			"Service Job",
			fields=["customer", {"COUNT": "name", "as": "count"}],
			filters=[["customer", "in", customers], ["workflow_state", "not in", list(CLOSED_STATES)]],
			group_by="customer",
		)
		return {r.customer: r.count for r in rows}

	def _owed(self, customers: list[str]) -> dict[str, float] | None:
		if not frappe.has_permission("Sales Invoice", "read", user=self.profile.user):
			return None
		if not customers:
			return {}
		rows = frappe.get_list(
			"Sales Invoice",
			fields=["customer", {"SUM": "outstanding_amount", "as": "owed"}],
			filters=[["customer", "in", customers], ["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
			group_by="customer",
		)
		return {r.customer: flt(r.owed) for r in rows}
