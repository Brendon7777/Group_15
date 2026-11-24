/* LTSM committee pages: manage inventory, issue / return, maintenance (Task 3A). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;

	/* All equipment bookings: include past, upcoming, pending and declined reservations. */
	const allBookingsBody = $("#all-bookings-table tbody");
	if (allBookingsBody) {
		const statusFilter = $("#all-bookings-status");
		const feedback = $("#all-bookings-feedback");
		const statusTone = { "Awaiting approval": "warning", Confirmed: "ok", Declined: "danger" };
		const reloadAllBookings = ui.createTable({
			tbody: allBookingsBody,
			columns: 7,
			emptyText: "No equipment bookings match this status.",
			load: async () => (await api.get("/api/committee/bookings", { all: true, status: statusFilter.value })).items,
			renderRow: (booking) => {
				const action = booking.status === "Awaiting approval"
					? `<div class="booking-actions"><button class="button button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Confirmed">Approve</button><button class="button button-secondary button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Declined">Decline</button></div>`
					: booking.status === "Confirmed" && `${booking.date}T${booking.start}` > new Date().toISOString().slice(0, 16)
						? `<button class="button button-secondary button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Declined" data-cancel-confirmed="true">Cancel</button>`
						: "—";
				return `<tr><td>${esc(booking.equipment)}</td><td>${esc(booking.booked_by)}</td><td>${ui.formatDate(booking.date)}<br>${esc(booking.start)}–${esc(booking.end)}</td><td>${esc(booking.room)}</td><td>${esc(booking.purpose)}</td><td>${ui.badge(booking.status, statusTone[booking.status])}</td><td>${action}</td></tr>`;
			}
		});
		statusFilter.addEventListener("change", reloadAllBookings);
		allBookingsBody.addEventListener("click", async (event) => {
			const button = event.target.closest("[data-booking-decision]");
			if (!button) return;
			if (button.dataset.cancelConfirmed && !window.confirm("Cancel this confirmed equipment booking?")) return;
			const rowButtons = button.closest("tr").querySelectorAll("button");
			rowButtons.forEach((item) => { item.disabled = true; });
			try {
				const result = await api.post(
					`/api/bookings/${encodeURIComponent(button.dataset.bookingId)}/decision`,
					{ decision: button.dataset.bookingDecision }
				);
				ui.showFeedback(feedback, "success", result.message);
				await reloadAllBookings();
				document.dispatchEvent(new Event("booking-calendar-refresh"));
			} catch (error) {
				ui.showFeedback(feedback, "error", error.message);
				if (error.status === 404 || error.status === 409) {
					await reloadAllBookings();
					document.dispatchEvent(new Event("booking-calendar-refresh"));
				}
				else rowButtons.forEach((item) => { item.disabled = false; });
			}
		});
		reloadAllBookings();
	}

	/* Booking calendar: switch between daily, weekly and monthly views. */
	const bookingCalendar = $("#booking-calendar");
	if (bookingCalendar) {
		const calendarTitle = $("#booking-calendar-title");
		const calendarStatus = $("#calendar-booking-status");
		const shortWeekdayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
		let calendarDate = new Date();
		calendarDate.setHours(0, 0, 0, 0);
		let calendarView = "month";
		let calendarBookings = [];
		let calendarLoad = 0;
		const dateKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
		const parseDate = (value) => {
			const [year, month, day] = value.split("-").map(Number);
			return new Date(year, month - 1, day);
		};
		const shiftDate = (date, days) => {
			const shifted = new Date(date);
			shifted.setDate(shifted.getDate() + days);
			return shifted;
		};
		const mondayStart = (date) => shiftDate(date, -((date.getDay() + 6) % 7));
		const dateLabel = (date, options) => date.toLocaleDateString("en-GB", options);
		const bookingMarkup = (booking) => {
			const statusClass = booking.status === "Declined"
				? " calendar-booking--declined"
				: booking.status === "Awaiting approval" ? " calendar-booking--awaiting" : "";
			const canCancel = booking.status === "Confirmed" && `${booking.date}T${booking.start}` > new Date().toISOString().slice(0, 16);
			const actions = booking.status === "Awaiting approval"
				? `<button class="button button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Confirmed">Approve</button><button class="button button-secondary button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Declined">Decline</button>`
				: canCancel
					? `<button class="button button-secondary button-small" type="button" data-booking-id="${esc(booking.id)}" data-booking-decision="Declined" data-cancel-confirmed="true">Cancel</button>`
					: "";
			return `<div class="calendar-booking${statusClass}"><span class="calendar-booking__time">${esc(booking.start)}–${esc(booking.end)}</span><strong>${esc(booking.equipment)}</strong><br>${esc(booking.booked_by)} · ${esc(booking.room)}<br>${esc(booking.status)}${actions ? `<div class="booking-actions">${actions}</div>` : ""}</div>`;
		};

		function renderCalendar() {
			const todayKey = dateKey(new Date());
			const selectedKey = dateKey(calendarDate);
			if (calendarView === "day") {
				calendarTitle.textContent = dateLabel(calendarDate, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
				const bookings = calendarBookings.filter((booking) => booking.date === selectedKey);
				bookingCalendar.innerHTML = `<div class="calendar-day calendar-day--single${selectedKey === todayKey ? " calendar-day--selected" : ""}"><span class="calendar-day__number${selectedKey === todayKey ? " calendar-day__number--today" : ""}">${esc(dateLabel(calendarDate, { weekday: "long", day: "numeric", month: "long" }))}</span>${bookings.length ? bookings.map(bookingMarkup).join("") : '<p class="calendar-empty">No equipment bookings for this day.</p>'}</div>`;
				return;
			}

			if (calendarView === "week") {
				const firstDay = mondayStart(calendarDate);
				const lastDay = shiftDate(firstDay, 6);
				calendarTitle.textContent = `${dateLabel(firstDay, { day: "numeric", month: "short" })} – ${dateLabel(lastDay, { day: "numeric", month: "short", year: "numeric" })}`;
				const days = Array.from({ length: 7 }, (_, index) => shiftDate(firstDay, index));
				bookingCalendar.innerHTML = `<div class="calendar-grid">${days.map((day, index) => {
					const key = dateKey(day);
					const bookings = calendarBookings.filter((booking) => booking.date === key);
					return `<section class="calendar-day${key === todayKey ? " calendar-day--selected" : ""}"><span class="calendar-day__number${key === todayKey ? " calendar-day__number--today" : ""}">${shortWeekdayNames[index]} ${day.getDate()}</span>${bookings.length ? bookings.map(bookingMarkup).join("") : '<p class="calendar-empty">No bookings</p>'}</section>`;
				}).join("")}</div>`;
				return;
			}

			const monthStart = new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
			const gridStart = mondayStart(monthStart);
			const monthEnd = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 0);
			const gridEnd = shiftDate(mondayStart(monthEnd), 6);
			calendarTitle.textContent = dateLabel(calendarDate, { month: "long", year: "numeric" });
			const dayCount = Math.round((gridEnd - gridStart) / 86400000) + 1;
			const cells = Array.from({ length: dayCount }, (_, index) => shiftDate(gridStart, index));
			bookingCalendar.innerHTML = `<div class="calendar-grid">${shortWeekdayNames.map((day) => `<div class="calendar-weekday">${day}</div>`).join("")}${cells.map((day) => {
				const key = dateKey(day);
				const bookings = calendarBookings.filter((booking) => booking.date === key);
				const outside = day.getMonth() !== calendarDate.getMonth();
				const visible = bookings.slice(0, 3).map(bookingMarkup).join("");
				const more = bookings.length > 3 ? `<div class="calendar-booking">+${bookings.length - 3} more booking${bookings.length - 3 === 1 ? "" : "s"}</div>` : "";
				return `<div class="calendar-day${outside ? " calendar-day--outside" : ""}${key === todayKey ? " calendar-day--selected" : ""}"><button class="calendar-day-select" type="button" data-calendar-date="${key}" aria-label="View ${esc(dateLabel(day, { weekday: "long", day: "numeric", month: "long", year: "numeric" }))}, ${bookings.length} booking${bookings.length === 1 ? "" : "s"}">${day.getDate()}</button>${visible}${more}</div>`;
			}).join("")}</div>`;
		}

		async function loadCalendar() {
			const ticket = ++calendarLoad;
			bookingCalendar.setAttribute("aria-busy", "true");
			bookingCalendar.innerHTML = '<p class="calendar-empty">Loading bookings…</p>';
			try {
				const { items } = await api.get("/api/committee/bookings", { all: true, status: calendarStatus.value });
				if (ticket !== calendarLoad) return;
				calendarBookings = items;
				renderCalendar();
			} catch (error) {
				if (ticket !== calendarLoad) return;
				bookingCalendar.innerHTML = `<p class="calendar-empty">${esc(error.message)}</p>`;
			} finally {
				if (ticket === calendarLoad) bookingCalendar.removeAttribute("aria-busy");
			}
		}

		document.querySelectorAll("[data-calendar-view]").forEach((button) => {
			button.addEventListener("click", () => {
				calendarView = button.dataset.calendarView;
				document.querySelectorAll("[data-calendar-view]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
				renderCalendar();
			});
		});
		$("#booking-calendar-previous").addEventListener("click", () => {
			if (calendarView === "day") calendarDate = shiftDate(calendarDate, -1);
			else if (calendarView === "week") calendarDate = shiftDate(calendarDate, -7);
			else calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() - 1, 1);
			renderCalendar();
		});
		$("#booking-calendar-next").addEventListener("click", () => {
			if (calendarView === "day") calendarDate = shiftDate(calendarDate, 1);
			else if (calendarView === "week") calendarDate = shiftDate(calendarDate, 7);
			else calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 1);
			renderCalendar();
		});
		$("#booking-calendar-today").addEventListener("click", () => {
			calendarDate = new Date();
			calendarDate.setHours(0, 0, 0, 0);
			renderCalendar();
		});
		calendarStatus.addEventListener("change", loadCalendar);
		document.addEventListener("booking-calendar-refresh", loadCalendar);
		bookingCalendar.addEventListener("click", (event) => {
			const decisionButton = event.target.closest("[data-booking-decision]");
			if (decisionButton) {
				event.preventDefault();
				event.stopPropagation();
				if (decisionButton.dataset.cancelConfirmed && !window.confirm("Cancel this confirmed equipment booking?")) return;
				decisionButton.disabled = true;
				api.post(
					`/api/bookings/${encodeURIComponent(decisionButton.dataset.bookingId)}/decision`,
					{ decision: decisionButton.dataset.bookingDecision }
				).then((result) => {
					ui.showFeedback($("#all-bookings-feedback"), "success", result.message);
					document.dispatchEvent(new Event("booking-calendar-refresh"));
				}).catch((error) => {
					ui.showFeedback($("#all-bookings-feedback"), "error", error.message);
					decisionButton.disabled = false;
				});
				return;
			}
			const dayButton = event.target.closest("button[data-calendar-date]");
			if (!dayButton) return;
			calendarDate = parseDate(dayButton.dataset.calendarDate);
			calendarView = "day";
			document.querySelectorAll("[data-calendar-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.calendarView === calendarView)));
			renderCalendar();
		});
		loadCalendar();
	}

	/* Request management: review availability, reserve stock and record fulfillment. */
	const requestTableBody = $("#committee-request-management-table tbody");
	if (requestTableBody) {
		const requestStatus = $("#committee-request-status");
		const requestFeedback = $("#request-management-feedback");
		const reviewPanel = $("#request-review-panel");
		const decisionForm = $("#request-decision-form");
		const decisionSelect = $("#request-decision");
		const collectionField = $("#collection-slot-field");
		const collectionInput = $("#collection-slot");
		const collectionLocation = $("#collection-location");
		const collectionLocationField = $("#collection-location-field");
		const saveDecisionButton = decisionForm.querySelector('button[type="submit"]');
		const requestsById = new Map();
		const statusTone = { "In review": "warning", Approved: "ok", "Ready for collection": "blue", Fulfilled: "ok", Declined: "danger" };
		const localDateTime = () => {
			const now = new Date();
			return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
		};
		collectionInput.min = localDateTime();

		function updateDecisionForm() {
			const approving = decisionSelect.value === "Approved";
			collectionField.hidden = !approving;
			collectionLocationField.hidden = !approving;
			collectionInput.required = approving;
			collectionLocation.required = approving;
			const request = requestsById.get(decisionForm.elements.request_id.value);
			const enoughStock = request && request.resource_id && request.available_stock >= request.quantity;
			saveDecisionButton.disabled = approving && (!enoughStock || !collectionLocation.value);
			if (approving && !enoughStock) {
				saveDecisionButton.title = "The full requested quantity must be in stock before approval.";
			} else if (approving && !collectionLocation.value) {
				saveDecisionButton.title = "Select a collection location before approval.";
			} else {
				saveDecisionButton.removeAttribute("title");
			}
		}

		async function loadCollectionLocations() {
			try {
				const { items } = await api.get("/api/collection-locations");
				ui.fillSelect(collectionLocation, items, (location) => ({
					value: location.id,
					label: location.name
				}));
				updateDecisionForm();
			} catch (error) {
				ui.showFeedback(requestFeedback, "error", `Could not load collection locations. ${error.message}`);
			}
		}

		const reloadRequests = ui.createTable({
			tbody: requestTableBody,
			columns: 8,
			emptyText: "No requests match this status filter.",
			load: async () => {
				const { items } = await api.get("/api/committee/requests", { status: requestStatus.value });
				requestsById.clear();
				items.forEach((request) => requestsById.set(String(request.id), request));
				return items;
			},
			renderRow: (request) => {
				const available = request.available_stock === null
					? "Not in inventory"
					: `${request.available_stock} ${request.unit || ""}`.trim();
				let action = "—";
				if (request.status === "In review" ||
					(["Approved", "Ready for collection"].includes(request.status) && request.allocated_quantity === null)) {
					action = `<button class="button button-secondary button-small" type="button" data-review-request="${esc(request.id)}">Review</button>`;
				} else if (request.status === "Ready for collection") {
					const slot = request.collection_slot ? `<small>${esc(request.collection_slot)}</small>` : "";
					const location = request.collection_location ? `<small>${esc(request.collection_location)}</small>` : "";
					const dueDate = ["Textbooks", "Equipment"].includes(request.category)
						? `<label class="sr-only" for="fulfill-due-${esc(request.id)}">Expected return date for ${esc(request.name)} request</label><input id="fulfill-due-${esc(request.id)}" type="date" data-fulfill-due required min="${ui.todayISO()}">`
						: "";
					action = `<div class="request-actions">${slot}${location}${dueDate}<button class="button button-small" type="button" data-fulfill-request="${esc(request.id)}">Mark fulfilled</button></div>`;
				}
				const quantity = request.allocated_quantity
					? `${request.quantity} requested · ${request.allocated_quantity} allocated`
					: `${request.quantity} ${request.unit || ""}`.trim();
				return `<tr><td><strong>${esc(request.name)}</strong><br><small>${esc(request.category)}</small></td><td>${esc(request.requested_by)}<br><small>${esc(request.requester_id)}</small></td><td>${esc(request.submitted_at || "Unknown")}</td><td>${request.needed_by ? ui.formatDate(request.needed_by, false) : "Not specified"}</td><td>${esc(quantity)}</td><td>${esc(available)}</td><td>${ui.badge(request.status, statusTone[request.status])}</td><td>${action}</td></tr>`;
			}
		});
		requestStatus.addEventListener("change", reloadRequests);

		function openReview(request) {
			decisionForm.elements.request_id.value = request.id;
			decisionSelect.value = "Approved";
			$("#review-request-item").textContent = `${request.name} · ${request.category} · ${request.quantity} ${request.unit || ""}`;
			$("#review-requester").textContent = `${request.requested_by} (${request.requester_id})`;
			$("#review-purpose").textContent = request.purpose;
			const note = $("#request-availability-note");
			if (request.resource_id === null) {
				note.textContent = "This request does not match an inventory item. Add or link the item in inventory before approving.";
			} else if (request.available_stock < request.quantity) {
				note.textContent = `Only ${request.available_stock} ${request.unit} are available; ${request.quantity} were requested. Stock is not sufficient to approve.`;
			} else {
				note.textContent = `${request.available_stock} ${request.unit} available. Approving will reserve ${request.quantity} ${request.unit} until the item is issued.`;
			}
			collectionInput.value = "";
			collectionLocation.value = "";
			collectionInput.min = localDateTime();
			ui.hideFeedback($("#request-decision-feedback"));
			reviewPanel.hidden = false;
			updateDecisionForm();
			reviewPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
		}

		requestTableBody.addEventListener("click", async (event) => {
			const reviewButton = event.target.closest("[data-review-request]");
			if (reviewButton) {
				const request = requestsById.get(reviewButton.dataset.reviewRequest);
				if (request) openReview(request);
				return;
			}
			const fulfillButton = event.target.closest("[data-fulfill-request]");
			if (!fulfillButton) return;
			const dueDateInput = fulfillButton.closest(".request-actions").querySelector("[data-fulfill-due]");
			if (dueDateInput && !dueDateInput.value) {
				dueDateInput.reportValidity();
				return;
			}
			fulfillButton.disabled = true;
			try {
				const result = await api.post(
					`/api/committee/requests/${encodeURIComponent(fulfillButton.dataset.fulfillRequest)}/fulfill`,
					dueDateInput ? { due_date: dueDateInput.value } : {}
				);
				ui.showFeedback(requestFeedback, "success", result.message);
				await reloadRequests();
			} catch (error) {
				ui.showFeedback(requestFeedback, "error", error.message);
				fulfillButton.disabled = false;
				if (error.status === 409 || error.status === 404) await reloadRequests();
			}
		});

		decisionSelect.addEventListener("change", updateDecisionForm);
		collectionLocation.addEventListener("change", updateDecisionForm);
		$("#cancel-request-review").addEventListener("click", () => {
			reviewPanel.hidden = true;
			decisionForm.reset();
		});
		ui.bindForm(decisionForm, {
			feedbackId: "request-decision-feedback",
			endpoint: (values) => `/api/requests/${encodeURIComponent(values.request_id)}/decision`,
			busyText: "Saving…",
			payload: (values) => ({
				decision: values.decision,
				...(values.decision === "Approved" ? {
					collection_slot: values.collection_slot,
					collection_location_id: Number(values.collection_location_id)
				} : {})
			}),
			success: (data) => data.message,
			onSuccess: async () => {
				await reloadRequests();
				reviewPanel.hidden = true;
				decisionForm.reset();
				ui.showFeedback(requestFeedback, "success", "Request decision saved.");
			}
		});
		loadCollectionLocations();
		const selectedRequestId = new URLSearchParams(window.location.search).get("request_id");
		reloadRequests().then(() => {
			const request = selectedRequestId && requestsById.get(selectedRequestId);
			if (request && (
				request.status === "In review" ||
				(["Approved", "Ready for collection"].includes(request.status) && request.allocated_quantity === null)
			)) openReview(request);
		});
	}

	/* User management: committee-only account listing, approval and access toggles. */
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
				const status = user.account_status === "pending"
					? "Awaiting LTSM approval"
					: user.role === "learner"
						? user.is_active ? "Borrower only; sign-in disabled" : "Deactivated"
						: user.is_active ? "Active" : "Deactivated";
				const action = user.account_status === "pending"
					? `<button class="button" type="button" data-approve-user-id="${esc(user.id)}">Approve</button>`
					: user.is_current_user
						? '<span class="muted">Current account</span>'
						: `<button class="button button-secondary" type="button" data-user-id="${esc(user.id)}" data-active="${user.is_active ? "true" : "false"}">${user.is_active ? "Deactivate" : "Reactivate"}</button>`;
				return `<tr><td>${esc(user.name)}</td><td>${esc(user.school_id)}</td><td>${esc(user.email)}</td><td>${esc(role)}</td><td>${esc(status)}</td><td class="account-actions">${action}</td></tr>`;
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
			const approveButton = event.target.closest("[data-approve-user-id]");
			if (approveButton) {
				ui.hideFeedback(feedback);
				ui.setBusy(approveButton, true, "Approving…");
				try {
					const result = await api.post(`/api/committee/users/${encodeURIComponent(approveButton.dataset.approveUserId)}/approve`);
					ui.showFeedback(feedback, "success", result.message);
					await reloadUsers();
				} catch (error) {
					ui.showFeedback(feedback, "error", error.message);
					ui.setBusy(approveButton, false);
				}
				return;
			}
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
		const inventoryType = $("[data-type-filter]");
		const inventoryById = new Map();
		const currency = new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" });
		const addCategory = $("#item-category");
		const addGradeField = $("#item-grade-field");
		const addGrade = $("#item-grade");
		const editCategory = $("#edit-item-category");
		const editGradeField = $("#edit-item-grade-field");
		const editGrade = $("#edit-item-grade");
		const updateGradeVisibility = (categorySelect, gradeField, gradeSelect) => {
			const isTextbook = categorySelect.value === "Textbooks";
			gradeField.hidden = !isTextbook;
			gradeSelect.required = isTextbook;
			if (!isTextbook) gradeSelect.value = "";
		};
		const updateAddGradeVisibility = () => updateGradeVisibility(addCategory, addGradeField, addGrade);
		const updateEditGradeVisibility = () => updateGradeVisibility(editCategory, editGradeField, editGrade);
		addCategory.addEventListener("change", updateAddGradeVisibility);
		editCategory.addEventListener("change", updateEditGradeVisibility);
		$("#inventory-form").addEventListener("reset", () => window.setTimeout(updateAddGradeVisibility, 0));
		$("#inventory-edit-form").addEventListener("reset", () => window.setTimeout(updateEditGradeVisibility, 0));
		const reload = ui.createTable({
			tbody: inventoryBody,
			columns: 9,
			emptyText: "No inventory items match your filters.",
			load: async () => (await api.get("/api/inventory", { q: search.value, category: category.value, type: inventoryType.value })).items,
			renderRow: (i) => {
				inventoryById.set(String(i.id), i);
				const image = window.LTSMResourceImages.imageFor(i);
				const quantityLabel = i.category === "Equipment"
					? `${i.stock} available`
					: `${i.stock} ${i.unit} in stock`;
				const typeLabel = i.inventory_type === "consumable"
					? "Consumable"
					: i.inventory_type === "non_consumable" ? "Non-consumable" : "Choose type";
				const priceLabel = i.unit_price === null ? "Not set" : currency.format(i.unit_price);
				const gradeLabel = i.category === "Textbooks" && i.grade ? `<small>${esc(i.grade)}</small>` : "";
				return `<tr><td><div class="inventory-item"><img class="inventory-item__image" src="${image.src}" data-image-fallback="${image.fallback}" alt="${esc(i.name)}"><span>${esc(i.name)}${gradeLabel}</span></div></td><td>${esc(i.category)}</td><td>${esc(typeLabel)}</td><td>${esc(quantityLabel)}</td><td>${esc(priceLabel)}</td><td>${esc(i.reorder_level)} ${esc(i.unit)}</td><td>${esc(i.storage_location || "Not set")}</td><td>${ui.badge(i.status, i.tone)}</td><td><button class="button button-secondary button-small" type="button" data-edit-inventory="${esc(i.id)}">Edit</button></td></tr>`;
			}
		});
		search.addEventListener("input", ui.debounce(reload));
		category.addEventListener("change", reload);
		inventoryType.addEventListener("change", reload);
		reload();

		const adjustmentItem = $("#adjustment-item");
		async function loadAdjustmentItems() {
			try {
				const { items } = await api.get("/api/inventory");
				ui.fillSelect(adjustmentItem, items, (item) => ({
					value: item.id,
					label: `${item.name} | ${item.category} | ${item.category === "Equipment" ? `${item.stock} available` : `${item.stock} ${item.unit} in stock`} | Reorder at ${item.reorder_level} | ${item.status}`
				}));
			} catch (error) {
				ui.showFeedback($("#stock-adjustment-feedback"), "error", `Could not load inventory items. ${error.message}`);
			}
		}
		loadAdjustmentItems();
		const editPanel = $("#edit-item-panel");
		const editForm = $("#inventory-edit-form");
		inventoryBody.addEventListener("click", (event) => {
			const button = event.target.closest("[data-edit-inventory]");
			if (!button) return;
			const item = inventoryById.get(button.dataset.editInventory);
			if (!item) return;
			Array.from(editGrade.options)
				.filter((option) => option.dataset.legacyGrade === "true")
				.forEach((option) => option.remove());
			if (item.category === "Textbooks" && item.grade && !["Grade 1", "Grade 2", "Grade 3"].includes(item.grade)) {
				const legacyOption = new Option(`${item.grade} (legacy; hidden from teacher catalogue)`, item.grade);
				legacyOption.dataset.legacyGrade = "true";
				editGrade.add(legacyOption);
			}
			editForm.elements.item_id.value = item.id;
			editForm.elements.item_name.value = item.name;
			editForm.elements.category.value = item.category;
			editGrade.value = item.grade || "";
			updateEditGradeVisibility();
			editForm.elements.inventory_type.value = item.inventory_type || "";
			editForm.elements.reorder_level.value = item.reorder_level;
			editForm.elements.description.value = item.description || "";
			editForm.elements.unit.value = item.unit;
			editForm.elements.storage_location.value = item.storage_location || "";
			editForm.elements.unit_price.value = item.unit_price === null ? "" : item.unit_price;
			ui.hideFeedback($("#inventory-edit-feedback"));
			editPanel.hidden = false;
			editPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
		});
		$("#cancel-inventory-edit").addEventListener("click", () => {
			editPanel.hidden = true;
			editForm.reset();
		});
		const reloadAdjustments = ui.createTable({
			tbody: $("#adjustments-table tbody"),
			columns: 7,
			emptyText: "No stock adjustments have been recorded.",
			load: async () => (await api.get("/api/inventory/adjustments")).items,
			renderRow: (a) => {
				const after = a.quantity_after !== null ? a.quantity_after : a.quantity_owned_after;
				return `<tr><td>${esc(a.item)}</td><td>${esc({ received: "Stock received", damaged: "Damaged write-off", lost: "Lost write-off", obsolete: "Obsolete write-off", manual: "Manual adjustment", issue: "Issued", return: "Returned" }[a.adjustment_type] || a.adjustment_type)}</td><td>${Number(a.quantity_change) > 0 ? "+" : ""}${esc(a.quantity_change)}</td><td>${after === null ? "—" : esc(after)}</td><td>${esc(a.reason)}</td><td>${esc(a.recorded_by)}</td><td>${esc(a.adjusted_at)}</td></tr>`;
			}
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
			payload: (v) => ({
				item_name: v.item_name.trim(),
				category: v.category,
				grade: v.grade,
				inventory_type: v.inventory_type,
				quantity: Number(v.quantity),
				reorder_level: Number(v.reorder_level),
				description: v.description.trim(),
				unit: v.unit.trim(),
				storage_location: v.storage_location.trim(),
				unit_price: v.unit_price === "" ? null : Number(v.unit_price)
			}),
			success: (data) => data.message,
			onSuccess: () => Promise.all([reload(), loadAdjustmentItems()])
		});
		ui.bindForm(editForm, {
			feedbackId: "inventory-edit-feedback",
			endpoint: (values) => `/api/inventory/${encodeURIComponent(values.item_id)}`,
			method: "PUT",
			busyText: "Saving…",
			payload: (v) => ({
				item_id: Number(v.item_id),
				item_name: v.item_name.trim(),
				category: v.category,
				grade: v.grade,
				inventory_type: v.inventory_type,
				reorder_level: Number(v.reorder_level),
				description: v.description.trim(),
				unit: v.unit.trim(),
				storage_location: v.storage_location.trim(),
				unit_price: v.unit_price === "" ? null : Number(v.unit_price)
			}),
			success: (data) => data.message,
			reset: false,
			onSuccess: async () => {
				await Promise.all([reload(), loadAdjustmentItems()]);
				editPanel.hidden = true;
				editForm.reset();
			}
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

	/* Allocation tracking: registered borrowers, outstanding issues, and linked movement history. */
	const movementForm = $("#movement-form");
	if (movementForm) {
		const itemSelect = $("#inventory-item");
		const borrowerSelect = $("#borrower-id");
		const loanSelect = $("#loan-id");
		const historySearch = $("#movement-history-search");
		const feedback = $("#movement-feedback");

		async function loadItems() {
			try {
				const { items } = await api.get("/api/inventory");
				ui.fillSelect(itemSelect, items, (item) => ({
					value: item.id,
					label: `${item.name} (${item.category === "Equipment" ? `${item.stock} available` : `${item.stock} in stock`})`
				}));
			} catch (error) {
				ui.showFeedback(feedback, "error", `Could not load inventory items. ${error.message}`);
			}
		}
		async function loadBorrowers() {
			try {
				const { items } = await api.get("/api/borrowers");
				ui.fillSelect(borrowerSelect, items, (borrower) => ({
					value: borrower.id,
					label: `${borrower.name} (${borrower.id}) · ${borrower.role === "staff" ? "Teacher" : "Learner"}`
				}));
			} catch (error) {
				ui.showFeedback(feedback, "error", `Could not load registered recipients. ${error.message}`);
			}
		}
		async function loadOutstandingLoans() {
			try {
				const { items } = await api.get("/api/loans");
				ui.fillSelect(loanSelect, items, (loan) => ({
					value: loan.id,
					label: `#${loan.id} · ${loan.borrower} · ${loan.item} · ${loan.quantity} outstanding (due ${loan.due || "not set"})`
				}));
			} catch (error) {
				ui.showFeedback(feedback, "error", `Could not load outstanding issues. ${error.message}`);
			}
		}
		const reloadLoans = ui.createTable({
			tbody: $("#loans-table tbody"),
			columns: 7,
			emptyText: "No items are currently on loan.",
			load: async () => (await api.get("/api/loans")).items,
			renderRow: (l) => `<tr><td>#${esc(l.id)}</td><td>${esc(l.borrower)}<br><small>${esc(l.borrower_id)}</small></td><td>${esc(l.item)}</td><td>${ui.formatDate(l.issued, false)}</td><td>${esc(l.quantity)}</td><td>${ui.formatDate(l.due, false)}</td><td>${ui.badge(l.status, l.tone)}</td></tr>`
		});
		const reloadHistory = ui.createTable({
			tbody: $("#movement-history-table tbody"),
			columns: 9,
			emptyText: "No allocation or retrieval history has been recorded.",
			load: async () => (await api.get("/api/movement-history", { q: historySearch.value.trim() })).items,
			renderRow: (event) => {
				const eventNames = { issue: "Issued", return: "Returned", lost: "Lost", damaged: "Damaged" };
				const linkedIssue = event.movement_type === "issue" ? `#${esc(event.id)}` : event.issue_id ? `#${esc(event.issue_id)}` : "Legacy / unlinked";
				const details = event.reason || (event.due ? `Due ${ui.formatDate(event.due, false)}` : "—");
				return `<tr><td>${esc(eventNames[event.movement_type] || event.movement_type)}</td><td>${linkedIssue}</td><td>${esc(event.borrower)}<br><small>${esc(event.borrower_id)}</small></td><td>${esc(event.item)}</td><td>${esc(event.quantity)}</td><td>${ui.formatDate(event.date, false)}${event.due ? `<br>Due ${ui.formatDate(event.due, false)}` : ""}</td><td>${esc(details)}</td><td>${esc(event.recorded_by)}</td><td>${esc(event.recorded_at)}</td></tr>`;
			}
		});
		let historySearchTimer;
		historySearch.addEventListener("input", () => {
			window.clearTimeout(historySearchTimer);
			historySearchTimer = window.setTimeout(reloadHistory, 250);
		});

		loadItems();
		loadBorrowers();
		loadOutstandingLoans();
		reloadLoans();
		reloadHistory();
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
				const body = {
					movement_type: v.movement_type,
					quantity: Number(v.quantity),
					movement_date: v.movement_date
				};
				if (v.movement_type === "issue") {
					body.item_id = Number(v.item);
					body.borrower_id = v.borrower_id;
					body.due_date = v.due_date;
				} else {
					body.loan_id = Number(v.loan_id);
					if (v.movement_type === "lost" || v.movement_type === "damaged") body.reason = v.reason.trim();
				}
				return body;
			},
			success: (data) => data.message,
			afterReset: () => {
				movementForm.elements["movement_date"].value = ui.todayISO();
				$("#movement-type").value = "issue";
				$("#movement-type").dispatchEvent(new Event("change"));
			},
			onSuccess: () => Promise.all([
				loadItems(), loadOutstandingLoans(), reloadLoans(), reloadHistory()
			])
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
