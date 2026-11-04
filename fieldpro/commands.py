"""Bench commands from this app (Frappe loads `commands` from <app>.commands)."""

import click
from frappe.commands import get_site, pass_context


@click.command("fieldpro-demo")
@pass_context
def fieldpro_demo(context):
	"""Load the Baridi Services demo: company, technicians, customers, stock and jobs."""
	import frappe

	from fieldpro.demo import DemoData

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		DemoData().seed()
	finally:
		frappe.destroy()


commands = [fieldpro_demo]
