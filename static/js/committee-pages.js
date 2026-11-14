/* LTSM committee pages: manage inventory, issue / return, maintenance (Task 3A). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;

	/* Manage inventory: GET /api/inventory?q=&category= and POST /api/inventory */
	const inventoryBody = $("#inventory-table tbody");
	if (inventoryBody) {
		const search = $("#inventory-search");
		const category = $("[data-category-filter]");
		const reload = ui.createTable({
			tbody: inventoryBody,
			columns: 5,
			emptyText: "No inventory items match your filters.",
			load: async () => (await api.get("/api/inventory", { q: search.value, category: category.value })).items,
			renderRow: (i) => `<tr><td>${esc(i.name)}</td><td>${esc(i.category)}</td><td>${esc(i.stock)}</td><td>${esc(i.reorder_level)}</td><td>${ui.badge(i.status, i.tone)}</td></tr>`
		});
		search.addEventListener("input", ui.debounce(reload));
		category.addEventListener("change", reload);
		reload();

		ui.bindForm($("#inventory-form"), {
			feedbackId: "inventory-feedback",
			endpoint: "/api/inventory",
			busyText: "Adding…",
			payload: (v) => ({ item_name: v.item_name.trim(), category: v.category, quantity: Number(v.quantity), reorder_level: Number(v.reorder_level) }),
			success: (data) => data.message,
			onSuccess: reload
		});
	}

	/* Issue / return: GET /api/inventory (item list), GET /api/loans, POST /api/movements */
	const movementForm = $("#movement-form");
	if (movementForm) {
		const itemSelect = $("#inventory-item");
		const feedback = $("#movement-feedback");

		async function loadItems() {
			try {
				const { items } = await api.get("/api/inventory");
				ui.fillSelect(itemSelect, items, (item) => ({ value: item.id, label: `${item.name} (${item.stock} in stock)` }));
			} catch (error) {
				ui.showFeedback(feedback, "error", `Could not load inventory items. ${error.message}`);
			}
		}
		const reloadLoans = ui.createTable({
			tbody: $("#loans-table tbody"),
			columns: 4,
			emptyText: "No items are currently on loan.",
			load: async () => (await api.get("/api/loans")).items,
			renderRow: (l) => `<tr><td>${esc(l.borrower)}</td><td>${esc(l.item)}${l.quantity > 1 ? ` ×${esc(l.quantity)}` : ""}</td><td>${ui.formatDate(l.due, false)}</td><td>${ui.badge(l.status, l.tone)}</td></tr>`
		});

		loadItems();
		reloadLoans();
		ui.bindForm(movementForm, {
			feedbackId: "movement-feedback",
			endpoint: "/api/movements",
			busyText: "Saving…",
			beforeSubmit: () => {
				const due = movementForm.elements["due_date"];
				const issuing = movementForm.elements["movement_type"].value === "issue";
				const tooEarly = issuing && due.value && due.value < movementForm.elements["movement_date"].value;
				due.setCustomValidity(tooEarly ? "Due date cannot be before the issue date." : "");
				if (tooEarly) { due.reportValidity(); return false; }
			},
			payload: (v) => {
				const body = { movement_type: v.movement_type, item_id: Number(v.item), borrower_id: v.borrower_id.trim(), quantity: Number(v.quantity), movement_date: v.movement_date };
				if (v.movement_type === "issue") body.due_date = v.due_date;
				return body;
			},
			success: (data) => data.message,
			afterReset: () => {
				movementForm.elements["movement_date"].value = ui.todayISO();
				$("#movement-type").dispatchEvent(new Event("change")); // re-run the page's due-date show/hide
			},
			onSuccess: () => Promise.all([loadItems(), reloadLoans()])
		});
	}

	/* Maintenance: GET /api/maintenance (log + summary) and POST /api/maintenance */
	const maintenanceForm = $("#maintenance-form");
	if (maintenanceForm) {
		const showSummary = (summary) => {
			for (const [key, value] of Object.entries(summary)) {
				const card = document.querySelector(`[data-stat="${key}"]`);
				if (card) card.textContent = value;
			}
		};
		const reload = ui.createTable({
			tbody: $("#maintenance-table tbody"),
			columns: 4,
			emptyText: "No maintenance issues have been logged.",
			load: async () => {
				const data = await api.get("/api/maintenance");
				showSummary(data.summary);
				return data.items;
			},
			renderRow: (m) => `<tr><td>${esc(m.item)}</td><td>${esc(m.issue)}</td><td>${ui.formatDate(m.reported, false)}</td><td>${ui.badge(m.status, m.tone)}</td></tr>`
		});
		reload();

		ui.bindForm(maintenanceForm, {
			feedbackId: "maintenance-feedback",
			endpoint: "/api/maintenance",
			busyText: "Logging…",
			payload: (v) => ({ equipment: v.equipment.trim(), reported_by: v.reported_by.trim(), priority: v.priority, date: v.date, description: v.description.trim() }),
			success: (data) => data.message,
			onSuccess: reload
		});
	}
})();
