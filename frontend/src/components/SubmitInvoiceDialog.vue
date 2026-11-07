<script setup>
// Submit a draft invoice, with the due date the manager chooses. A draft posts on the day it is
// submitted but keeps the due date it was drafted with, so an older draft would fail ERPNext's
// "Due Date cannot be before Posting Date": the date offered here is never before the posting
// day. If the server still refuses, its message stays in this dialog so the date can be changed
// and the submit tried again.
import { ref } from "vue";
import { dayLabel, money } from "../lib/format.js";
import { suggestedDueDate } from "../lib/invoices.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ invoice: { type: Object, required: true } });
const emit = defineEmits(["close", "submitted"]);

const dueDate = ref(suggestedDueDate(props.invoice));
const saving = ref(false);
const error = ref(null);
const modal = ref(null);
let submitted = null; // the updated row, handed over once the dialog has animated out

async function submit() {
	saving.value = true;
	error.value = null;
	try {
		const { data } = await api.post("manage.submit_invoice", {
			invoice: props.invoice.id,
			due_date: dueDate.value,
		});
		notify(`${data.id} submitted, due ${dayLabel(data.due_date)}`);
		submitted = data;
		modal.value.close();
	} catch (exc) {
		error.value = exc;
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<BaseModal
		ref="modal"
		:title="`Submit ${invoice.id}?`"
		@close="submitted ? emit('submitted', submitted) : emit('close')"
	>
		<form id="submit-invoice-form" class="form" @submit.prevent="submit">
			<p class="muted">
				{{ money(invoice.total) }} to {{ invoice.customer.name }}. Submitting posts it to the accounts and takes the
				parts out of the technician's van. To change it afterwards, accounts must cancel it in Desk.
			</p>

			<div class="dates">
				<div class="field">
					<span class="label">Posting date</span>
					<strong>{{ dayLabel(invoice.posts_on) }}</strong>
				</div>
				<div class="field">
					<label for="due-date">Due date</label>
					<input
						id="due-date"
						v-model="dueDate"
						class="input"
						:class="{ invalid: error?.fields?.due_date }"
						type="date"
						:min="invoice.posts_on"
						required
					/>
				</div>
			</div>

			<div v-if="error" class="problem" role="alert">
				<strong>The invoice was not submitted</strong>
				<p>{{ error.message }}</p>
				<p v-if="error.fields?.due_date" class="small">Choose a due date on or after the posting date, then submit again.</p>
			</div>
		</form>

		<template #footer="{ close }">
			<button class="btn" :disabled="saving" @click="close">Not yet</button>
			<button type="submit" form="submit-invoice-form" class="btn btn-primary" :disabled="saving || !dueDate">
				{{ saving ? "Submitting…" : "Submit invoice" }}
			</button>
		</template>
	</BaseModal>
</template>

<style scoped>
.form {
	display: flex;
	flex-direction: column;
	gap: 16px;
}

.form p {
	margin: 0;
}

.dates {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 14px;
	align-items: start;
}

.label {
	font-weight: 500;
	font-size: 13px;
	color: var(--text-muted);
}

.dates strong {
	line-height: 36px;
}

.input.invalid {
	border-color: var(--danger);
}

.problem {
	padding: 12px 14px;
	border-radius: var(--radius-sm);
	background: var(--danger-soft);
	color: var(--danger);
}

.problem p {
	margin-top: 4px;
}

.small {
	font-size: 12px;
}
</style>
