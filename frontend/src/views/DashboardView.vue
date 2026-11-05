<script setup>
// Today's numbers (the same Number Cards as the Desk workspace) and the jobs waiting on a manager,
// each with the one action it needs.
import { ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import AssignDialog from "../components/AssignDialog.vue";
import { dayLabel } from "../lib/format.js";
import { api, boot } from "../lib/server.js";
import { notify } from "../lib/toast.js";
import { useRequest } from "../lib/useRequest.js";

// Card label (from the server) to its look and the list it opens.
const CARD_LOOK = {
	"Jobs Booked Today": { icon: "plus", tone: "blue", to: "/jobs" },
	"Waiting for a Technician": { icon: "user", tone: "orange", to: "/jobs?status=Booked" },
	"Jobs In Progress": { icon: "wrench", tone: "amber", to: "/jobs?status=In%20Progress" },
	"Waiting for Approval": { icon: "clock", tone: "violet", to: "/jobs?status=Pending%20Approval" },
	"Done This Week": { icon: "check", tone: "green", to: "/jobs?status=Done" },
	"Done but Not Invoiced": { icon: "file", tone: "red", to: "/jobs?status=Done" },
};

const LISTS = [
	{ key: "unassigned", title: "Needs a technician", empty: "Every job has a technician.", action: "Assign" },
	{ key: "waiting_approval", title: "Waiting for your approval", empty: "Nothing to approve.", action: "Approve" },
	{ key: "overdue", title: "Overdue", empty: "No job is late.", action: null },
	{ key: "rework", title: "Sent back by customers", empty: "No rework.", action: null },
];

const { data, error, loading, reload } = useRequest(async () => (await api.get("manage.overview")).data, {
	refreshSeconds: 60,
});
const assigning = ref(null);
const busy = ref("");

const greeting = (() => {
	const hour = new Date().getHours();
	const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
	return `${part}, ${(boot.full_name || "").split(" ")[0]}`;
})();

async function approve(job) {
	busy.value = job.id;
	try {
		await api.post("manage.act", { job: job.id, action: "Approve" });
		notify(`${job.id} approved`);
		await reload();
	} catch (exc) {
		notify(exc.message, "error");
	} finally {
		busy.value = "";
	}
}

function onAssigned(job) {
	assigning.value = null;
	notify(`${job.id} assigned to ${job.technician.name}`);
	reload();
}
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<h1>{{ greeting }}</h1>
				<p>{{ new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }) }} · here is the field today.</p>
			</div>
			<button class="btn" :disabled="loading" @click="reload">
				<AppIcon name="refresh" :size="16" /> Refresh
			</button>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>

		<section class="stats">
			<template v-if="data">
				<RouterLink
					v-for="card in data.cards"
					:key="card.label"
					:to="CARD_LOOK[card.label]?.to || '/jobs'"
					class="stat card"
				>
					<span
						class="stat-icon"
						:style="{
							color: `var(--${CARD_LOOK[card.label]?.tone || 'gray'}-fg)`,
							background: `var(--${CARD_LOOK[card.label]?.tone || 'gray'}-bg)`,
						}"
					>
						<AppIcon :name="CARD_LOOK[card.label]?.icon || 'list'" :size="18" />
					</span>
					<span class="stat-value">{{ card.value }}</span>
					<span class="stat-label">{{ card.label }}</span>
				</RouterLink>
			</template>
			<template v-else>
				<div v-for="n in 6" :key="n" class="stat card skeleton" />
			</template>
		</section>

		<section v-if="data" class="lists">
			<div v-for="list in LISTS" :key="list.key" class="list card">
				<header>
					<h2>{{ list.title }}</h2>
					<span class="count">{{ data.attention[list.key].length }}</span>
				</header>
				<p v-if="!data.attention[list.key].length" class="empty">
					<AppIcon name="check" :size="16" /> {{ list.empty }}
				</p>
				<ul v-else>
					<li v-for="job in data.attention[list.key]" :key="job.id">
						<RouterLink :to="`/jobs/${job.id}`" class="row-main">
							<span class="row-issue">{{ job.issue }}</span>
							<span class="row-sub">
								{{ job.customer.name }} · {{ dayLabel(job.scheduled_date) }}
								<template v-if="job.technician"> · {{ job.technician.name }}</template>
							</span>
						</RouterLink>
						<button
							v-if="list.action === 'Assign'"
							class="btn btn-sm"
							@click="assigning = job"
						>
							Assign
						</button>
						<button
							v-else-if="list.action === 'Approve'"
							class="btn btn-sm"
							:disabled="busy === job.id"
							@click="approve(job)"
						>
							Approve
						</button>
					</li>
				</ul>
			</div>
		</section>

		<AssignDialog v-if="assigning" :job="assigning" @close="assigning = null" @assigned="onAssigned" />
	</div>
</template>

<style scoped>
.stats {
	display: grid;
	grid-template-columns: repeat(6, minmax(0, 1fr));
	gap: 14px;
	margin-bottom: 24px;
}

.stat {
	display: flex;
	flex-direction: column;
	gap: 4px;
	padding: 16px;
	color: var(--text);
	min-height: 118px;
	transition: box-shadow 0.15s, transform 0.15s;
}

.stat:hover {
	text-decoration: none;
	box-shadow: var(--shadow-lift);
	transform: translateY(-1px);
}

.stat-icon {
	display: grid;
	place-items: center;
	width: 32px;
	height: 32px;
	border-radius: 8px;
	margin-bottom: 6px;
}

.stat-value {
	font-size: 28px;
	font-weight: 700;
	letter-spacing: -0.02em;
	line-height: 1.1;
}

.stat-label {
	color: var(--text-muted);
	font-size: 13px;
}

.skeleton {
	background: linear-gradient(90deg, var(--surface) 0%, var(--surface-muted) 50%, var(--surface) 100%);
}

.lists {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
	gap: 16px;
}

.list header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 14px 16px;
	border-bottom: 1px solid var(--border);
}

.list h2 {
	font-size: 15px;
	font-weight: 600;
}

.count {
	min-width: 24px;
	padding: 1px 8px;
	border-radius: 999px;
	background: var(--surface-muted);
	border: 1px solid var(--border);
	text-align: center;
	font-size: 12px;
	font-weight: 600;
	color: var(--text-muted);
}

.empty {
	display: flex;
	align-items: center;
	gap: 8px;
	margin: 0;
	padding: 18px 16px;
	color: var(--green-fg);
}

ul {
	list-style: none;
	margin: 0;
	padding: 0;
}

li {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 10px 16px;
	border-bottom: 1px solid var(--border);
}

li:last-child {
	border-bottom: 0;
}

.row-main {
	display: flex;
	flex-direction: column;
	flex: 1;
	min-width: 0;
	color: var(--text);
}

.row-main:hover {
	text-decoration: none;
}

.row-main:hover .row-issue {
	color: var(--brand);
}

.row-issue {
	font-weight: 550;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.row-sub {
	font-size: 12px;
	color: var(--text-muted);
}

@media (max-width: 1200px) {
	.stats {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
}

@media (max-width: 760px) {
	.stats {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.lists {
		grid-template-columns: 1fr;
	}
}
</style>
