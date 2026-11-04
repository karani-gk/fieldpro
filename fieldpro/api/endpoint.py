"""The decorator every fieldpro endpoint uses.

    @api(methods=["GET"])
    def list_jobs(cursor=None): ...

It whitelists the function (so it is callable at /api/method/<dotted.path>), limits the HTTP
methods, and turns any failure into the one error format (errors.py). Endpoints stay thin: they
read arguments, call a service and return `{"data": ...}`. The rules live in fieldpro.services.
"""

import functools

import frappe

from fieldpro.api.errors import ApiError, ServerError


def api(*, methods: tuple[str, ...] | list[str] = ("GET",), allow_guest: bool = False):
	def decorator(fn):
		@functools.wraps(fn)
		def endpoint(*args, **kwargs):
			try:
				return fn(*args, **kwargs)
			except Exception as exc:
				# We answered instead of raising, so Frappe will not roll back for us. Undo any
				# half-done writes first: an error response must never leave a partial change.
				frappe.db.rollback()
				error = ApiError.from_exception(exc)
				if error is None:
					log = frappe.log_error(title=f"fieldpro API: {fn.__module__}.{fn.__name__}")
					error = ServerError(f"Something went wrong on the server. Reference: {log.name}")
				error.send()
				return None

		return frappe.whitelist(allow_guest=allow_guest, methods=list(methods))(endpoint)

	return decorator


def ok(data, **meta) -> dict:
	"""A success body: {"data": ..., plus paging fields such as next_cursor}."""
	return {"data": data, **meta}
