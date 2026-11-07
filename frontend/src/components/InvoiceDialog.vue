<script setup>
// One invoice, opened from the Invoices list: who it bills, for which job, every line and total.
// A draft can be submitted from here; "Submit" asks once more in the footer (it posts the ledger
// and takes the parts out of the van), so no second dialog opens on top of this one.
import { ref } from "vue";
import { dayLabel, money } from "../lib/format.js";
import { invoiceTone } from "../lib/invoices.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import AppIcon from "./AppIcon.vue";
import BaseModal from "./BaseModal.vue";
import StatusBadge from "./StatusBadge.vue";

const props = defineProps({ id: { type: String, required: true } });
const emit = defineEmits(["close", "changed"]);

const invoice = ref(null);
const error = ref(null);
const confirming = ref(false);
const submitting = ref(false);
const modal = ref(null);

async function load() {
	try {
		invoice.value = (await api.get("manage.invoice", { invoice: props.id })).data;
	} catch (exc) {
		error.value = exc;
	}
}
load();

async function submit() {
	submitting.value = true;
	try {
		const { data } = await api.post("manage.submit_invoice", { invoice: props.id });
		notify(`${data.id} submitted`);
		emit("changed", data);
		confirming.value = false;
		await load();
	} catch (exc) {
		notify(exc.message, "error");
	} finally {
		submitting.value = false;
	}
}
</script>

<template>
	<BaseModal ref="modal" :title="id" wide @close="emit('close')">
		<div v-if="error" class="error-banner">{{ error.message }}</div>
		<p v-else-if="!invoice" class="faint">Loading…</p>

		<div v-else class="invoice">
			<div class="facts">
				<div>
					<span class="label">Status</span>
					<StatusBadge :status="invoice.status" :tone="invoiceTone(invoice.status)" />
				</div>
				<div>
					<span class="label">Customer</span>
					<RouterLink :to="{ path: '/invoices', query: { customer: invoice.customer.id } }" @click="modal.close()">
						{{ invoice.customer.name }}
					</RouterLink>
				</div>
				<div>
					<span class="label">Job</span>
					<RouterLink :to="`/jobs/${invoice.job}`" @click="modal.close()">{{ invoice.job }}</RouterLink>
					<small v-if="invoice.issue" class="faint">{{ invoice.issue }}</small>
				</div>
				<div v-if="invoice.technician">
					<span class="label">Technician</span>
					<span>{{ invoice.technician.name }}</span>
				</div>
				<div>
					<span class="label">Date</span>
					<span>{{ dayLabel(invoice.posting_date) }}</span>
				</div>
				<div v-if="!invoice.is_draft && invoice.due_date">
					<span class="label">Due</span>
					<span>{{ dayLabel(invoice.due_date) }}</span>
				</div>
			</div>

			<div class="lines">
				<table class="data-table">
					<thead>
						<tr>
							<th>Item</th>
							<th class="num">Qty</th>
							<th class="num">Rate</th>
							<th class="num">Amount</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(line, i) in invoice.items" :key="i">
							<td>
								<strong>{{ line.item_name }}</strong>
								<div class="faint small">
									{{ line.item_code }}<template v-if="line.description"> · {{ line.description }}</template>
								</div>
							</td>
							<td class="num">{{ line.qty }} {{ line.uom }}</td>
							<td class="num">{{ money(line.rate) }}</td>
							<td class="num">{{ money(line.amount) }}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<dl class="totals">
				<div>
					<dt>Net total</dt>
					<dd>{{ money(invoice.net_total) }}</dd>
				</div>
				<div v-if="invoice.discount">
					<dt>Discount</dt>
					<dd>− {{ money(invoice.discount) }}</dd>
				</div>
				<div v-for="(tax, i) in invoice.taxes" :key="i">
					<dt>{{ tax.description }}</dt>
					<dd>{{ money(tax.amount) }}</dd>
				</div>
				<div class="grand">
					<dt>Total</dt>
					<dd>{{ money(invoice.grand_total) }}</dd>
				</div>
				<div v-if="!invoice.is_draft" :class="{ owed: Number(invoice.outstanding.amount) > 0 }">
					<dt>Still owed</dt>
					<dd>{{ money(invoice.outstanding) || "0.00" }}</dd>
				</div>
			</dl>

			<p v-if="invoice.remarks" class="remarks muted">{{ invoice.remarks }}</p>
		</div>

		<template #footer="{ close }">
			<template v-if="confirming">
				<span class="warn">Submitting posts it to the accounts and takes the parts out of the van.</span>
				<button class="btn" :disabled="submitting" @click="confirming = false">Not yet</button>
				<button class="btn btn-primary" :disabled="submitting" @click="submit">
					{{ submitting ? "Submitting…" : "Submit invoice" }}
				</button>
			</template>
			<template v-else>
				<a :href="`/app/sales-invoice/${id}`" class="btn btn-ghost" title="Open in Desk">
					<AppIcon name="external" :size="15" /> Desk
				</a>
				<a v-if="invoice" :href="invoice.pdf_url" class="btn" target="_blank">
					<AppIcon name="download" :size="15" /> PDF
				</a>
				<button class="btn" @click="close">Close</button>
				<button v-if="invoice?.is_draft" class="btn btn-primary" @click="confirming = true">Submit</button>
			</template>
		</template>
	</BaseModal>
</template>

<style scoped>
.facts {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
	gap: 14px 20px;
	margin-bottom: 18px;
}

.facts div {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 3px;
	min-width: 0;
}

.label {
	font-size: 12px;
	font-weight: 600;
	color: var(--text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.facts small {
	max-width: 100%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.lines {
	overflow-x: auto;
	border: 1px solid var(--border);
	border-radius: var(--radius-sm);
}

.small {
	font-size: 12px;
}

.totals {
	display: flex;
	flex-direction: column;
	gap: 6px;
	width: min(320px, 100%);
	margin: 16px 0 0 auto;
}

.totals div {
	display: flex;
	justify-content: space-between;
	gap: 16px;
}

.totals dt {
	color: var(--text-muted);
}

.totals dd {
	margin: 0;
	font-variant-numeric: tabular-nums;
}

.totals .grand {
	padding-top: 8px;
	border-top: 1px solid var(--border);
	font-size: 16px;
	font-weight: 650;
}

.totals .grand dt {
	color: var(--text);
}

.totals .owed {
	color: var(--red-fg);
	font-weight: 600;
}

.totals .owed dt {
	color: inherit;
}

.remarks {
	margin: 16px 0 0;
	font-size: 13px;
}

.warn {
	margin-right: auto;
	font-size: 13px;
	color: var(--amber-fg);
}
</style>
