<script setup>
// Each active technician's load: open jobs, today's, late ones, and the last seven days' work
// (the same numbers as the Technician Performance report).
import AppIcon from "../components/AppIcon.vue";
import { initials } from "../lib/format.js";
import { api } from "../lib/server.js";
import { useRequest } from "../lib/useRequest.js";

const { data, error, loading, reload } = useRequest(async () => (await api.get("manage.technicians")).data, {
	refreshSeconds: 120,
});
</script>

<template>
	<div class="page">
		<div class="page-head">
			<div>
				<h1>Technicians</h1>
				<p>Who has what, so new work goes to the right person.</p>
			</div>
			<button class="btn" :disabled="loading" @click="reload">
				<AppIcon name="refresh" :size="16" /> Refresh
			</button>
		</div>

		<div v-if="error" class="error-banner">{{ error.message }}</div>
		<p v-else-if="data && !data.length" class="muted">No active technicians. Add one in Desk under Technician.</p>

		<div class="team">
			<article v-for="tech in data || []" :key="tech.id" class="card person">
				<header>
					<span class="avatar">{{ initials(tech.name) }}</span>
					<div>
						<h2>{{ tech.name }}</h2>
						<a v-if="tech.mobile_no" :href="`tel:${tech.mobile_no}`" class="contact">
							<AppIcon name="phone" :size="13" /> {{ tech.mobile_no }}
						</a>
					</div>
					<span v-if="tech.in_progress" class="on-site">On a job</span>
				</header>

				<div class="numbers">
					<div>
						<strong>{{ tech.open_jobs }}</strong>
						<span>Open</span>
					</div>
					<div>
						<strong>{{ tech.today }}</strong>
						<span>Today</span>
					</div>
					<div :class="{ late: tech.overdue }">
						<strong>{{ tech.overdue }}</strong>
						<span>Late</span>
					</div>
				</div>

				<div class="week">
					<span class="faint">Last 7 days</span>
					<span>{{ tech.week.jobs_done }} done · {{ tech.week.visits }} visits · {{ tech.week.hours }} h</span>
				</div>

				<RouterLink :to="{ path: '/jobs', query: { technician: tech.id } }" class="btn btn-sm see-jobs">
					See jobs
				</RouterLink>
			</article>
		</div>
	</div>
</template>

<style scoped>
.team {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 16px;
}

.person {
	display: flex;
	flex-direction: column;
	gap: 14px;
	padding: 18px;
}

header {
	display: flex;
	align-items: center;
	gap: 12px;
}

h2 {
	font-size: 16px;
	font-weight: 600;
}

.avatar {
	display: grid;
	place-items: center;
	flex: none;
	width: 44px;
	height: 44px;
	border-radius: 50%;
	background: var(--brand);
	color: #fff;
	font-weight: 700;
}

.contact {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 13px;
	color: var(--text-muted);
}

.on-site {
	margin-left: auto;
	padding: 2px 8px;
	border-radius: 999px;
	background: var(--amber-bg);
	color: var(--amber-fg);
	font-size: 12px;
	font-weight: 600;
	white-space: nowrap;
}

.numbers {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 8px;
}

.numbers div {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 10px 4px;
	border-radius: var(--radius-sm);
	background: var(--surface-muted);
	border: 1px solid var(--border);
}

.numbers strong {
	font-size: 22px;
	line-height: 1.1;
}

.numbers span {
	font-size: 12px;
	color: var(--text-muted);
}

.numbers .late {
	background: var(--red-bg);
	border-color: transparent;
	color: var(--red-fg);
}

.numbers .late span {
	color: var(--red-fg);
}

.week {
	display: flex;
	justify-content: space-between;
	gap: 8px;
	font-size: 13px;
}

.see-jobs {
	align-self: flex-start;
}

.see-jobs:hover {
	text-decoration: none;
}
</style>
