/* Keep notification badges current and support paged, actionable history. */
(function () {
	"use strict";

	const api = window.LTSM && window.LTSM.api;
	if (!api) return;

	const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
		"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
	}[character]));
	const module = document.body.dataset.notificationModule;
	const historyList = document.querySelector("[data-notification-items]");
	const historyStatus = document.querySelector("[data-notification-status]");
	const moreButton = document.querySelector("[data-notification-more]");
	const badgeLabels = {
		"request-management": "Request management",
		"my-requests": "My requests",
		bookings: "Equipment bookings"
	};
	let historyItems = [];
	let beforeId = null;
	let hasMore = false;
	let loadingMore = false;

	function renderBadges(unread) {
		for (const badge of document.querySelectorAll("[data-notification-badge]")) {
			const key = badge.dataset.notificationBadge;
			const count = Number(unread[key] || 0);
			badge.hidden = count === 0;
			badge.textContent = count > 9 ? "9+" : String(count);
			const link = badge.closest("a");
			if (link) {
				const label = badgeLabels[key] || "module";
				link.setAttribute("aria-label", count ? `${label}, ${count} unread notification${count === 1 ? "" : "s"}` : label);
			}
		}
	}

	function renderHistory() {
		if (!historyList) return;
		if (!historyItems.length) {
			historyList.innerHTML = "<li>No notifications yet.</li>";
		} else {
			historyList.innerHTML = historyItems.map((item) => {
				const target = typeof item.target_url === "string" && item.target_url.startsWith("/")
					&& !item.target_url.startsWith("//") ? item.target_url : "#";
				const done = item.done === true || Number(item.done) === 1;
				const state = ["notification-item"];
				if (!Number(item.unread)) state.push("notification-item--read");
				if (done) state.push("notification-item--done");
				const action = done
					? '<span class="notification-done-status">Done</span>'
					: `<button class="button button-secondary button-small notification-done-button" type="button" data-notification-done="${escape(item.id)}" aria-label="Mark ${escape(item.title)} as done">Mark done</button>`;
				return `<li class="${state.join(" ")}"><a href="${escape(target)}"><strong>${escape(item.title)}</strong><p>${escape(item.message)}</p><time>${escape(item.created_at)}</time></a><div class="notification-item__actions">${action}</div></li>`;
			}).join("");
		}
		if (moreButton) {
			moreButton.hidden = !hasMore;
			moreButton.disabled = loadingMore;
			moreButton.textContent = loadingMore ? "Loading…" : "Load more";
		}
	}

	async function refresh() {
		const result = await api.get("/api/notifications", module ? { module } : undefined);
		renderBadges(result.unread || {});
		if (historyList && module) {
			const latest = result.items || [];
			if (!historyItems.length) {
				historyItems = latest;
				beforeId = result.next_before_id;
				hasMore = Boolean(result.has_more);
			} else {
				const known = new Map(historyItems.map((item) => [String(item.id), item]));
				const latestIds = new Set(latest.map((item) => String(item.id)));
				historyItems = [
					...latest.map((item) => ({ ...known.get(String(item.id)), ...item })),
					...historyItems.filter((item) => !latestIds.has(String(item.id)))
				];
			}
			renderHistory();
		}
	}

	async function loadMore() {
		if (!module || !hasMore || loadingMore) return;
		loadingMore = true;
		renderHistory();
		if (historyStatus) historyStatus.textContent = "";
		try {
			const result = await api.get("/api/notifications", {
				module,
				before_id: beforeId
			});
			const loadedIds = new Set(historyItems.map((item) => String(item.id)));
			historyItems.push(...(result.items || []).filter(
				(item) => !loadedIds.has(String(item.id))
			));
			beforeId = result.next_before_id;
			hasMore = Boolean(result.has_more);
			if (historyStatus) historyStatus.textContent = "More notifications loaded.";
		} catch (error) {
			if (historyStatus) historyStatus.textContent = `Could not load more notifications. ${error.message}`;
			console.error("Could not load more notifications.", error);
		} finally {
			loadingMore = false;
			renderHistory();
		}
	}

	async function markDone(notificationId, button) {
		button.disabled = true;
		if (historyStatus) historyStatus.textContent = "";
		try {
			await api.post(`/api/notifications/${encodeURIComponent(notificationId)}/done`, {});
			const item = historyItems.find((notification) => String(notification.id) === String(notificationId));
			if (item) {
				item.done = true;
				item.unread = false;
			}
			renderHistory();
			if (historyStatus) historyStatus.textContent = "Notification marked as done.";
			try {
				const result = await api.get("/api/notifications");
				renderBadges(result.unread || {});
			} catch (error) {
				console.error("Could not refresh notification badges.", error);
			}
		} catch (error) {
			if (historyStatus) historyStatus.textContent = `Could not mark notification as done. ${error.message}`;
			console.error("Could not mark notification as done.", error);
			renderHistory();
		}
	}

	async function initialize() {
		if (module) {
			try {
				await api.post("/api/notifications/read", { module });
			} catch (error) {
				if (historyStatus) historyStatus.textContent = `Could not mark notifications as read. ${error.message}`;
				console.error("Could not mark module notifications as read.", error);
			}
		}
		try {
			await refresh();
		} catch (error) {
			if (historyList) historyList.innerHTML = `<li>Could not load notifications. ${escape(error.message)}</li>`;
			if (historyStatus) historyStatus.textContent = "Refresh the page to try again.";
			console.error("Could not load notifications.", error);
		}
	}

	if (moreButton) moreButton.addEventListener("click", loadMore);
	if (historyList) {
		historyList.addEventListener("click", (event) => {
			const button = event.target.closest("[data-notification-done]");
			if (button) markDone(button.dataset.notificationDone, button);
		});
	}

	initialize();
	window.setInterval(async () => {
		try {
			await refresh();
		} catch (error) {
			console.error("Could not refresh notifications.", error);
		}
	}, 15000);
})();
