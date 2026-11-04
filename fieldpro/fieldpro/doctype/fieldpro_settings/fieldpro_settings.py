import frappe
from frappe.model.document import Document


class FieldproSettings(Document):
	def validate(self):
		if self.labour_item and frappe.db.get_value("Item", self.labour_item, "is_stock_item"):
			frappe.throw(frappe._("The labour item must be a non-stock item (hours are not stock)."))
