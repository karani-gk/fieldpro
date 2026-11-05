"""The Kanban board managers open from the Field Service workspace: one column per workflow state.

Number cards, charts and the workspace ship as standard files that Frappe syncs on every migrate.
A Kanban Board has no "standard" flag, so there is no file to ship: this creates it once, on
install and on migrate. It never overwrites a board that exists, because managers reorder cards
and recolour columns, and a migrate must not undo their work.
"""

import frappe

from fieldpro.services.job_rules import CANCELLED

BOARD_NAME = "Job Board"

# Kanban column colours from the workflow state styles, so the board matches the job form.
INDICATOR_FOR_STYLE = {
	"Primary": "Blue",
	"Info": "Light Blue",
	"Success": "Green",
	"Warning": "Orange",
	"Danger": "Red",
	"Inverse": "Gray",
}

# Closed jobs pile up for ever; the board is for work in flight, so Cancelled starts archived.
ARCHIVED_STATES = frozenset({CANCELLED})

# What a card shows besides the job's title (issue).
CARD_FIELDS = ["customer_name", "technician_name", "scheduled_date"]


class JobBoard:
	def __init__(self, doctype: str = "Service Job"):
		self.doctype = doctype

	def ensure(self) -> bool:
		"""Create the board if it is missing. Returns True when it was created."""
		if frappe.db.exists("Kanban Board", BOARD_NAME):
			return False
		workflow = self._workflow()
		if not workflow:
			# Fixtures load before after_install / after_migrate, so this means a broken install.
			frappe.log_error(f"No workflow for {self.doctype}", "Job Board not created")
			return False
		board = frappe.new_doc("Kanban Board")
		board.kanban_board_name = BOARD_NAME
		board.reference_doctype = self.doctype
		# Dragging a card saves the job, so the workflow and JobRules still decide which moves
		# are allowed: an illegal move is refused like any other save.
		board.field_name = workflow.workflow_state_field
		board.fields = frappe.as_json(CARD_FIELDS)
		board.private = 0
		for state in workflow.states:
			board.append("columns", self._column(state.state))
		board.insert(ignore_permissions=True)
		return True

	def _workflow(self):
		name = frappe.db.get_value("Workflow", {"document_type": self.doctype, "is_active": 1})
		return frappe.get_doc("Workflow", name) if name else None

	def _column(self, state: str) -> dict:
		style = frappe.db.get_value("Workflow State", state, "style")
		return {
			"column_name": state,
			"indicator": INDICATOR_FOR_STYLE.get(style, "Gray"),
			"status": "Archived" if state in ARCHIVED_STATES else "Active",
		}


def ensure_job_board() -> None:
	"""after_install and after_migrate hook."""
	JobBoard().ensure()
