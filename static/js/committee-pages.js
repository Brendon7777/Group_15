/* LTSM committee pages: manage inventory, issue / return, maintenance (Task 3A). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;

	/* User management: committee-only account listing, creation and access toggles. */
	const usersBody = $("#users-table tbody");
	if (usersBody) {
		const feedback = $("#users-list-feedback");
		const reloadUsers = ui.createTable({
			tbody: usersBody,
			columns: 6,
			emptyText: "No user accounts have been created.",
			load: async () => (await api.get("/api/committee/users")).items,
			renderRow: (user) => {
				const role = { learner: "Learner", staff: "Teacher / staff", ltsm: "LTSM committee" }[user.role] || user.role;
				const access = user.is_active ? "Active" : "Deactivated";
				const action = user.is_current_user
					? '<span class="muted">Current account</span>'
					: `<button class="button button-secondary" type="button" data-user-id="${esc(user.id)}" data-active="${user.is_active ? "true" : "false"}">${user.is_active ? "Deactivate" : "Reactivate"}</button>`;
				return `<tr><td>${esc(user.name)}</td><td>${esc(user.school_id)}</td><td>${esc(user.email)}</td><td>${esc(role)}</td><td>${esc(access)}</td><td class="account-actions">${action}</td></tr>`;
			}
		});
		reloadUsers();

		ui.bindForm($("#user-management-form"), {
			feedbackId: "user-management-feedback",
			endpoint: "/api/committee/users",
			busyText: "Creating…",
			payload: (values) => ({
				full_name: values.full_name.trim(),
				role: values.role,
				school_id: values.school_id.trim(),
				email: values.email.trim(),
				password: values.password
			}),
			success: (data) => data.message,
			onSuccess: reloadUsers
		});

		usersBody.addEventListener("click", async (event) => {
			const button = event.target.closest("[data-user-id]");
			if (!button) return;
			const isActive = button.dataset.active === "true";
			if (isActive && !window.confirm("Deactivate this account? It will no longer be able to sign in.")) return;
			ui.hideFeedback(feedback);
			ui.setBusy(button, true, isActive ? "Deactivating…" : "Reactivating…");
			try {
				const result = await api.post(`/api/committee/users/${encodeURIComponent(button.dataset.userId)}/status`, { is_active: !isActive });
				ui.showFeedback(feedback, "success", result.message);
				await reloadUsers();
			} catch (error) {
				ui.showFeedback(feedback, "error", error.message);
				ui.setBusy(button, false);
			}
		});
	}

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

		const adjustmentItem = $("#adjustment-item");
		async function loadAdjustmentItems() {
			try {
				const { items } = await api.get("/api/inventory");
				ui.fillSelect(adjustmentItem, items, (item) => ({
					value: item.id,
					label: `${item.name} | ${item.category} | ${item.stock} in stock | Reorder at ${item.reorder_level} | ${item.status}`
				}));
			} catch (error) {
				ui.showFeedback($("#stock-adjustment-feedback"), "error", `Could not load inventory items. ${error.message}`);
			}
		}
		loadAdjustmentItems();
		const reloadAdjustments = ui.createTable({
			tbody: $("#adjustments-table tbody"),
			columns: 7,
			emptyText: "No stock adjustments have been recorded.",
			load: async () => (await api.get("/api/inventory/adjustments")).items,
			renderRow: (a) => `<tr><td>${esc(a.item)}</td><td>${esc(a.adjustment_type)}</td><td>${Number(a.quantity_change) > 0 ? "+" : ""}${esc(a.quantity_change)}</td><td>${a.quantity_after === null ? "—" : esc(a.quantity_after)}</td><td>${esc(a.reason)}</td><td>${esc(a.recorded_by)}</td><td>${esc(a.adjusted_at)}</td></tr>`
		});
		reloadAdjustments();
		const suggestionsBody = $("#suggestions-table tbody");
		const reloadSuggestions = ui.createTable({
			tbody: suggestionsBody,
			columns: 4,
			emptyText: "No resource suggestions have been submitted.",
			load: async () => (await api.get("/api/committee/suggestions")).items,
			renderRow: (suggestion) => `<tr><td>${esc(suggestion.name)}</td><td>${esc(suggestion.message)}</td><td>${esc(suggestion.submitted_by)}</td><td>${esc(suggestion.submitted)}</td></tr>`
		});
		reloadSuggestions();

		ui.bindForm($("#inventory-form"), {
			feedbackId: "inventory-feedback",
			endpoint: "/api/inventory",
			busyText: "Adding…",
			payload: (v) => ({ item_name: v.item_name.trim(), category: v.category, quantity: Number(v.quantity), reorder_level: Number(v.reorder_level) }),
			success: (data) => data.message,
			onSuccess: () => Promise.all([reload(), loadAdjustmentItems()])
		});
		ui.bindForm($("#stock-adjustment-form"), {
			feedbackId: "stock-adjustment-feedback",
			endpoint: "/api/inventory/adjust",
			busyText: "Adjusting…",
			payload: (v) => ({ item_id: Number(v.item_id), action: v.action, quantity: Number(v.quantity), reason: v.reason.trim() }),
			success: (data) => data.message,
			onSuccess: () => Promise.all([reload(), loadAdjustmentItems(), reloadAdjustments()])
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
