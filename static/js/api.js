/*
 * LTSM Portal – shared fetch() helpers (Task 3A).
 * Loaded on every page (base.html, login.html, register.html). Exposes window.LTSM = { api, ui }.
 * Every call goes to the Flask JSON API under /api – see API_CONTRACT.md.
 */
(function () {
	"use strict";

	/* ---------- API client ---------- */
	class ApiError extends Error {
		constructor(message, status, fields) {
			super(message);
			this.name = "ApiError";
			this.status = status;
			this.fields = fields || {};
		}
	}

	async function request(method, url, body) {
		const options = { method, credentials: "same-origin", headers: { Accept: "application/json" } };
		if (body !== undefined) {
			options.headers["Content-Type"] = "application/json";
			options.body = JSON.stringify(body);
		}

		let response;
		try {
			response = await fetch(url, options);
		} catch (networkError) {
			throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
		}

		let payload = null;
		try { payload = await response.json(); } catch (parseError) { /* empty or non-JSON body */ }

		if (!response.ok) {
			// An expired session sends the user back to sign in; a wrong password on the login call does not.
			if (response.status === 401 && url !== "/api/login") window.location.assign("/login");
			throw new ApiError((payload && payload.error) || `Something went wrong (error ${response.status}).`, response.status, payload && payload.fields);
		}
		return payload;
	}

	function withQuery(url, params) {
		const query = new URLSearchParams();
		for (const [key, value] of Object.entries(params || {})) {
			if (value !== undefined && value !== null && String(value).trim() !== "") query.set(key, String(value).trim());
		}
		const text = query.toString();
		return text ? `${url}?${text}` : url;
	}

	const api = {
		ApiError,
		get: (url, params) => request("GET", withQuery(url, params)),
		post: (url, body) => request("POST", url, body === undefined ? {} : body),
		put: (url, body) => request("PUT", url, body === undefined ? {} : body)
	};

	/* ---------- UI helpers ---------- */
	const ui = {};
	const TONES = { ok: "", warning: " badge--warning", danger: " badge--danger", blue: " badge--blue" };

	ui.escape = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
	ui.badgeClass = (tone) => `badge${TONES[tone] || ""}`;
	ui.badge = (text, tone) => `<span class="${ui.badgeClass(tone)}">${ui.escape(text)}</span>`;
	ui.todayISO = () => { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
	ui.formatDate = (iso, withYear = true) => {
		const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
		if (!match) return ui.escape(iso);
		return new Date(+match[1], +match[2] - 1, +match[3]).toLocaleDateString("en-GB", withYear ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });
	};
	ui.debounce = (fn, wait = 250) => {
		let timer;
		return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); };
	};

	ui.showFeedback = (element, kind, message) => {
		if (!element) return;
		element.className = `form-feedback form-feedback--${kind}`;
		element.setAttribute("role", kind === "error" ? "alert" : "status");
		element.textContent = message;
		element.hidden = false;
		element.scrollIntoView({ behavior: "smooth", block: "nearest" });
	};
	ui.hideFeedback = (element) => { if (element) { element.hidden = true; element.textContent = ""; } };

	ui.setBusy = (button, busy, busyText) => {
		if (!button) return;
		if (busy) {
			button.dataset.label = button.textContent;
			button.textContent = busyText || "Saving…";
			button.disabled = true;
			button.setAttribute("aria-busy", "true");
		} else {
			if (button.dataset.label) button.textContent = button.dataset.label;
			button.disabled = false;
			button.removeAttribute("aria-busy");
		}
	};

	ui.markInvalid = (form, fields) => {
		for (const name of Object.keys(fields || {})) {
			const control = form.elements[name];
			if (control && control.setAttribute) {
				control.setAttribute("aria-invalid", "true");
				control.addEventListener("input", () => control.removeAttribute("aria-invalid"), { once: true });
			}
		}
	};
	ui.clearInvalid = (form) => form.querySelectorAll("[aria-invalid]").forEach((control) => control.removeAttribute("aria-invalid"));

	/* Replace a <select>'s options with API data, keeping the disabled "Select …" prompt. */
	ui.fillSelect = (select, items, toOption) => {
		const prompt = select.querySelector("option[disabled]");
		select.innerHTML = "";
		if (prompt) select.append(prompt);
		for (const item of items) {
			const { value, label } = toOption(item);
			const option = document.createElement("option");
			option.value = value;
			option.textContent = label;
			select.append(option);
		}
	};

	/*
	 * Fill a <tbody> from the API. Shows a loading row, then the rows, an empty-state row, or an error row with a retry button.
	 * Returns reload(); responses that arrive out of order are ignored.
	 */
	/* One full-width message row inside a <tbody>: kind is "loading", "empty" or "error"; html must already be escaped. */
	ui.rowMessage = (tbody, columns, kind, html) => { tbody.innerHTML = `<tr class="state-row state-row--${kind}"><td colspan="${columns}">${html}</td></tr>`; };

	/* Show rows, or the empty-state row when there are none. */
	ui.setRows = (tbody, columns, items, renderRow, emptyText) => {
		if (items.length) tbody.innerHTML = items.map(renderRow).join("");
		else ui.rowMessage(tbody, columns, "empty", ui.escape(emptyText));
	};

	ui.createTable = ({ tbody, columns, load, renderRow, emptyText, retry }) => {
		let latest = 0;
		const showRow = (kind, html) => ui.rowMessage(tbody, columns, kind, html);

		async function reload() {
			const ticket = ++latest;
			tbody.setAttribute("aria-busy", "true");
			showRow("loading", "Loading…");
			try {
				const items = await load();
				if (ticket !== latest) return;
				ui.setRows(tbody, columns, items, renderRow, typeof emptyText === "function" ? emptyText() : emptyText);
			} catch (error) {
				if (ticket !== latest) return;
				showRow("error", `${ui.escape(error.message)} <button type="button" class="state-retry">Try again</button>`);
				tbody.querySelector(".state-retry").addEventListener("click", retry || reload);
			} finally {
				if (ticket === latest) tbody.removeAttribute("aria-busy");
			}
		}
		return reload;
	};

	/*
	 * Turn a <form> into a fetch() POST.
	 * options: feedbackId, endpoint, payload(values, form), success(data), busyText, beforeSubmit(), onSuccess(data), reset (default true), afterReset().
	 */
	ui.bindForm = (form, options) => {
		const feedback = document.getElementById(options.feedbackId);
		const button = form.querySelector('button[type="submit"]');

		form.addEventListener("submit", async (event) => {
			event.preventDefault();
			if (options.beforeSubmit && options.beforeSubmit() === false) return;
			if (!form.reportValidity()) return;
			ui.hideFeedback(feedback);
			ui.clearInvalid(form);
			ui.setBusy(button, true, options.busyText);
			try {
				const values = Object.fromEntries(new FormData(form));
				const endpoint = typeof options.endpoint === "function" ? options.endpoint(values, form) : options.endpoint;
				const payload = options.payload(values, form);
				const data = options.method === "PUT"
					? await api.put(endpoint, payload)
					: await api.post(endpoint, payload);
				ui.showFeedback(feedback, "success", options.success ? options.success(data) : (data.message || "Saved."));
				if (options.reset !== false) {
					form.reset();
					if (options.afterReset) options.afterReset();
				}
				if (options.onSuccess) await options.onSuccess(data);
			} catch (error) {
				ui.showFeedback(feedback, "error", error.message);
				ui.markInvalid(form, error.fields);
			} finally {
				ui.setBusy(button, false);
			}
		});
	};

	/* Any link marked data-signout ends the server session first. */
	document.addEventListener("click", async (event) => {
		const link = event.target.closest("[data-signout]");
		if (!link) return;
		event.preventDefault();
		try { await api.post("/api/logout"); } catch (error) { /* leave anyway */ }
		window.location.assign("/login");
	});

	window.LTSM = { api, ui };
})();
