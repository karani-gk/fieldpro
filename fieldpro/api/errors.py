"""The one error format both sides agree on.

Every fieldpro endpoint fails the same way: an HTTP status that means something, and a body

    {"error": {"code": "not_found", "message": "Service Job JOB-2026-00009 not found", "fields": {}}}

`code` is stable and machine-readable (clients branch on it), `message` is for people, `fields`
names the inputs that were wrong. Frappe's own exceptions are translated here, so a client never
has to parse Frappe's `exc_type` or `_server_messages`.
"""

import frappe
from frappe.model.workflow import WorkflowPermissionError, WorkflowTransitionError
from frappe.utils import strip_html


class ApiError(Exception):
	status = 400
	code = "bad_request"

	def __init__(self, message: str | None = None, *, fields: dict | None = None, code: str | None = None):
		super().__init__(message or self.code)
		self.message = message or self.code.replace("_", " ").capitalize()
		self.fields = fields or {}
		if code:
			self.code = code

	def as_dict(self) -> dict:
		return {"code": self.code, "message": self.message, "fields": self.fields}

	def send(self) -> None:
		"""Write this error as the response. The caller returns None, so Frappe adds no `message`."""
		frappe.local.response.http_status_code = self.status
		frappe.local.response["error"] = self.as_dict()
		# frappe.throw() queued its message for `_server_messages`; this format replaces it.
		frappe.local.message_log = []

	@classmethod
	def from_exception(cls, exc: Exception) -> "ApiError | None":
		"""The API error for an exception, or None when it is a bug (a 500, logged by the caller)."""
		if isinstance(exc, ApiError):
			return exc
		message = _message(exc)
		for frappe_type, api_type in FRAPPE_ERRORS:
			if isinstance(exc, frappe_type):
				if api_type is Forbidden and frappe.session.user == "Guest":
					return Unauthorized(message)
				return api_type(message)
		return None


class Unauthorized(ApiError):
	status = 401
	code = "unauthorized"


class Forbidden(ApiError):
	status = 403
	code = "forbidden"


class NotFound(ApiError):
	status = 404
	code = "not_found"


class Conflict(ApiError):
	status = 409
	code = "conflict"


class InvalidTransition(Conflict):
	code = "invalid_transition"


class Invalid(ApiError):
	status = 422
	code = "invalid"


class RateLimited(ApiError):
	status = 429
	code = "rate_limited"


class ServerError(ApiError):
	status = 500
	code = "server_error"


# Order matters: the first match wins, and the specific errors are subclasses of ValidationError.
FRAPPE_ERRORS: tuple[tuple[type[Exception], type[ApiError]], ...] = (
	(frappe.DoesNotExistError, NotFound),
	(frappe.AuthenticationError, Unauthorized),
	(frappe.SessionExpired, Unauthorized),
	(frappe.PermissionError, Forbidden),
	(WorkflowPermissionError, Forbidden),
	(frappe.TooManyRequestsError, RateLimited),
	(WorkflowTransitionError, InvalidTransition),
	(frappe.TimestampMismatchError, Conflict),
	(frappe.DuplicateEntryError, Conflict),
	(frappe.UniqueValidationError, Conflict),
	(frappe.ValidationError, Invalid),
)


def _message(exc: Exception) -> str:
	text = str(exc.args[0]) if exc.args else str(exc)
	return strip_html(text).strip() or exc.__class__.__name__
