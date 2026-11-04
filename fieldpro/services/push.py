"""Push notifications to the technician's phone, through Firebase Cloud Messaging (HTTP v1).

Senders are strategies: FcmSender talks to Google, LogSender writes to logs/fieldpro.push.log.
Development and tests use the log sender, so nothing ever reaches a real phone by accident;
production turns on "Send Push Notifications" in Fieldpro Settings and adds a service account.
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Protocol

import frappe
import jwt
import requests

from fieldpro.settings import AppSettings

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
ACCESS_TOKEN_CACHE_KEY = "fieldpro:fcm_access_token"


@dataclass
class PushMessage:
	title: str
	body: str
	data: dict = field(default_factory=dict)


class PushSender(Protocol):
	def send(self, token: str, message: PushMessage) -> bool:
		"""Deliver one message. False means the token is dead and should be forgotten."""


class LogSender:
	def send(self, token: str, message: PushMessage) -> bool:
		frappe.logger("fieldpro.push").info(
			{"token": token[:12] + "...", "title": message.title, "body": message.body, "data": message.data}
		)
		return True


class FcmSender:
	def __init__(self, service_account: dict):
		self.account = service_account

	def send(self, token: str, message: PushMessage) -> bool:
		url = f"https://fcm.googleapis.com/v1/projects/{self.account['project_id']}/messages:send"
		body = {
			"message": {
				"token": token,
				"notification": {"title": message.title, "body": message.body},
				# FCM data values must be strings.
				"data": {k: str(v) for k, v in message.data.items()},
			}
		}
		response = requests.post(
			url, json=body, headers={"Authorization": f"Bearer {self._access_token()}"}, timeout=10
		)
		if response.status_code in (400, 404) and "UNREGISTERED" in response.text:
			return False
		response.raise_for_status()
		return True

	def _access_token(self) -> str:
		cached = frappe.cache.get_value(ACCESS_TOKEN_CACHE_KEY)
		if cached:
			return cached
		now = int(time.time())
		assertion = jwt.encode(
			{
				"iss": self.account["client_email"],
				"scope": FCM_SCOPE,
				"aud": GOOGLE_TOKEN_URL,
				"iat": now,
				"exp": now + 3600,
			},
			self.account["private_key"],
			algorithm="RS256",
		)
		response = requests.post(
			GOOGLE_TOKEN_URL,
			data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
			timeout=10,
		)
		response.raise_for_status()
		token = response.json()["access_token"]
		# Google's tokens last an hour; refresh ten minutes early.
		frappe.cache.set_value(ACCESS_TOKEN_CACHE_KEY, token, expires_in_sec=3000)
		return token


class PushService:
	def __init__(self, sender: PushSender | None = None, settings: AppSettings | None = None):
		self.settings = settings or AppSettings()
		self.sender = sender or self._default_sender()

	def notify_user(self, user: str, message: PushMessage) -> int:
		"""Send to every device the user registered. Returns how many accepted it."""
		sent = 0
		for row in frappe.get_all("Device Token", filters={"user": user}, fields=["name", "token"]):
			try:
				if self.sender.send(row.token, message):
					sent += 1
				else:
					frappe.delete_doc("Device Token", row.name, ignore_permissions=True)
			except Exception:
				# One bad device must not stop the others; the error is logged with its context.
				frappe.log_error(title=f"fieldpro push failed for {user}")
		return sent

	def _default_sender(self) -> PushSender:
		if self.settings.push_enabled and self.settings.fcm_service_account:
			return FcmSender(self.settings.fcm_service_account)
		return LogSender()


class DeviceRegistry:
	def register(self, user: str, token: str, platform: str = "web") -> str:
		token_hash = hashlib.sha256(token.encode()).hexdigest()
		name = frappe.db.get_value("Device Token", {"token_hash": token_hash}, "name")
		doc = frappe.get_doc("Device Token", name) if name else frappe.new_doc("Device Token")
		# A phone that changes hands belongs to whoever registered it last.
		doc.update(
			{
				"user": user,
				"token": token,
				"token_hash": token_hash,
				"platform": platform,
				"last_seen": frappe.utils.now_datetime(),
			}
		)
		doc.flags.ignore_permissions = True
		doc.save()
		return doc.name

	def unregister(self, user: str, token: str) -> None:
		token_hash = hashlib.sha256(token.encode()).hexdigest()
		for name in frappe.get_all(
			"Device Token", filters={"token_hash": token_hash, "user": user}, pluck="name"
		):
			frappe.delete_doc("Device Token", name, ignore_permissions=True)


def notify_user(user: str, title: str, body: str, data: dict | None = None) -> None:
	"""Background job entry point (job_events.py)."""
	PushService().notify_user(user, PushMessage(title, body, data or {}))
