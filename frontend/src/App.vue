<script setup>
import AppIcon from "./components/AppIcon.vue";
import ToastHost from "./components/ToastHost.vue";
import { initials } from "./lib/format.js";
import { boot } from "./lib/server.js";

const DESK_URL = "/desk/field-service?desk=1";

const NAV = [
	{ to: "/", label: "Dashboard", icon: "home", exact: true },
	{ to: "/board", label: "Job board", icon: "board" },
	{ to: "/jobs", label: "Jobs", icon: "list" },
	{ to: "/team", label: "Technicians", icon: "team" },
];
</script>

<template>
	<div class="shell">
		<aside class="sidebar">
			<RouterLink to="/" class="brand">
				<span class="logo"><AppIcon name="wrench" :size="18" /></span>
				<span>
					<strong>Field Service</strong>
					<small>{{ boot.company || "fieldpro" }}</small>
				</span>
			</RouterLink>

			<RouterLink to="/jobs/new" class="btn btn-primary new-job">
				<AppIcon name="plus" :size="16" /> New job
			</RouterLink>

			<nav>
				<RouterLink
					v-for="item in NAV"
					:key="item.to"
					:to="item.to"
					class="nav-item"
					:exact-active-class="item.exact ? 'active' : ''"
					:active-class="item.exact ? '' : 'active'"
				>
					<AppIcon :name="item.icon" />
					<span>{{ item.label }}</span>
				</RouterLink>
			</nav>

			<div class="foot">
				<!-- ?desk=1 keeps this manager in Desk until they open /manage again (manager_landing.py). -->
				<a :href="DESK_URL" class="nav-item subtle" title="Use ERPNext Desk until you come back here">
					<AppIcon name="external" />
					<span>Switch to Desk</span>
				</a>
				<div class="me">
					<span class="avatar">{{ initials(boot.full_name) }}</span>
					<span class="who">
						<strong>{{ boot.full_name }}</strong>
						<small>{{ boot.user }}</small>
					</span>
				</div>
			</div>
		</aside>

		<main class="main">
			<RouterView />
		</main>
		<ToastHost />
	</div>
</template>

<style scoped>
.shell {
	display: grid;
	grid-template-columns: 240px 1fr;
	min-height: 100vh;
	/* The sidebar's colour runs the full height, however long the page scrolls. */
	background: linear-gradient(to right, var(--ink) 240px, transparent 240px);
}

.sidebar {
	position: sticky;
	top: 0;
	height: 100vh;
	display: flex;
	flex-direction: column;
	gap: 18px;
	padding: 18px 14px;
	background: var(--ink);
	color: #d5e6e0;
}

.brand {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 4px 6px;
	color: #fff;
}

.brand:hover {
	text-decoration: none;
}

.brand strong {
	display: block;
	font-size: 15px;
}

.brand small {
	display: block;
	font-size: 12px;
	color: var(--mint);
}

.logo {
	display: grid;
	place-items: center;
	width: 34px;
	height: 34px;
	border-radius: 9px;
	background: var(--brand);
	color: #fff;
}

.new-job {
	justify-content: center;
	height: 36px;
}

.new-job:hover {
	text-decoration: none;
}

nav {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.nav-item {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--radius-sm);
	color: #c4d8d1;
	font-weight: 500;
}

.nav-item:hover {
	background: var(--ink-soft);
	color: #fff;
	text-decoration: none;
}

.nav-item.active {
	background: var(--ink-soft);
	color: #fff;
	box-shadow: inset 3px 0 0 var(--mint);
}

.nav-item.subtle {
	font-size: 13px;
	color: #9fb8b0;
}

.foot {
	margin-top: auto;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.me {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 6px 0;
	border-top: 1px solid var(--ink-soft);
}

.avatar {
	display: grid;
	place-items: center;
	flex: none;
	width: 32px;
	height: 32px;
	border-radius: 50%;
	background: var(--mint);
	color: var(--ink);
	font-weight: 700;
	font-size: 12px;
}

.who {
	min-width: 0;
}

.who strong,
.who small {
	display: block;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.who strong {
	color: #fff;
	font-size: 13px;
}

.who small {
	font-size: 12px;
	color: #9fb8b0;
}

.main {
	min-width: 0;
}

@media (max-width: 860px) {
	.shell {
		grid-template-columns: 1fr;
		background: none;
	}

	.sidebar {
		position: static;
		height: auto;
		flex-direction: row;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
		padding: 12px 16px;
	}

	nav {
		flex-direction: row;
		flex-wrap: wrap;
		order: 3;
		width: 100%;
	}

	.new-job {
		margin-left: auto;
	}

	.foot {
		display: none;
	}
}
</style>
