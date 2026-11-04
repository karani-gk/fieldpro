"""Phone sign-in for technicians: a six-digit code by email or SMS, exchanged for an API token.

The technician types their mobile number either way; Fieldpro Settings decides where the code
goes. Email is the default because it reaches every country with no gateway to pay for.

The mobile pattern: the app never holds a password. It proves the phone number once and gets the
technician's own key and secret, which it sends on every request as
`Authorization: token <key>:<secret>`. Signing in on a new phone issues a new secret, which signs
the old phone out.

Codes are stored hashed, expire in five minutes, allow five guesses and three sends per ten
minutes. An unknown number gets the same answer as a known one, so the endpoint cannot be used
to find out who works here.
"""

import hashlib
import hmac
import secrets
from typing import Protocol

import frappe
from frappe import _

from fieldpro.api.errors import RateLimited, Unauthorized
from fieldpro.settings import AppSettings
from fieldpro.utils import normalise_mobile

CODE_TTL = 300
MAX_GUESSES = 5
MAX_SENDS = 3
SEND_WINDOW = 600


class SmsGateway(Protocol):
	def send(self, number: str, message: str) -> None: ...


class FrappeSmsGateway:
	"""The gateway configured in SMS Settings (Africa's Talking, Twilio, any HTTP gateway)."""

	def send(self, number: str, message: str) -> None:
		from frappe.core.doctype.sms_settings.sms_settings import send_sms

		send_sms([number], message, success_msg=False)


class LogSmsGateway:
	"""Development: no SMS is sent. The message is saved as an SMS Log you can read in Desk."""

	def send(self, number: str, message: str) -> None:
		frappe.get_doc(
			{
				"doctype": "SMS Log",
				"sender_name": "fieldpro (not sent)",
				"sent_on": frappe.utils.today(),
				"message": message,
				"requested_numbers": number,
				"no_of_requested_sms": 1,
			}
		).insert(ignore_permissions=True)
		frappe.logger("fieldpro.sms").info({"to": number, "message": message})


def default_gateway() -> SmsGateway:
	if frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		return FrappeSmsGateway()
	return LogSmsGateway()


class EmailSender(Protocol):
	def send(self, email: str, message: str) -> None: ...


class EmailCodeSender:
	"""Frappe's email queue, sent through the outgoing Email Account."""

	def send(self, email: str, message: str) -> None:
		frappe.sendmail(
			recipients=[email],
			subject=_("Your fieldpro sign-in code"),
			message=message,
			# A sign-in code is not a newsletter: no unsubscribe link to switch it off.
			add_unsubscribe_link=0,
		)


class UnsentEmailLog:
	"""Development, with no outgoing Email Account: Frappe refuses to queue the email, so nothing
	is sent. The code is saved in SMS Log, where the course has always shown it, with the address
	it would have gone to."""

	def send(self, email: str, message: str) -> None:
		LogSmsGateway().send(email, message)


def default_email_sender() -> EmailSender:
	from frappe.email.doctype.email_account.email_account import EmailAccount

	# find_outgoing() also counts the site_config account and the dummy one used when emails are muted.
	if EmailAccount.find_outgoing():
		return EmailCodeSender()
	return UnsentEmailLog()


class CodeDelivery(Protocol):
	def deliver(self, technician, mobile: str, message: str) -> None: ...


class SmsDelivery:
	def __init__(self, gateway: SmsGateway):
		self.gateway = gateway

	def deliver(self, technician, mobile: str, message: str) -> None:
		self.gateway.send(mobile, message)


class EmailDelivery:
	"""To the email of the technician's user, the address they already sign in to Frappe with."""

	def __init__(self, sender: EmailSender | None = None):
		self.sender = sender or default_email_sender()

	def deliver(self, technician, mobile: str, message: str) -> None:
		email = frappe.db.get_value("User", technician.user, "email")
		if not email:
			# Raising would tell the caller this number is a technician; log it for the manager.
			frappe.log_error(
				title="fieldpro: sign-in code not sent",
				message=f"Technician {technician.name} ({technician.user}) has no email address.",
			)
			return
		self.sender.send(email, message)


