<script setup>
// Book a job for a customer who called in. Choosing a technician now assigns it straight away;
// leaving it empty puts the job in "Needs a technician" on the dashboard.
import { onMounted, ref, watch } from "vue";
import { dialogs } from "../lib/dialogs.js";
import { isoDay } from "../lib/format.js";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import BaseModal from "./BaseModal.vue";

const emit = defineEmits(["close", "booked"]);

const form = ref({
	customer: "",
	issue: "",
	description: "",
	site_address: "",
	contact_phone: "",
	preferred_date: isoDay(),
	technician: "",
});
const customerText = ref("");
const customers = ref([]);
const showCustomers = ref(false);
const technicians = ref([]);
const saving = ref(false);
const error = ref(null);
const modal = ref(null);
let booked = null; // the new job, handed over once the dialog has animated out

// Search customers as the manager types, after a short pause.
let timer = null;
let chosenName = "";
watch(customerText, (text) => {
	if (form.value.customer && text !== chosenName) form.value.customer = "";
	clearTimeout(timer);
	timer = setTimeout(() => findCustomers(text), 200);
});

async function findCustomers(text) {
	try {
		customers.value = (await api.get("manage.customers", { q: text })).data;
	} catch (exc) {
		notify(exc.message, "error");
	}
}

function pickCustomer(customer) {
	chosenName = customer.name;
	customerText.value = customer.name;
	form.value.customer = customer.id;
	showCustomers.value = false;
}

// Let a click on a suggestion land before the list closes.
function hideCustomersSoon() {
	setTimeout(() => (showCustomers.value = false), 150);
}

async function submit() {
	saving.value = true;
	error.value = null;
	try {
		const { data } = await api.post("manage.book_job", form.value);
		notify(`${data.id} booked${data.technician ? ` and assigned to ${data.technician.name}` : ""}`);
		booked = data;
		modal.value.close();
	} catch (exc) {
		error.value = exc;
	} finally {
		saving.value = false;
	}
}

onMounted(async () => {
	findCustomers("");
	// Booked from a customer's row: that customer is already chosen.
	if (dialogs.customer) pickCustomer(dialogs.customer);
	try {
		technicians.value = (await api.get("manage.technicians")).data;
	} catch (exc) {
		console.error("fieldpro: technicians for booking", exc);
	}
});
</script>

<template>
	<BaseModal ref="modal" title="New job" wide @close="booked ? emit('booked', booked) : emit('close')">
		<form id="new-job-form" class="form" @submit.prevent="submit">
			<p class="muted wide intro">Book work for a customer who called in.</p>

			<div class="field wide picker">
				<label for="customer">Customer</label>
				<input
					id="customer"
					v-model="customerText"
					class="input"
					placeholder="Start typing a customer name"
					autocomplete="off"
					required
					@focus="showCustomers = true"
					@blur="hideCustomersSoon"
				/>
				<ul v-if="showCustomers && customers.length" class="suggestions card">
					<li v-for="c in customers" :key="c.id" @mousedown.prevent="pickCustomer(c)">
						<strong>{{ c.name }}</strong>
						<span v-if="c.id !== c.name" class="faint">{{ c.id }}</span>
					</li>
				</ul>
				<span v-if="error?.fields?.customer" class="field-error">{{ error.fields.customer }}</span>
			</div>

			<div class="field wide">
				<label for="issue">What is wrong?</label>
				<input id="issue" v-model="form.issue" class="input" placeholder="e.g. Cold room not cooling" required />
			</div>

			<div class="field wide">
				<label for="description">Details</label>
				<textarea id="description" v-model="form.description" class="input" placeholder="What the customer told you" />
			</div>

			<div class="field wide">
				<label for="site">Site address</label>
				<textarea id="site" v-model="form.site_address" class="input" rows="2" />
			</div>

			<div class="field">
				<label for="phone">Contact phone</label>
				<input id="phone" v-model="form.contact_phone" class="input" type="tel" placeholder="+254…" />
			</div>

			<div class="field">
				<label for="date">Date</label>
				<input id="date" v-model="form.preferred_date" class="input" type="date" :min="isoDay()" />
			</div>

			<div class="field wide">
				<label for="technician">Technician <span class="faint">(optional)</span></label>
				<select id="technician" v-model="form.technician" class="select">
					<option value="">Decide later</option>
					<option v-for="t in technicians" :key="t.id" :value="t.id">
						{{ t.name }} — {{ t.open_jobs }} open, {{ t.today }} today
					</option>
				</select>
			</div>

			<div v-if="error" class="error-banner wide">{{ error.message }}</div>
		</form>

		<template #footer="{ close }">
			<button type="button" class="btn" @click="close">Cancel</button>
			<button type="submit" form="new-job-form" class="btn btn-primary" :disabled="saving || !form.customer">
				{{ saving ? "Booking…" : form.technician ? "Book and assign" : "Book job" }}
			</button>
		</template>
	</BaseModal>
</template>

<style scoped>
.form {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 16px 20px;
}

.wide {
	grid-column: 1 / -1;
}

.intro {
	margin: -6px 0 0;
}

.error-banner {
	margin: 0;
}

.picker {
	position: relative;
}

.suggestions {
	position: absolute;
	top: 100%;
	left: 0;
	right: 0;
	z-index: 10;
	margin: 4px 0 0;
	padding: 4px;
	list-style: none;
	max-height: 240px;
	overflow-y: auto;
	box-shadow: var(--shadow-lift);
}

.suggestions li {
	display: flex;
	justify-content: space-between;
	gap: 8px;
	padding: 8px 10px;
	border-radius: var(--radius-sm);
	cursor: pointer;
}

.suggestions li:hover {
	background: var(--mint-soft);
}

@media (max-width: 600px) {
	.form {
		grid-template-columns: 1fr;
	}
}
</style>
