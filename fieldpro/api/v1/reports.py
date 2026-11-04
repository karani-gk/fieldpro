"""Numbers for the technician app."""

from fieldpro.access import AccessProfile
from fieldpro.api.endpoint import api, ok
from fieldpro.api.errors import Forbidden
from fieldpro.services.reports import WeekStats


@api(methods=["GET"])
def my_week():
	technician = AccessProfile().technician
	if not technician:
		raise Forbidden()
	return ok(WeekStats().for_technician(technician))