def default_delivery(settings: AppSettings | None = None) -> CodeDelivery:
	channels = {"Email": EmailDelivery, "SMS": lambda: SmsDelivery(default_gateway())}
	return channels[(settings or AppSettings()).sign_in_code_channel]()


class OtpService:
	def __init__(
		self,
		sms: SmsGateway | None = None,
		tokens: "TokenIssuer | None" = None,
		delivery: CodeDelivery | None = None,
	):
		# A caller that hands in an SMS gateway means SMS, whatever the setting says.
		self.delivery = delivery or (SmsDelivery(sms) if sms else default_delivery())
		self.tokens = tokens or TokenIssuer()

	def request(self, mobile_no: str) -> None:
		mobile = normalise_mobile(mobile_no)
		self._count_send(mobile)
		technician = self._technician(mobile)
		if not technician:
			return
		code = f"{secrets.randbelow(10**6):06d}"
		frappe.cache.set_value(
			self._key(mobile), {"hash": self._hash(mobile, code), "guesses": 0}, expires_in_sec=CODE_TTL
		)
		self.delivery.deliver(
			technician,
			mobile,
			_("Your fieldpro sign-in code is {0}. It expires in 5 minutes.").format(code),
		)

	def verify(self, mobile_no: str, code: str) -> dict:
		mobile = normalise_mobile(mobile_no)
		entry = frappe.cache.get_value(self._key(mobile))
		if not entry:
			raise Unauthorized(_("The code has expired. Ask for a new one."), code="code_expired")
		entry["guesses"] += 1
		if entry["guesses"] > MAX_GUESSES:
			frappe.cache.delete_value(self._key(mobile))
			raise RateLimited(_("Too many wrong codes. Ask for a new one."))
		if not hmac.compare_digest(entry["hash"], self._hash(mobile, (code or "").strip())):
			frappe.cache.set_value(self._key(mobile), entry, expires_in_sec=CODE_TTL)
			raise Unauthorized(_("That code is not right."), code="wrong_code")
		frappe.cache.delete_value(self._key(mobile))
		technician = self._technician(mobile)
		if not technician:
			raise Unauthorized(_("This number is no longer an active technician."))
		return {
			"token": self.tokens.issue(technician.user),
			"user": technician.user,
			"technician": {"id": technician.name, "name": technician.full_name},
		}

	def _count_send(self, mobile: str) -> None:
		key = f"fieldpro:otp_sends:{mobile}"
		sends = (frappe.cache.get_value(key) or 0) + 1
		if sends > MAX_SENDS:
			raise RateLimited(_("Too many codes sent to this number. Wait ten minutes."))
		frappe.cache.set_value(key, sends, expires_in_sec=SEND_WINDOW)

	@staticmethod
	def _technician(mobile: str):
		return frappe.db.get_value(
			"Technician", {"mobile_no": mobile, "is_active": 1}, ["name", "user", "full_name"], as_dict=True
		)

	@staticmethod
	def _key(mobile: str) -> str:
		return f"fieldpro:otp:{mobile}"

	@staticmethod
	def _hash(mobile: str, code: str) -> str:
		return hashlib.sha256(
			f"{mobile}:{code}:{frappe.local.conf.get('encryption_key', '')}".encode()
		).hexdigest()


class TokenIssuer:
	"""API key and secret on the User: Frappe checks `Authorization: token key:secret` itself."""

	def issue(self, user: str) -> str:
		doc = frappe.get_doc("User", user)
		doc.api_key = doc.api_key or frappe.generate_hash(length=15)
		secret = frappe.generate_hash(length=15)
		doc.api_secret = secret
		doc.flags.ignore_permissions = True
		doc.save()
		return f"{doc.api_key}:{secret}"

	def revoke(self, user: str) -> None:
		"""A new secret nobody knows: every device holding the old one is signed out."""
		doc = frappe.get_doc("User", user)
		doc.api_secret = frappe.generate_hash(length=15)
		doc.flags.ignore_permissions = True
		doc.save()
