"""What a client checks first: is the server reachable, which API is this, must I update?"""

import frappe

from fieldpro.api.endpoint import api, ok
from fieldpro.api.v1 import API_VERSION, MIN_CLIENT_VERSION
from fieldpro.settings import AppSettings
from fieldpro.utils import to_iso


@api(methods=["GET"], allow_guest=True)
def info():
	return ok(
		{
			"api_version": API_VERSION,
			"min_client_version": MIN_CLIENT_VERSION,
			"server_time": to_iso(frappe.utils.now_datetime()),
			"currency": AppSettings().currency,
			"company": frappe.db.get_value("Company", AppSettings().company, "company_name"),
		}
	)
