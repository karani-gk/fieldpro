<script setup>
// The everyday Fieldpro Settings: approvals, what an hour of labour bills, how technicians get
// their sign-in code, and whether Desk sends field managers here. Secrets (push key, webhook
// secrets) and activation stay in Desk: the server never sends them to this screen.
import { computed, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { api } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import { useRequest } from "../lib/useRequest.js";

const FIELDS = ["approval_threshold", "labour_item", "labour_rate", "sign_in_code_channel", "keep_managers_in_desk"];

const form = ref(null);
const saving = ref(false);
const saveError = ref(null);

const { data, error } = useRequest(async () => (await api.get("manage.settings")).data);
// The form is a copy of what was loaded; a later reload (back to the tab) keeps unsaved edits.
watch(data, (settings) => {
	if (settings && !dirty.value) form.value = pick(settings);
});

function pick(settings) {
	return Object.fromEntries(FIELDS.map((f) => [f, settings[f]]));
}

// Only what changed is sent, so two managers editing different settings do not undo each other.
const changes = computed(() => {
	if (!data.value || !form.value) return {};
	const saved = pick(data.value);
	return Object.fromEntries(FIELDS.filter((f) => form.value[f] !== saved[f]).map((f) => [f, form.value[f]]));
});
const dirty = computed(() => Object.keys(changes.value).length > 0);

async function save() {
	saving.value = true;
	saveError.value = null;
	try {
		data.value = (await api.post("manage.update_settings", { changes: changes.value })).data;
		form.value = pick(data.value);
		notify("Settings saved");
	} catch (exc) {
		saveError.value = exc;
	} finally {
		saving.value = false;
	}
}

function undo() {
	form.value = pick(data.value);
	saveError.value = null;
}

const fieldError = (name) => saveError.value?.fields?.[name];
</script>

<template>
	<div class="page settings">
		<div class="page-head">
			<div>
				<h1>Settings</h1>
				<p>How jobs are approved and billed, and how people sign in.</p>
			</div>
			<a href="/app/fieldpro-settings" class="btn" title="Push notifications, webhooks and activation">
				<AppIcon name="external" :size="16" /> All settings in Desk
			</a>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>
		<p v-else-if="!data || !form" class="faint">Loading…</p>

		<form v-else class="sections" @submit.prevent="save">
			<p v-if="!data.can_edit" class="notice">You can see these settings. Ask a System Manager to change them.</p>

			<fieldset :disabled="!data.can_edit || saving">
				<section class="card section">
					<header>
						<h2>Approvals</h2>
						<p class="muted">A job estimated above this waits for a manager before the customer signs off.</p>
					</header>
					<div class="field">
						<label for="approval_threshold">Approve jobs above ({{ data.currency }})</label>
						<input
							id="approval_threshold"
							v-model.number="form.approval_threshold"
							class="input"
							type="number"
							min="0"
							step="any"
						/>
						<span class="hint">0 means every job needs approval.</span>
						<span v-if="fieldError('approval_threshold')" class="field-error">{{ saveError.message }}</span>
					</div>
				</section>

				<section class="card section">
					<header>
						<h2>Invoicing</h2>
						<p class="muted">Each finished job's invoice bills its hours on this item, at this rate, plus the parts used.</p>
					</header>
					<div class="grid">
						<div class="field">
							<label for="labour_item">Labour item</label>
							<select id="labour_item" v-model="form.labour_item" class="select">
								<option value="">None: bill parts only</option>
								<option v-for="item in data.choices.labour_item" :key="item.id" :value="item.id">
									{{ item.name }} ({{ item.id }})
								</option>
							</select>
							<span v-if="fieldError('labour_item')" class="field-error">{{ saveError.message }}</span>
						</div>
						<div class="field">
							<label for="labour_rate">Rate per hour ({{ data.currency }})</label>
							<input
								id="labour_rate"
								v-model.number="form.labour_rate"
								class="input"
								type="number"
								min="0"
								step="any"
							/>
							<span v-if="fieldError('labour_rate')" class="field-error">{{ saveError.message }}</span>
						</div>
					</div>
				</section>

				<section class="card section">
					<header>
						<h2>Technician sign-in</h2>
						<p class="muted">How a technician who signs in with their phone number gets the one-time code.</p>
					</header>
					<div class="choices" role="radiogroup" aria-label="Send sign-in codes by">
						<label
							v-for="channel in data.choices.sign_in_code_channel"
							:key="channel"
							class="choice"
							:class="{ chosen: form.sign_in_code_channel === channel }"
						>
							<input v-model="form.sign_in_code_channel" type="radio" :value="channel" />
							<strong>{{ channel }}</strong>
							<span class="muted">
								{{
									channel === "SMS"
										? "Uses the gateway in Desk's SMS Settings. Each code costs a message."
										: "Free, and works in any country. Needs an outgoing email account."
								}}
							</span>
						</label>
					</div>
					<span v-if="fieldError('sign_in_code_channel')" class="field-error">{{ saveError.message }}</span>
				</section>

				<section class="card section">
					<header>
						<h2>Manager app</h2>
					</header>
					<label class="toggle">
						<input v-model="form.keep_managers_in_desk" type="checkbox" />
						<span>
							<strong>Keep field managers in Desk</strong>
							<span class="muted">
								Off: field managers who open Desk land here. On: they stay in Desk. System Managers are never sent here.
							</span>
						</span>
					</label>
				</section>

				<section class="card section readonly">
					<header>
						<h2>Company</h2>
						<p class="muted">Jobs and invoices are made for this company, in {{ data.currency }}.</p>
					</header>
					<strong>{{ data.company || "Not set" }}</strong>
				</section>
			</fieldset>

			<div v-if="data.can_edit" class="save-bar" :class="{ shown: dirty }">
				<span>You have unsaved changes.</span>
				<button type="button" class="btn btn-ghost" :disabled="saving" @click="undo">Undo</button>
				<button type="submit" class="btn btn-primary" :disabled="saving || !dirty">
					{{ saving ? "Saving…" : "Save changes" }}
				</button>
			</div>
		</form>
	</div>
</template>

<style scoped>
/* A readable column, aligned with the other pages' left edge. */
.settings .page-head,
.settings .sections {
	max-width: 860px;
}

.sections fieldset {
	display: flex;
	flex-direction: column;
	gap: 16px;
	margin: 0;
	padding: 0;
	border: 0;
	min-width: 0;
}

.section {
	display: flex;
	flex-direction: column;
	gap: 14px;
	padding: 20px;
}

.section h2 {
	font-size: 15px;
	font-weight: 600;
}

.section header p {
	margin: 2px 0 0;
	font-size: 13px;
}

.grid {
	display: grid;
	grid-template-columns: 2fr 1fr;
	gap: 14px;
}

.field .input,
.field .select {
	max-width: 420px;
}

.hint {
	font-size: 12px;
	color: var(--text-faint);
}

.choices {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	gap: 10px;
}

.choice {
	display: grid;
	grid-template-columns: auto 1fr;
	column-gap: 10px;
	row-gap: 2px;
	padding: 12px 14px;
	border: 1px solid var(--border-strong);
	border-radius: var(--radius-sm);
	cursor: pointer;
}

.choice input {
	grid-row: span 2;
	margin-top: 3px;
	accent-color: var(--brand);
}

.choice span {
	font-size: 13px;
}

.choice.chosen {
	border-color: var(--brand);
	background: var(--mint-soft);
}

.toggle {
	display: flex;
	gap: 12px;
	cursor: pointer;
}

.toggle input {
	margin-top: 3px;
	width: 16px;
	height: 16px;
	accent-color: var(--brand);
}

.toggle span {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.toggle .muted {
	font-size: 13px;
}

.readonly {
	background: var(--surface-muted);
}

.notice {
	margin: 0 0 16px;
	padding: 12px 14px;
	border-radius: var(--radius-sm);
	background: var(--amber-bg);
	color: var(--amber-fg);
}

/* Slides up from the bottom while there is something to save. */
.save-bar {
	position: sticky;
	bottom: 16px;
	display: flex;
	align-items: center;
	gap: 10px;
	margin-top: 16px;
	padding: 12px 16px;
	border-radius: var(--radius);
	background: var(--ink);
	color: #fff;
	box-shadow: var(--shadow-lift);
	opacity: 0;
	transform: translateY(12px);
	pointer-events: none;
	transition:
		opacity 0.18s ease,
		transform 0.18s ease;
}

.save-bar.shown {
	opacity: 1;
	transform: none;
	pointer-events: auto;
}

.save-bar span {
	margin-right: auto;
}

.save-bar .btn-ghost {
	color: #fff;
}

@media (max-width: 640px) {
	.grid {
		grid-template-columns: 1fr;
	}
}
</style>
