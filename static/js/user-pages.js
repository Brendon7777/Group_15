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
		const CATEGORY_IMAGES = {
			Textbooks: "mathematics-textbook.jpg",
			Stationery: "learner stationary pack.jpg",
			Equipment: "laptop-type A.webp",
			Other: "abacus.webp"
		};
		const RESOURCE_IMAGES = [
			{ match: ["natural sciences"], file: "grade 8 -  natural sciences textbook.webp" },
			{ match: ["grade 3", "mathematics workbook"], file: "grade 3- Mathematics workbook.jpg" },
			{ match: ["grade 2", "english workbook"], file: "Grade 2-English workbook.jpg" },
			{ match: ["mathematics"], file: "mathematics-textbook.jpg" },
			{ match: ["whiteboard marker", "white-board marker"], file: "white-board markers.jpg" },
			{ match: ["printer ink", "ink cartridge"], file: "printer ink-catridges.jpg" },
			{ match: ["stationery pack"], file: "learner stationary pack.jpg" },
			{ match: ["exercise book"], file: "A4-exercise book.jpg" },
			{ match: ["geometry set"], file: "geometry-set.jpg" },
			{ match: ["projector"], file: "classroom-projector.webp" },
			{ match: ["tablet"], file: "tablet.jpg" },
			{ match: ["speaker"], file: "portable-speaker.webp" },
			{ match: ["camera"], file: "usb-camera.webp" },
			{ match: ["laptop"], file: "laptop-type A.webp" },
			{ match: ["printer"], file: "printer-a.webp" },
			{ match: ["abacus"], file: "abacus.webp" },
			{ match: ["clock"], file: "teaching-clock.webp" }
		];
		const imageFor = (item) => {
			const name = item.name.toLowerCase();
			const match = RESOURCE_IMAGES.find(({ match: terms }) => terms.every((term) => name.includes(term)));
			return match?.file || CATEGORY_IMAGES[item.category];
		};
		const reload = ui.createTable({
			tbody: resourceBody,
			columns: 5,
			emptyText: "No resources match your search. Try another keyword or category.",
			load: async () => (await api.get("/api/resources", { q: search.value, category: category.value })).items,
			renderRow: (item) => {
				const image = imageFor(item);
				const visual = image
					? `<img class="catalogue-item__image" src="/static/images/inventory/${encodeURIComponent(image)}" alt="${esc(item.name)}">`
					: `<span class="catalogue-item__icon" aria-hidden="true">${ICONS[item.category] || "▤"}</span>`;
				const action = item.category === "Equipment"
					? `<a class="catalogue-action" href="/book-equipment.html?equipment_id=${encodeURIComponent(item.id)}">Book</a>`
					: `<a class="catalogue-action" href="/request-resources.html?resource_name=${encodeURIComponent(item.name)}">Request</a>`;
				return `<tr><td><div class="catalogue-item">${visual}<span><span class="catalogue-item__name">${esc(item.name)}</span><span class="catalogue-item__description">${esc(item.description)}</span></span></div></td><td><span class="badge catalogue-category">${esc(item.category)}</span></td><td>${ui.badge(item.availability, item.tone)}</td><td><span class="catalogue-count">${esc(item.stock)}</span><span class="sr-only"> ${esc(item.unit)} available</span></td><td>${action}</td></tr>`;
			}
		});
		search.addEventListener("input", ui.debounce(reload));
		category.addEventListener("change", reload);
		reload();
	}

	/* Request a resource: GET /api/resources (suggestions) and POST /api/requests */
	const requestForm = $("#request-form");
	if (requestForm) {
		const suggestions = $("#catalogue-items");
		const resourceName = $("#resource-name");
		const requestCategory = $("#category");
		const quantityInput = $("#quantity");
		const availabilityNote = $("#available-quantity");
		const requestedResourceName = new URLSearchParams(window.location.search).get("resource_name");
		if (requestedResourceName) resourceName.value = requestedResourceName;
		const resourceCatalog = new Map();
		const validCategories = new Set(Array.from(requestCategory.options).filter((option) => !option.disabled).map((option) => option.value));
		const matchingResource = () => resourceCatalog.get(resourceName.value.trim().toLocaleLowerCase());
		const updateRequestCategory = () => {
			const name = resourceName.value.trim();
			const item = matchingResource();
			requestCategory.value = !name ? "" : validCategories.has(item?.category) ? item.category : "Other";
			availabilityNote.textContent = item
				? `Available now: ${item.stock} ${item.unit} for this request.`
				: name ? "Availability is not listed for this item." : "Enter a product name to check current availability.";
		};

		resourceName.addEventListener("input", updateRequestCategory);
		resourceName.addEventListener("change", updateRequestCategory);
		quantityInput.addEventListener("input", () => {
			const item = matchingResource();
			if (item && Number(quantityInput.value) > item.stock) {
				availabilityNote.textContent = `Only ${item.stock} ${item.unit} available. Reduce the requested quantity to continue.`;
			} else {
				updateRequestCategory();
			}
		});
		if (suggestions) {
			api.get("/api/resources")
				.then(({ items }) => {
					items.forEach((item) => resourceCatalog.set(item.name.trim().toLocaleLowerCase(), item));
					suggestions.innerHTML = items.map((item) => `<option value="${esc(item.name)}">`).join("");
					updateRequestCategory();
				})
				.catch(() => {
					availabilityNote.textContent = "Could not load current availability. Stock will be checked when you submit.";
				});
		}
		ui.bindForm(requestForm, {
			feedbackId: "request-feedback",
			endpoint: "/api/requests",
			busyText: "Submitting…",
			beforeSubmit: () => {
				const item = matchingResource();
				if (item && Number(quantityInput.value) > item.stock) {
					ui.showFeedback($("#request-feedback"), "error", `Only ${item.stock} ${item.unit} of ${item.name} are currently available. Reduce the quantity before submitting.`);
					quantityInput.focus();
					return false;
				}
				return true;
			},
			payload: (v) => ({ resource_name: v.resource_name.trim(), category: v.category, quantity: Number(v.quantity), needed_by: v.needed_by, purpose: v.purpose.trim() }),
			success: () => "Request submitted. The LTSM committee will review it – track its progress on My requests."
		});
	}

	const suggestionForm = $("#suggestion-form");
	if (suggestionForm) {
		const anonymous = $("#suggestion-anonymous");
		const nameField = $("#suggestion-name-field");
		const submitterName = $("#submitter-name");
		const updateAnonymousFields = () => {
			const userIsSignedIn = document.body.dataset.userSignedIn === "true";
			const needsName = !anonymous.checked && !userIsSignedIn;
			nameField.hidden = !needsName;
			submitterName.required = needsName;
		};
		anonymous.addEventListener("change", updateAnonymousFields);
		updateAnonymousFields();
		ui.bindForm(suggestionForm, {
			feedbackId: "suggestion-feedback",
			endpoint: "/api/suggestions",
			busyText: "Sending…",
			payload: (values) => ({
				resource_name: values.resource_name.trim(),
				message: values.message.trim(),
				anonymous: values.anonymous === "on",
				submitter_name: values.submitter_name.trim()
			}),
			success: (data) => data.message,
			afterReset: updateAnonymousFields
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
				const requestedEquipmentId = new URLSearchParams(window.location.search).get("equipment_id");
				if (requestedEquipmentId && items.some((item) => String(item.id) === requestedEquipmentId)) {
					equipmentSelect.value = requestedEquipmentId;
				}
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
