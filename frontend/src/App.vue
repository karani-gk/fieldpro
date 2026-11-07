<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "./components/AppIcon.vue";
import NewJobDialog from "./components/NewJobDialog.vue";
import ToastHost from "./components/ToastHost.vue";
import { dialogs, openNewJob } from "./lib/dialogs.js";
import { initials } from "./lib/format.js";
import { api, boot } from "./lib/server.js";
import { notify } from "./lib/toast.js";

const router = useRouter();
const menuOpen = ref(false);
const menu = ref(null);
const signingOut = ref(false);

// The account menu closes on a click anywhere else, or Escape.
function onDocumentClick(event) {
	if (menu.value && !menu.value.contains(event.target)) menuOpen.value = false;
}
function onKey(event) {
	if (event.key === "Escape") menuOpen.value = false;
}
onMounted(() => {
	document.addEventListener("click", onDocumentClick);
	document.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
	document.removeEventListener("click", onDocumentClick);
	document.removeEventListener("keydown", onKey);
});

async function signOut() {
	signingOut.value = true;
	try {
		await api.signOut();
		window.location.href = "/login";
	} catch (exc) {
		signingOut.value = false;
		notify(exc.message, "error");
	}
}

function onBooked(job) {
	dialogs.newJob = false;
	router.push(`/jobs/${job.id}`);
}

// The Desk home, not the Field Service workspace: for field managers that workspace opens the
// manager app (public/js/manager_app.js), so landing there would bounce straight back.
const DESK_URL = "/desk?desk=1";

const NAV = [
	{ to: "/", label: "Dashboard", icon: "home", exact: true },
	{ to: "/board", label: "Job board", icon: "board" },
	{ to: "/jobs", label: "Jobs", icon: "list" },
	{ to: "/team", label: "Technicians", icon: "team" },
	{ to: "/customers", label: "Customers", icon: "building" },
	{ to: "/invoices", label: "Invoices", icon: "receipt" },
	{ to: "/settings", label: "Settings", icon: "settings" },
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

			<button class="btn btn-primary new-job" @click="openNewJob">
				<AppIcon name="plus" :size="16" /> New job
			</button>

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

			<div ref="menu" class="foot">
				<Transition name="pop">
					<div v-if="menuOpen" class="account-menu" role="menu">
						<div class="menu-who">
							<strong>{{ boot.full_name }}</strong>
							<small>{{ boot.user }}</small>
						</div>
						<!-- ?desk=1 keeps this manager in Desk until they open /manage again (manager_landing.py). -->
						<a :href="DESK_URL" class="menu-item" role="menuitem">
							<AppIcon name="external" :size="16" /> Switch to Desk
						</a>
						<button class="menu-item danger" role="menuitem" :disabled="signingOut" @click="signOut">
							<AppIcon name="logout" :size="16" /> {{ signingOut ? "Signing out…" : "Sign out" }}
						</button>
					</div>
				</Transition>
				<button
					class="me"
					:aria-expanded="menuOpen"
					aria-haspopup="menu"
					title="Your account"
					@click="menuOpen = !menuOpen"
				>
					<span class="avatar">{{ initials(boot.full_name) }}</span>
					<span class="who">
						<strong>{{ boot.full_name }}</strong>
						<small>{{ boot.user }}</small>
					</span>
					<AppIcon name="chevron" :size="16" class="chevron" />
				</button>
			</div>
		</aside>

		<main class="main">
			<RouterView />
		</main>
		<NewJobDialog v-if="dialogs.newJob" @close="dialogs.newJob = false" @booked="onBooked" />
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

.foot {
	position: relative;
	margin-top: auto;
	padding-top: 10px;
	border-top: 1px solid var(--ink-soft);
}

.me {
	display: flex;
	align-items: center;
	gap: 10px;
	width: 100%;
	padding: 8px 6px;
	border: 0;
	border-radius: var(--radius-sm);
	background: none;
	color: inherit;
	font: inherit;
	text-align: left;
	cursor: pointer;
}

.me:hover,
.me[aria-expanded="true"] {
	background: var(--ink-soft);
}

.chevron {
	margin-left: auto;
	flex: none;
	color: #9fb8b0;
	transform: rotate(-90deg);
}

.account-menu {
	position: absolute;
	left: 0;
	right: 0;
	bottom: calc(100% + 6px);
	z-index: 40;
	padding: 6px;
	border: 1px solid var(--border);
	border-radius: var(--radius);
	background: var(--surface);
	color: var(--text);
	box-shadow: var(--shadow-lift);
}

.menu-who {
	padding: 8px 10px 10px;
	margin-bottom: 4px;
	border-bottom: 1px solid var(--border);
}

.menu-who strong,
.menu-who small {
	display: block;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.menu-who small {
	color: var(--text-muted);
}

.menu-item {
	display: flex;
	align-items: center;
	gap: 10px;
	width: 100%;
	padding: 8px 10px;
	border: 0;
	border-radius: var(--radius-sm);
	background: none;
	color: var(--text);
	font: inherit;
	font-weight: 500;
	text-align: left;
	cursor: pointer;
}

.menu-item:hover {
	background: var(--surface-muted);
	text-decoration: none;
}

.menu-item.danger {
	color: var(--danger);
}

.menu-item.danger:hover {
	background: var(--danger-soft);
}

.pop-enter-active,
.pop-leave-active {
	transition:
		opacity 0.16s ease,
		transform 0.16s ease;
}

.pop-enter-from,
.pop-leave-to {
	opacity: 0;
	transform: translateY(6px);
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

	/* On a phone the account menu is the avatar in the top bar, opening downwards. */
	.foot {
		margin: 0;
		padding: 0;
		border: 0;
	}

	.me {
		padding: 2px;
		border-radius: 50%;
	}

	.who,
	.chevron {
		display: none;
	}

	.account-menu {
		left: auto;
		right: 0;
		top: calc(100% + 6px);
		bottom: auto;
		width: 240px;
	}
}
</style>
