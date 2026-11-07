<script setup>
// Add a customer, often while they are on the phone. ERPNext makes their primary contact from the
// phone and email, and their address from the street and town (customer_directory.py). "Add and
// book a job" goes straight on to the New job dialog with this customer chosen.
import { ref } from "vue";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import BaseModal from "./BaseModal.vue";

// The choices and defaults from manage.customer_form, loaded once by the Customers screen.
const props = defineProps({ choices: { type: Object, required: true } });
const emit = defineEmits(["close", "created"]);

const form = ref({
	customer_name: "",
	customer_type: props.choices.defaults.customer_type,
	mobile_no: "",
	email: "",
	customer_group: props.choices.defaults.customer_group || "",
	territory: props.choices.defaults.territory || "",
	address_line1: "",
	city: "",
});
const saving = ref(false);
const error = ref(null);
const modal = ref(null);
const formEl = ref(null);
let created = null; // {customer, book}, handed over once the dialog has animated out

async function save(book) {
	saving.value = true;
	error.value = null;
	try {
		const { data } = await api.post("manage.add_customer", form.value);
		notify(`${data.name} added`);
		created = { customer: data, book };
		modal.value.close();
	} catch (exc) {
		error.value = exc;
	} finally {
		saving.value = false;
	}
}

// Outside the form, so the browser's own checks (a town once a street is given) run first.
function saveAndBook() {
	if (formEl.value.reportValidity()) save(true);
}

const fieldError = (name) => error.value?.fields?.[name];
</script>

<template>
	<BaseModal ref="modal" title="New customer" wide @close="created ? emit('created', created) : emit('close')">
		<form id="new-customer-form" ref="formEl" class="form" @submit.prevent="save(false)">
			<p class="muted wide intro">Only the name is needed. Contact details help technicians reach the site.</p>

			<div class="field wide">
				<label for="c-name">Name</label>
				<input
					id="c-name"
					v-model="form.customer_name"
					class="input"
					:class="{ invalid: fieldError('customer_name') }"
					placeholder="e.g. Wanjiku Clinic"
					autocomplete="off"
					required
				/>
				<span v-if="fieldError('customer_name')" class="field-error">{{ error.message }}</span>
			</div>

			<div class="field wide">
				<span class="label">Type</span>
				<div class="segments" role="radiogroup" aria-label="Customer type">
					<label
						v-for="type in choices.customer_types"
						:key="type"
						class="segment"
						:class="{ chosen: form.customer_type === type }"
					>
						<input v-model="form.customer_type" type="radio" :value="type" />
						{{ type }}
					</label>
				</div>
			</div>

			<div class="field">
				<label for="c-phone">Mobile</label>
				<input id="c-phone" v-model="form.mobile_no" class="input" type="tel" placeholder="+254 7…" />
			</div>
			<div class="field">
				<label for="c-email">Email</label>
				<input
					id="c-email"
					v-model="form.email"
					class="input"
					:class="{ invalid: fieldError('email') }"
					type="email"
					placeholder="name@example.com"
				/>
				<span v-if="fieldError('email')" class="field-error">{{ error.message }}</span>
			</div>

			<div class="field">
				<label for="c-street">Street address</label>
				<input id="c-street" v-model="form.address_line1" class="input" placeholder="Building, road" />
			</div>
			<div class="field">
				<label for="c-city">Town or city</label>
				<input
					id="c-city"
					v-model="form.city"
					class="input"
					:class="{ invalid: fieldError('city') }"
					:required="!!form.address_line1.trim()"
				/>
				<span v-if="fieldError('city')" class="field-error">{{ error.message }}</span>
			</div>

			<div class="field">
				<label for="c-group">Customer group</label>
				<select id="c-group" v-model="form.customer_group" class="select">
					<option v-for="group in choices.customer_groups" :key="group">{{ group }}</option>
				</select>
			</div>
			<div class="field">
				<label for="c-territory">Territory</label>
				<select id="c-territory" v-model="form.territory" class="select">
					<option v-for="place in choices.territories" :key="place">{{ place }}</option>
				</select>
			</div>

			<!-- An error that is not about one field (permission, server) shows here. -->
			<div v-if="error && !Object.keys(error.fields || {}).length" class="error-banner wide" role="alert">
				{{ error.message }}
			</div>
		</form>

		<template #footer="{ close }">
			<button type="button" class="btn" :disabled="saving" @click="close">Cancel</button>
			<button
				type="button"
				class="btn"
				:disabled="saving || !form.customer_name.trim()"
				@click="saveAndBook"
			>
				Add and book a job
			</button>
			<button type="submit" form="new-customer-form" class="btn btn-primary" :disabled="saving || !form.customer_name.trim()">
				{{ saving ? "Adding…" : "Add customer" }}
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

.label {
	font-weight: 500;
	font-size: 13px;
	color: var(--text-muted);
}

.input.invalid {
	border-color: var(--danger);
}

.segments {
	display: inline-flex;
	align-self: flex-start;
	gap: 4px;
	padding: 3px;
	border: 1px solid var(--border);
	border-radius: var(--radius-sm);
	background: var(--surface-muted);
}

.segment {
	padding: 5px 12px;
	border-radius: 4px;
	font-size: 13px;
	font-weight: 500;
	color: var(--text-muted);
	cursor: pointer;
}

.segment input {
	position: absolute;
	opacity: 0;
	pointer-events: none;
}

.segment.chosen {
	background: var(--surface);
	color: var(--text);
	box-shadow: var(--shadow);
}

.segment:has(input:focus-visible) {
	outline: 2px solid var(--brand);
}

@media (max-width: 600px) {
	.form {
		grid-template-columns: 1fr;
	}
}
</style>
