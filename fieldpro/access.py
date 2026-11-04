"""Who is calling, in fieldpro's terms: a manager, a technician, a customer, or nobody we know.

Every permission decision in the app starts here, so the rules live in one place: the
permission hooks (permissions.py), the edit guard on Service Job and the API endpoints.
"""

from functools import cached_property

import frappe

MANAGER_ROLES = frozenset({"System Manager", "Field Manager"})
TECHNICIAN_ROLE = "Field Technician"
CUSTOMER_ROLE = "Customer"


class AccessProfile:
	def __init__(self, user: str | None = None):
		self.user = user or frappe.session.user

	@cached_property
	def roles(self) -> set[str]:
		return set(frappe.get_roles(self.user))

	@property
	def is_manager(self) -> bool:
		return self.user == "Administrator" or bool(self.roles & MANAGER_ROLES)

	@cached_property
	def technician(self) -> str | None:
		"""The Technician record this user signs in as, if any (active only)."""
		if TECHNICIAN_ROLE not in self.roles:
			return None
		return frappe.db.get_value("Technician", {"user": self.user, "is_active": 1}, "name")

	@cached_property
	def customers(self) -> list[str]:
		"""Customers whose portal this user may use: ERPNext's Portal Users table on Customer."""
		if CUSTOMER_ROLE not in self.roles:
			return []
		return frappe.get_all(
			"Portal User",
			filters={"user": self.user, "parenttype": "Customer"},
			pluck="parent",
		)

	@property
	def kind(self) -> str:
		if self.is_manager:
			return "manager"
		if self.technician:
			return "technician"
		if self.customers:
			return "customer"
		return "none"

	def can_see_job(self, technician: str | None, customer: str | None) -> bool:
		if self.is_manager:
			return True
		if self.technician:
			return bool(technician) and technician == self.technician
		return bool(customer) and customer in self.customers
