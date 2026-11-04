"""Performance numbers: one query, used by the Desk report and the technician's "my week" screen.

Desk can afford a fresh query for a manager. A phone opening "my week" many times a day gets the
same numbers from the cache, which is cleared when one of the technician's visits changes.
"""

import frappe
from frappe.utils import add_days, flt, getdate, today

WEEK_CACHE_SECONDS = 600


def performance(from_date, to_date, technician: str | None = None) -> list[dict]:
	"""Jobs done, visits and hours per technician between two dates (by visit start)."""
	conditions = ["v.status = 'Closed'", "date(v.started_at) between %(from_date)s and %(to_date)s"]
	if technician:
		conditions.append("v.technician = %(technician)s")
	return frappe.db.sql(
		f"""
		select v.technician, t.full_name as technician_name,
			count(distinct case when j.workflow_state = 'Done' then j.name end) as jobs_done,
			count(v.name) as visits,
			coalesce(sum(v.duration_hours), 0) as hours,
			coalesce(sum(p.parts_amount), 0) as parts_value
		from `tabJob Visit` v
		join `tabTechnician` t on t.name = v.technician
		join `tabService Job` j on j.name = v.service_job
		left join (
			select parent, sum(amount) as parts_amount from `tabParts Used`
			where parenttype = 'Job Visit' group by parent
		) p on p.parent = v.name
		where {" and ".join(conditions)}
		group by v.technician, t.full_name
		order by hours desc
		""",
		{"from_date": from_date, "to_date": to_date, "technician": technician},
		as_dict=True,
	)


class WeekStats:
	def for_technician(self, technician: str) -> dict:
		key = self._key(technician)
		cached = frappe.cache.get_value(key)
		if cached:
			return cached
		stats = self._compute(technician)
		frappe.cache.set_value(key, stats, expires_in_sec=WEEK_CACHE_SECONDS)
		return stats

	def clear(self, technician: str) -> None:
		frappe.cache.delete_value(self._key(technician))

	def _compute(self, technician: str) -> dict:
		end = getdate(today())
		start = add_days(end, -6)
		rows = performance(start, end, technician)
		daily = frappe.db.sql(
			"""
			select date(started_at) as day, sum(duration_hours) as hours from `tabJob Visit`
			where technician = %s and status = 'Closed' and date(started_at) between %s and %s
			group by date(started_at)
			""",
			(technician, start, end),
			as_dict=True,
		)
		by_day = {getdate(r.day): flt(r.hours, 2) for r in daily}
		total = rows[0] if rows else {}
		return {
			"from": start.isoformat(),
			"to": end.isoformat(),
			"jobs_done": int(total.get("jobs_done") or 0),
			"visits": int(total.get("visits") or 0),
			"hours": flt(total.get("hours"), 2),
			"days": [
				{"date": add_days(start, i).isoformat(), "hours": by_day.get(add_days(start, i), 0)}
				for i in range(7)
			],
		}

	@staticmethod
	def _key(technician: str) -> str:
		return f"fieldpro:week:{technician}"
