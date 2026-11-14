/* Teacher / learner pages: browse resources, request a resource, my requests, equipment bookings (Task 3A). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;

	/* Browse resources: GET /api/resources?q=&category= */
	const resourceBody = $("#resource-list tbody");
	if (resourceBody) {
		const search = $("#resource-search");
		const category = $("#category-filter");
		const ICONS = { Textbooks: "▤", Stationery: "✎", Equipment: "⌁" };
		const reload = ui.createTable({
			tbody: resourceBody,
			columns: 4,
			emptyText: "No resources match your search. Try another keyword or category.",
			load: async () => (await api.get("/api/resources", { q: search.value, category: category.value })).items,
			renderRow: (item) => `<tr><td><div class="catalogue-item"><span class="catalogue-item__icon" aria-hidden="true">${ICONS[item.category] || "▤"}</span><span><span class="catalogue-item__name">${esc(item.name)}</span><span class="catalogue-item__description">${esc(item.description)}</span></span></div></td><td><span class="badge catalogue-category">${esc(item.category)}</span></td><td>${ui.badge(item.availability, item.tone)}</td><td><span class="catalogue-count">${esc(item.stock)}</span><span class="sr-only"> ${esc(item.unit)} available</span></td></tr>`
		});
		search.addEventListener("input", ui.debounce(reload));
		category.addEventListener("change", reload);
		reload();
	}

	/* Request a resource: GET /api/resources (suggestions) and POST /api/requests */
	const requestForm = $("#request-form");
	if (requestForm) {
		const suggestions = $("#catalogue-items");
		if (suggestions) {
			api.get("/api/resources")
				.then(({ items }) => { suggestions.innerHTML = items.map((item) => `<option value="${esc(item.name)}">`).join(""); })
				.catch(() => { /* keep the built-in suggestions */ });
		}
		ui.bindForm(requestForm, {
			feedbackId: "request-feedback",
			endpoint: "/api/requests",
			busyText: "Submitting…",
			payload: (v) => ({ resource_name: v.resource_name.trim(), category: v.category, quantity: Number(v.quantity), needed_by: v.needed_by, purpose: v.purpose.trim() }),
			success: () => "Request submitted. The LTSM committee will review it – track its progress on My requests."
		});
	}

	/* My requests: GET /api/requests?status= */
	const requestsBody = $("#requests-table tbody");
	if (requestsBody) {
		const status = $("#request-status");
		const reload = ui.createTable({
			tbody: requestsBody,
			columns: 6,
			emptyText: () => (status.value ? "No requests have this status." : "You have not submitted any requests yet."),
			load: async () => (await api.get("/api/requests", { status: status.value })).items,
			renderRow: (r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.category)}</td><td>${ui.formatDate(r.submitted)}</td><td>${esc(r.quantity)}</td><td>${ui.badge(r.status, r.tone)}</td><td>${esc(r.update)}</td></tr>`
		});
		status.addEventListener("change", reload);
		reload();
	}

	/* Equipment bookings: GET /api/equipment, GET /api/bookings, POST /api/bookings */
	const bookingForm = $("#booking-form");
	if (bookingForm) {
		const equipmentSelect = $("#equipment");
		const feedback = $("#booking-feedback");

		async function loadEquipment() {
			try {
				const { items } = await api.get("/api/equipment");
				ui.fillSelect(equipmentSelect, items, (item) => ({ value: item.id, label: `${item.name} (${item.stock} in stock)` }));
			} catch (error) {
				ui.showFeedback(feedback, "error", `Could not load equipment. ${error.message}`);
			}
		}
		const reloadBookings = ui.createTable({
			tbody: $("#bookings-table tbody"),
			columns: 3,
			emptyText: "You have no upcoming bookings.",
			load: async () => (await api.get("/api/bookings")).items,
			renderRow: (b) => `<tr><td>${esc(b.equipment)}<br><small>${esc(b.room)}</small></td><td>${ui.formatDate(b.date, false)}<br><small>${esc(b.start)}–${esc(b.end)}</small></td><td>${ui.badge(b.status, b.tone)}</td></tr>`
		});

		loadEquipment();
		reloadBookings();
		ui.bindForm(bookingForm, {
			feedbackId: "booking-feedback",
			endpoint: "/api/bookings",
			busyText: "Requesting…",
			payload: (v) => ({ equipment_id: Number(v.equipment), booking_date: v.booking_date, start_time: v.start_time, end_time: v.end_time, room: v.room.trim(), purpose: v.purpose.trim() }),
			success: (data) => data.message,
			onSuccess: reloadBookings
		});
	}
})();
