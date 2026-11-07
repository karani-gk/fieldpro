<script setup>
// The customers a manager books for: how to reach them, their open jobs and, for managers who may
// read invoices, what they owe. Each row books a job, or opens their jobs or invoices.
import { ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { openNewJob } from "../lib/dialogs.js";
import { money } from "../lib/format.js";
import { api } from "../lib/server.js";
import { useRequest } from "../lib/useRequest.js";

const search = ref("");
const { data, error, loading, reload } = useRequest(
	async () => (await api.get("manage.customer_directory", { q: search.value })).data,
);

// Typing waits for a pause before asking the server.
let timer = null;
watch(search, () => {
	clearTimeout(timer);
	timer = setTimeout(reload, 250);
});

// `owed` is null for managers without an accounts role: the column is left out for them.
const showOwed = (rows) => (rows || []).some((c) => c.owed !== null);
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<h1>Customers</h1>
				<p>Who you work for, their open jobs and what they owe.</p>
			</div>
			<a href="/app/customer/new" class="btn" title="Customers are added in Desk">
				<AppIcon name="external" :size="16" /> Add in Desk
			</a>
		</div>

		<div class="card toolbar">
			<label class="search-box">
				<AppIcon name="search" :size="16" />
				<input v-model="search" class="input" placeholder="Search customers" />
			</label>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>

		<div v-else class="card data-table-wrap">
			<table class="data-table">
				<thead>
					<tr>
						<th>Customer</th>
						<th>Contact</th>
						<th class="num">Open jobs</th>
						<th v-if="showOwed(data)" class="num">Owed</th>
						<th><span class="sr-only">Actions</span></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="customer in data || []" :key="customer.id">
						<td>
							<strong>{{ customer.name }}</strong>
							<div v-if="customer.id !== customer.name" class="faint small">{{ customer.id }}</div>
						</td>
						<td>
							<div class="contact">
								<a v-if="customer.mobile_no" :href="`tel:${customer.mobile_no}`">
								<AppIcon name="phone" :size="13" /> {{ customer.mobile_no }}
							</a>
							<a v-if="customer.email" :href="`mailto:${customer.email}`" class="faint">{{ customer.email }}</a>
							<span v-if="!customer.mobile_no && !customer.email" class="faint">None saved</span>
							</div>
						</td>
						<td class="num">
							<RouterLink
								v-if="customer.open_jobs"
								:to="{ path: '/jobs', query: { customer: customer.id } }"
								class="count"
							>
								{{ customer.open_jobs }}
							</RouterLink>
							<span v-else class="faint">0</span>
						</td>
						<td v-if="showOwed(data)" class="num">
							<RouterLink
								v-if="Number(customer.owed?.amount)"
								:to="{ path: '/invoices', query: { status: 'Unpaid', customer: customer.id } }"
								class="owed"
							>
								{{ money(customer.owed) }}
							</RouterLink>
							<span v-else class="faint">0</span>
						</td>
						<td>
							<div class="row-actions">
								<button class="btn btn-primary btn-sm" @click="openNewJob(customer)">
									<AppIcon name="plus" :size="14" /> Job
								</button>
								<RouterLink :to="{ path: '/jobs', query: { customer: customer.id } }" class="btn btn-sm">
									Jobs
								</RouterLink>
							</div>
						</td>
					</tr>
					<tr v-if="data && !data.length && !loading" class="empty-row">
						<td :colspan="showOwed(data) ? 5 : 4">No customers match “{{ search }}”.</td>
					</tr>
				</tbody>
			</table>
		</div>
		<p v-if="data?.length === 50" class="faint more">Showing the first 50. Search to find others.</p>
	</div>
</template>

<style scoped>
.small {
	font-size: 12px;
}

.contact {
	display: flex;
	flex-direction: column;
	gap: 2px;
	font-size: 13px;
}

.contact a {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.count {
	font-weight: 600;
}

.owed {
	color: var(--red-fg);
	font-weight: 600;
}

.btn:hover {
	text-decoration: none;
}

.more {
	margin-top: 12px;
	text-align: center;
}
</style>
