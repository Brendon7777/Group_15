/* Dashboards and reports: KPI cards, approval actions and report tables (Task 3B). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;
	const banner = $("#dashboard-feedback");

	/* ---------- shared KPI helpers: <p data-kpi="key"> holds the number, <p data-kpi-note="key"> the note ---------- */
	function showKpis(kpis) {
		for (const [key, kpi] of Object.entries(kpis)) {
			const value = $(`[data-kpi="${key}"]`);
			const note = $(`[data-kpi-note="${key}"]`);
			if (value) value.textContent = Number(kpi.value).toLocaleString("en-GB");
			if (note) note.textContent = kpi.note;
		}
	}
	function showKpiError() {
		document.querySelectorAll("[data-kpi]").forEach((el) => { el.textContent = "–"; });
		document.querySelectorAll("[data-kpi-note]").forEach((el) => { el.textContent = "Unavailable"; });
	}
	function showLoadError(message, retry) {
		banner.className = "form-feedback form-feedback--error";
		banner.setAttribute("role", "alert");
		banner.innerHTML = `${esc(message)} <button type="button" class="state-retry">Try again</button>`;
		banner.hidden = false;
		banner.querySelector("button").addEventListener("click", () => { banner.hidden = true; retry(); });
	}

	/* ---------- Teacher / staff dashboard: GET /api/dashboard/user ---------- */
	if ($("#dashboard-activity-tiles")) {
		const loansBody = $(".issued-items-table tbody");
		const issuedCount = $("#issued-count");
		const bookingCard = $("#next-booking");

		function render(data) {
			showKpis(data.kpis);
			for (const card of document.querySelectorAll("[data-category]")) {
				const info = data.categories.find((c) => c.category === card.dataset.category);
				if (!info) continue;
				card.querySelector("[data-cat-count]").textContent = `${info.units.toLocaleString("en-GB")} items`;
				const badge = card.querySelector("[data-cat-badge]");
				badge.textContent = info.label;
				badge.className = ui.badgeClass(info.tone);
			}
			issuedCount.textContent = `${data.loans.length} active item${data.loans.length === 1 ? "" : "s"}`;
			ui.setRows(loansBody, 4, data.loans, (l) => `<tr><td class="issued-item-name">${esc(l.item)}${l.quantity > 1 ? ` ×${esc(l.quantity)}` : ""}</td><td>${ui.formatDate(l.issued)}</td><td>${ui.formatDate(l.due)}</td><td><span class="badge issued-status ${l.tone === "ok" ? "issued-status--active" : "issued-status--due"}">${esc(l.status)}</span></td></tr>`, "Nothing is currently issued to you.");
			const b = data.next_booking;
			bookingCard.innerHTML = b
				? `<div class="booking-card__top"><h3>${esc(b.equipment)}</h3>${ui.badge(b.status, b.tone)}</div><p class="booking-date"><span aria-hidden="true">◷</span> ${ui.formatDate(b.date, false)} · ${esc(b.start)}–${esc(b.end)}</p><p class="booking-detail">${esc(b.room)} · ${esc(b.purpose)}</p>`
				: `<p class="booking-detail">You have no upcoming bookings. <a href="book-equipment.html">Book equipment</a></p>`;
		}

		async function start() {
			banner.hidden = true;
			ui.rowMessage(loansBody, 4, "loading", "Loading…");
			bookingCard.innerHTML = `<p class="booking-detail">Loading…</p>`;
			try {
				render(await api.get("/api/dashboard/user"));
			} catch (error) {
				showKpiError();
				ui.rowMessage(loansBody, 4, "error", esc(error.message));
				bookingCard.innerHTML = `<p class="booking-detail">Could not load your next booking.</p>`;
				showLoadError(`Could not load your dashboard. ${error.message}`, start);
			}
		}
		start();
	}

	/* ---------- Committee dashboard: KPIs and request / booking actions ---------- */
	const committeeGrid = $(".committee-dashboard .content-grid");
	if (committeeGrid) {
		const actionFeedback = $("#action-feedback");
		const decisionButtons = (kind, id, name, accept) => `<div class="request-decision-actions"><button class="request-decision-button" type="button" data-kind="${kind}" data-id="${esc(id)}" data-decision="${accept}" aria-label="Accept ${esc(name)} ${kind}">Accept</button><button class="request-decision-button request-decision-button--decline" type="button" data-kind="${kind}" data-id="${esc(id)}" data-decision="Declined" aria-label="Decline ${esc(name)} ${kind}">Decline</button></div>`;
		const currency = new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" });
		const abcBasisButtons = Array.from(document.querySelectorAll("[data-abc-basis]"));
		let abcBasis = "value";
		let abcRequestVersion = 0;
		function showABCClassifications(data) {
			const usageMode = data.abc_basis_mode === "usage";
			$("#abc-basis-column-heading").textContent = usageMode ? "Usage basis" : "Value basis";
			$("#abc-value-column-heading").textContent = usageMode ? "Annual usage" : "Value (R)";
			$("#abc-basis-help").textContent = usageMode
				? "Annual usage uses forecast quantities for consumables and recorded issues in the last 12 months for reusable items. Items without recorded usage are unclassified."
				: "Value mode uses forecast annual usage value for consumables and current stock value for non-consumables.";
			$("#business-abc-table").innerHTML = data.abc_items.length
				? data.abc_items.map((item) => {
					const type = item.inventory_type === "consumable"
						? "Consumable"
						: item.inventory_type === "non_consumable" ? "Non-consumable" : "Choose type";
					const value = item.abc_value === null
						? item.abc_basis
						: usageMode
							? `${Number(item.abc_value).toLocaleString("en-ZA", { maximumFractionDigits: 2 })} ${item.unit}/year`
							: currency.format(item.abc_value);
					return `<tr><th scope="row">${esc(item.name)}</th><td>${type}</td><td><span class="abc-class">${esc(item.abc_class)}</span></td><td>${esc(item.abc_basis)}</td><td>${esc(value)}</td></tr>`;
				}).join("")
				: '<tr><td colspan="5">No inventory items have been added.</td></tr>';
		}

		async function loadABCClassifications() {
			const requestVersion = ++abcRequestVersion;
			const basis = abcBasis;
			try {
				const data = await api.get("/api/dashboard/business-value", {
					basis
				});
				if (requestVersion !== abcRequestVersion) return;
				showABCClassifications(data);
			} catch (error) {
				if (requestVersion !== abcRequestVersion) return;
				$("#business-abc-table").innerHTML =
					`<tr><td colspan="5">ABC classification data could not be loaded. ${esc(error.message)}</td></tr>`;
			}
		}
		abcBasisButtons.forEach((button) => {
			button.addEventListener("click", () => {
				if (button.dataset.abcBasis === abcBasis) return;
				abcBasis = button.dataset.abcBasis;
				abcBasisButtons.forEach((option) => {
					option.setAttribute("aria-pressed", String(option.dataset.abcBasis === abcBasis));
				});
				loadABCClassifications();
			});
		});

		async function loadSummary() {
			banner.hidden = true;
			try {
				const data = await api.get("/api/dashboard/committee");
				showKpis(data.kpis);
				loadABCClassifications();
			} catch (error) {
				showKpiError();
				showLoadError(`Could not load the committee summary. ${error.message}`, loadSummary);
			}
		}

		const reloadRequests = ui.createTable({
			tbody: $("#committee-requests-table tbody"),
			columns: 5,
			emptyText: "No requests are waiting for review.",
			load: async () => (await api.get("/api/committee/requests", { status: "In review" })).items,
			renderRow: (r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.requested_by)}</td><td>${esc(r.submitted_at || "Unknown")}</td><td>${ui.badge(r.priority, r.priority_tone)}</td><td><div class="request-decision-actions"><a class="request-decision-button" href="request-management.html?request_id=${encodeURIComponent(r.id)}">Review</a><button class="request-decision-button request-decision-button--decline" type="button" data-kind="request" data-id="${esc(r.id)}" data-decision="Declined" aria-label="Decline ${esc(r.name)} request">Decline</button></div></td></tr>`
		});
		const reloadBookings = ui.createTable({
			tbody: $("#committee-bookings-table tbody"),
			columns: 5,
			emptyText: "There are no upcoming equipment bookings.",
			load: async () => (await api.get("/api/committee/bookings")).items,
			renderRow: (b) => {
				const actions = b.status === "Awaiting approval"
					? decisionButtons("booking", b.id, b.equipment, "Confirmed")
					: b.status === "Confirmed" && `${b.date}T${b.start}` > new Date().toISOString().slice(0, 16)
						? `<button class="request-decision-button request-decision-button--decline" type="button" data-kind="booking" data-id="${esc(b.id)}" data-decision="Declined" data-cancel-confirmed="true" aria-label="Cancel ${esc(b.equipment)} booking">Cancel</button>`
						: "—";
				return `<tr><td>${esc(b.equipment)} · ${esc(b.room)}</td><td>${esc(b.booked_by)}</td><td>${ui.formatDate(b.date, false)}, ${esc(b.start)}</td><td>${ui.badge(b.status, b.tone)}</td><td>${actions}</td></tr>`;
			}
		});
		const reloadAll = () => Promise.all([reloadRequests(), reloadBookings(), loadSummary()]);

		committeeGrid.addEventListener("click", async (event) => {
			const button = event.target.closest("button[data-decision]");
			if (!button) return;
			if (button.dataset.cancelConfirmed && !window.confirm("Cancel this confirmed equipment booking?")) return;
			const rowButtons = button.closest("tr").querySelectorAll("button");
			rowButtons.forEach((b) => { b.disabled = true; });
			const url = `/api/${button.dataset.kind === "booking" ? "bookings" : "requests"}/${encodeURIComponent(button.dataset.id)}/decision`;
			try {
				const data = await api.post(url, { decision: button.dataset.decision });
				ui.showFeedback(actionFeedback, "success", data.message);
				await reloadAll();
			} catch (error) {
				ui.showFeedback(actionFeedback, "error", error.message);
				if (error.status === 409 || error.status === 404) await reloadAll(); // someone else already decided it
				else rowButtons.forEach((b) => { b.disabled = false; });
			}
		});

		loadSummary();
		reloadRequests();
		reloadBookings();
	}

	/* ---------- Reports: GET /api/reports feeds three tables ---------- */
	const categoryBody = $("#category-summary-table tbody");
	if (categoryBody) {
		// The three tables share one request (made once per second at most). A failed request is never kept,
		// and "Try again" on any table reloads all three.
		let shared = null;
		const getReport = () => {
			if (!shared) {
				const request = api.get("/api/reports");
				const forget = () => { if (shared === request) shared = null; };
				request.then(() => setTimeout(forget, 1000), forget);
				shared = request;
			}
			return shared;
		};
		const reloaders = [];
		const reloadAll = () => reloaders.forEach((reload) => reload());
		const addTable = (config) => reloaders.push(ui.createTable({ ...config, retry: reloadAll }));

		addTable({
			tbody: $(".insights-table tbody"), columns: 3, emptyText: "No report data is available yet.",
			load: async () => (await getReport()).summary,
			renderRow: (s) => `<tr><td>${esc(s.area)}</td><td>${esc(s.finding)}</td><td>${esc(s.action)}</td></tr>`
		});
		addTable({
			tbody: categoryBody, columns: 5, emptyText: "No inventory has been recorded yet.",
			load: async () => (await getReport()).categories,
			renderRow: (c) => `<tr><td>${esc(c.category)}</td><td>${esc(c.total)}</td><td>${esc(c.available)}</td><td>${esc(c.low_stock)}</td><td>${ui.badge(c.condition, c.tone)}</td></tr>`
		});
		addTable({
			tbody: $(".status-table tbody"), columns: 2, emptyText: "No requests have been submitted yet.",
			load: async () => (await getReport()).requests_by_status,
			renderRow: (s) => `<tr><td>${ui.badge(s.status, s.tone)}</td><td>${esc(s.count)}</td></tr>`
		});
		reloadAll();
	}
})();
