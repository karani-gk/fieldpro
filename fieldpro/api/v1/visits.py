"""On-site work: start and end visits, record parts and photos. Technicians only."""

import frappe

from fieldpro.access import AccessProfile
from fieldpro.api import shapes
from fieldpro.api.endpoint import api, ok
from fieldpro.api.errors import Forbidden
from fieldpro.services.jobs import JobService, VisitPhotos
from fieldpro.services.visits import VisitService
from fieldpro.utils import from_iso


def _visit(doc):
	currency = frappe.db.get_value("Service Job", doc.service_job, "currency")
	return shapes.visit(doc, VisitPhotos.for_visits([doc.name]).get(doc.name, []), currency)


@api(methods=["POST"])
def start_visit(job: str, client_id: str | None = None, started_at: str | None = None):
	return ok(_visit(VisitService().start(job, client_id=client_id, started_at=from_iso(started_at))))


@api(methods=["POST"])
def end_visit(visit: str, ended_at: str | None = None, notes: str | None = None):
	return ok(_visit(VisitService().end(visit, ended_at=from_iso(ended_at), notes=notes)))


@api(methods=["POST"])
def add_part(visit: str, item_code: str, qty: float, client_id: str | None = None):
	return ok(_visit(VisitService().add_part(visit, item_code=item_code, qty=qty, client_id=client_id)))


@api(methods=["POST"])
def add_photo(visit: str, file_name: str, content: str):
	"""content: the image as base64 (a data URL is accepted)."""
	file = VisitService().add_photo(visit, file_name=file_name, content=content)
	return ok({"id": file.name, "name": file.file_name, "url": file.file_url})


@api(methods=["GET"])
def van_stock(search: str | None = None):
	"""Parts in the technician's van, with what is left, for the "add part" picker."""
	profile = AccessProfile()
	if not profile.technician:
		raise Forbidden()
	warehouse = frappe.db.get_value("Technician", profile.technician, "warehouse")
	filters = {"warehouse": warehouse, "actual_qty": [">", 0]}
	if search:
		filters["item_code"] = ["like", f"%{search}%"]
	bins = frappe.get_all(
		"Bin",
		filters=filters,
		fields=["item_code", "actual_qty"],
		order_by="item_code",
		ignore_permissions=True,
	)
	names = dict(
		frappe.get_all(
			"Item",
			filters={"name": ["in", [b.item_code for b in bins]]},
			fields=["name", "item_name"],
			as_list=True,
		)
	)
	return ok(
		[
			{"code": b.item_code, "name": names.get(b.item_code, b.item_code), "in_van": b.actual_qty}
			for b in bins
		]
	)
