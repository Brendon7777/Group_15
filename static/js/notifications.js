/* Keep module notification badges current and render each module's history. */
(function () {
	"use strict";

	const api = window.LTSM && window.LTSM.api;
	if (!api) return;

	const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
		"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
	}[character]));
	const module = document.body.dataset.notificationModule;
	const historyList = document.querySelector("[data-notification-items]");
	const badgeLabels = {
		"request-management": "Request management",
		"my-requests": "My requests",
		bookings: "Equipment bookings"
	};

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

	function renderHistory(items) {
		if (!historyList) return;
		if (!items.length) {
			historyList.innerHTML = "<li>No notifications yet.</li>";
			return;
		}
		historyList.innerHTML = items.map((item) => {
			const target = typeof item.target_url === "string" && item.target_url.startsWith("/")
				&& !item.target_url.startsWith("//") ? item.target_url : "#";
			const state = Number(item.unread) ? "notification-item" : "notification-item notification-item--read";
			return `<li class="${state}"><a href="${escape(target)}"><strong>${escape(item.title)}</strong><p>${escape(item.message)}</p><time>${escape(item.created_at)}</time></a></li>`;
		}).join("");
	}

	async function refresh() {
		const result = await api.get("/api/notifications", module ? { module } : undefined);
		renderBadges(result.unread || {});
		if (historyList) renderHistory(result.items || []);
	}

	async function initialize() {
		if (module) {
			try {
				await api.post("/api/notifications/read", { module });
			} catch (error) {
				if (historyList) historyList.textContent = `Could not mark notifications as read. ${error.message}`;
				console.error("Could not mark module notifications as read.", error);
			}
		}
		try {
			await refresh();
		} catch (error) {
			if (historyList) historyList.textContent = `Could not load notifications. ${error.message}`;
			console.error("Could not load notifications.", error);
		}
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
