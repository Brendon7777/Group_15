(function () {
	"use strict";
	const { api, ui } = window.LTSM;
	const $ = (selector) => document.querySelector(selector);
	const esc = ui.escape;
	const metrics = new Map([
		["requests_submitted", { label: "Requests submitted", unit: "requests", kind: "count" }],
		["request_waiting", { label: "Average time to ready", unit: "minutes", kind: "duration" }],
		["collection_waiting", { label: "Average time from ready to collection", unit: "minutes", kind: "duration" }],
		["request_fulfillment", { label: "Average request-to-fulfillment time", unit: "minutes", kind: "duration" }],
		["bookings_requested", { label: "Bookings submitted", unit: "bookings", kind: "count" }],
		["booking_conflicts", { label: "Booking conflict rate", unit: "percent", kind: "rate" }]
	]);
	const periodForm = $("#evidence-period-form");
	if (!periodForm) return;

	const feedback = $("#evidence-feedback");
	const today = ui.todayISO();
	const fromDate = new Date(`${today}T00:00:00`);
	fromDate.setDate(fromDate.getDate() - 29);
	const isoDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
	periodForm.elements.from.value = isoDate(fromDate);
	periodForm.elements.to.value = today;

	function formatValue(value, unit) {
		if (value === null || value === undefined) return "No data";
		const rounded = Number(value).toLocaleString("en-GB", { maximumFractionDigits: 2 });
		if (unit === "minutes") return `${rounded} min`;
		if (unit === "percent") return `${rounded}%`;
		return `${rounded} ${unit}`;
	}

	function formatChange(item) {
		if (item.change === null || item.change === undefined) {
			if (item.previous_value === null && item.current_value !== null) return "No prior data to compare";
			if (item.previous_value === 0 && item.current_value > 0) return "New activity (previously 0)";
			return "Not enough data to compare";
		}
		if (item.kind === "count") {
			if (item.change === 0) return "No change";
			const sign = item.change > 0 ? "+" : "−";
			return `${sign}${Math.abs(item.change)} ${item.unit} vs previous`;
		}
		if (item.change === 0) return "No change";
		return `${Math.abs(item.change)}% ${item.change < 0 ? "lower" : "higher"} vs previous`;
	}

	function hideLatestSummary() {
		const summary = $("#evidence-trend-latest");
		if (summary) summary.hidden = true;
	}

	function renderEvidence(data) {
		$("#evidence-period-note").textContent =
			`Selected period: ${ui.formatDate(data.period_start)}–${ui.formatDate(data.period_end)}. Compared with ${ui.formatDate(data.previous_period_start)}–${ui.formatDate(data.previous_period_end)}.`;
		$("#evidence-table-body").innerHTML = data.items.map((item) => {
			const previous = item.previous_value === null
				? "No data"
				: formatValue(item.previous_value, item.unit);
			const current = formatValue(item.current_value, item.unit);
			const previousSample = `${item.previous_sample_count} ${item.kind === "count" ? "events" : item.kind === "rate" ? "attempts" : "completed requests"}`;
			const currentSample = `${item.current_sample_count} ${item.kind === "count" ? "events" : item.kind === "rate" ? "attempts" : "completed requests"}`;
			return `<tr>
				<th scope="row">${esc(item.label)}</th>
				<td>${esc(previous)}<small>${esc(previousSample)}</small></td>
				<td>${esc(current)}<small>${esc(currentSample)}</small></td>
				<td><span class="evidence-change">${esc(formatChange(item))}</span><a class="button button-small evidence-trend-button" href="#evidence-trend-chart" aria-label="View line graph for ${esc(item.label)}" data-metric-key="${esc(item.key)}">View line graph</a></td>
			</tr>`;
		}).join("");
	}

	async function loadEvidence() {
		ui.hideFeedback(feedback);
		$("#evidence-table-body").innerHTML = '<tr><td colspan="4">Loading KPIs…</td></tr>';
		try {
			const data = await api.get("/api/evidence/automatic", {
				from: periodForm.elements.from.value,
				to: periodForm.elements.to.value
			});
			renderEvidence(data);
			$("#evidence-trend").innerHTML = '<p class="evidence-chart-empty">Choose “View line graph” beside a KPI to see its daily trend.</p>';
			$("#evidence-trend-title").textContent = "KPI line graph";
			hideLatestSummary();
		} catch (error) {
			$("#evidence-table-body").innerHTML = `<tr><td colspan="4">${esc(error.message)}</td></tr>`;
			ui.showFeedback(feedback, "error", `Could not load automatic KPIs. ${error.message}`);
		}
	}

	function svgElement(name, attributes) {
		const element = document.createElementNS("http://www.w3.org/2000/svg", name);
		for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
		return element;
	}

	function chartAxisMaximum(value, unit) {
		if (unit === "percent") return 100;
		if (value <= 0) return 1;
		const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
		const normalized = value / magnitude;
		const factor = [1, 2, 2.5, 5, 10].find((candidate) => candidate >= normalized) || 10;
		return factor * magnitude;
	}

	function shortDate(value) {
		return new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {
			day: "2-digit",
			month: "short"
		});
	}

	function renderTrend(data) {
		const container = $("#evidence-trend");
		$("#evidence-trend-title").textContent = data.label;
		const latestSummary = $("#evidence-trend-latest");
		container.replaceChildren();
		if (latestSummary) latestSummary.hidden = true;
		if (!data.points.length) {
			const empty = document.createElement("p");
			empty.className = "evidence-chart-empty";
			empty.textContent = "No recorded events for this KPI in the selected period.";
			container.append(empty);
			return;
		}

		const width = 920;
		const height = 370;
		const margin = { top: 20, right: 28, bottom: 48, left: 84 };
		const plotWidth = width - margin.left - margin.right;
		const plotHeight = height - margin.top - margin.bottom;
		const values = data.points.map((point) => Number(point.value));
		const maxValue = chartAxisMaximum(Math.max(...values), data.unit);
		const rangeStart = new Date(`${data.period_start}T00:00:00`).getTime();
		const rangeEnd = new Date(`${data.period_end}T00:00:00`).getTime();
		const rangeLength = rangeEnd - rangeStart;
		const x = (value) => margin.left + (
			rangeLength === 0
				? plotWidth / 2
				: ((new Date(`${value}T00:00:00`).getTime() - rangeStart) / rangeLength) * plotWidth
		);
		const y = (value) => margin.top + plotHeight - (Number(value) / maxValue) * plotHeight;
		const svg = svgElement("svg", {
			class: "evidence-line-chart",
			viewBox: `0 0 ${width} ${height}`,
			role: "img",
			"aria-label": `${data.label} daily line graph, ${data.points.length} observations from ${ui.formatDate(data.period_start)} to ${ui.formatDate(data.period_end)}`
		});
		const title = svgElement("title", {});
		title.textContent = `${data.label} by day`;
		svg.append(title);
		const definitions = svgElement("defs", {});
		const areaGradient = svgElement("linearGradient", {
			id: "evidence-area-gradient", x1: "0", x2: "0", y1: "0", y2: "1"
		});
		areaGradient.append(svgElement("stop", { offset: "0%", "stop-color": "#0b9678", "stop-opacity": ".24" }));
		areaGradient.append(svgElement("stop", { offset: "100%", "stop-color": "#0b9678", "stop-opacity": ".015" }));
		const lineGradient = svgElement("linearGradient", {
			id: "evidence-line-gradient", x1: "0", x2: "1", y1: "0", y2: "0"
		});
		lineGradient.append(svgElement("stop", { offset: "0%", "stop-color": "#035e82" }));
		lineGradient.append(svgElement("stop", { offset: "100%", "stop-color": "#0daa88" }));
		definitions.append(areaGradient, lineGradient);
		svg.append(definitions);

		for (let tick = 0; tick <= 4; tick += 1) {
			const tickValue = maxValue * tick / 4;
			const tickY = y(tickValue);
			svg.append(svgElement("line", {
				x1: margin.left, y1: tickY, x2: width - margin.right, y2: tickY,
				class: "evidence-chart-gridline", stroke: "#e7efed", "stroke-width": "1"
			}));
			const label = svgElement("text", {
				x: margin.left - 12, y: tickY + 4, "text-anchor": "end",
				class: "evidence-chart-axis", fill: "#73847f", "font-size": "12"
			});
			const axisValue = Number(tickValue.toPrecision(3)).toLocaleString("en-GB", { maximumFractionDigits: 2 });
			label.textContent = data.unit === "percent" ? `${axisValue}%`
				: data.unit === "minutes" ? `${axisValue} min`
					: axisValue;
			svg.append(label);
		}

		const points = data.points.map((point) => ({
			x: x(point.date),
			y: y(point.value),
			point
		}));
		if (points.length > 1) {
			const linePath = points.map((point, index) =>
				`${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
			).join(" ");
			const baselineY = margin.top + plotHeight;
			const areaPath = `${linePath} L ${points[points.length - 1].x} ${baselineY} L ${points[0].x} ${baselineY} Z`;
			svg.append(svgElement("path", {
				d: areaPath, class: "evidence-chart-area", fill: "url(#evidence-area-gradient)"
			}));
			svg.append(svgElement("path", {
				d: linePath, class: "evidence-chart-line", fill: "none",
				stroke: "url(#evidence-line-gradient)", "stroke-width": "3.5",
				"stroke-linecap": "round", "stroke-linejoin": "round"
			}));
		}
		for (const { x: pointX, y: pointY, point } of points) {
			const circle = svgElement("circle", {
				cx: pointX, cy: pointY, r: "5", class: "evidence-chart-point",
				fill: "#fff", stroke: "#087c68", "stroke-width": "3",
				tabindex: "0",
				"aria-label": `${ui.formatDate(point.date)}: ${formatValue(point.value, data.unit)}, sample size ${point.sample_count}`
			});
			const description = svgElement("title", {});
			description.textContent = `${ui.formatDate(point.date)}: ${formatValue(point.value, data.unit)} (n=${point.sample_count})`;
			circle.append(description);
			svg.append(circle);
		}
		svg.append(svgElement("line", {
			x1: margin.left, y1: margin.top + plotHeight,
			x2: width - margin.right, y2: margin.top + plotHeight,
			stroke: "#cbd9d6", "stroke-width": "1.25"
		}));
		const dateTicks = [...new Set([0, .5, 1].map((fraction) => {
			const tickDate = new Date(rangeStart + rangeLength * fraction);
			return `${tickDate.getFullYear()}-${String(tickDate.getMonth() + 1).padStart(2, "0")}-${String(tickDate.getDate()).padStart(2, "0")}`;
		}))];
		for (const tickDateValue of dateTicks) {
			const tickDate = new Date(`${tickDateValue}T00:00:00`);
			const fraction = rangeLength === 0 ? .5 : (tickDate.getTime() - rangeStart) / rangeLength;
			const label = svgElement("text", {
				x: margin.left + plotWidth * fraction, y: height - 14,
				"text-anchor": fraction === 0 ? "start" : fraction === 1 ? "end" : "middle",
				class: "evidence-chart-axis", fill: "#73847f", "font-size": "12"
			});
			label.textContent = shortDate(tickDateValue);
			svg.append(label);
		}
		container.append(svg);
		const note = document.createElement("p");
		note.textContent = `${data.sample_count} records represented. Values show daily ${data.kind === "count" ? "event totals" : data.kind === "rate" ? "booking conflict rates" : "average completion times"}. Focus or hover over a point for its exact value and sample size.`;
		container.append(note);
		const latest = data.points[data.points.length - 1];
		if (latestSummary) {
			latestSummary.hidden = false;
			const latestLabel = document.createElement("span");
			latestLabel.textContent = "Latest daily value";
			const latestValue = document.createElement("strong");
			latestValue.textContent = formatValue(latest.value, data.unit);
			const latestDate = document.createElement("small");
			latestDate.textContent = `${ui.formatDate(latest.date)} · n=${latest.sample_count}`;
			latestSummary.replaceChildren(latestLabel, latestValue, latestDate);
		}
	}

	async function loadTrend(metricKey) {
		const metric = metrics.get(metricKey);
		if (!metric) return;
		const container = $("#evidence-trend");
		container.innerHTML = '<p class="evidence-chart-empty">Loading line graph…</p>';
		$("#evidence-trend-title").textContent = `${metric.label} line graph`;
		hideLatestSummary();
		try {
			const data = await api.get("/api/evidence/trends", {
				metric: metricKey,
				from: periodForm.elements.from.value,
				to: periodForm.elements.to.value
			});
			renderTrend(data);
			$("#evidence-trend-chart").scrollIntoView({ behavior: "smooth", block: "start" });
		} catch (error) {
			container.textContent = `Could not load this line graph. ${error.message}`;
			ui.showFeedback(feedback, "error", `Could not load KPI trend. ${error.message}`);
		}
	}

	periodForm.addEventListener("submit", (event) => {
		event.preventDefault();
		if (periodForm.elements.from.value > periodForm.elements.to.value) {
			ui.showFeedback(feedback, "error", "The start date must be on or before the end date.");
			return;
		}
		loadEvidence();
	});

	$("#evidence-table-body").addEventListener("click", (event) => {
		const link = event.target.closest("[data-metric-key]");
		if (!link) return;
		event.preventDefault();
		loadTrend(link.dataset.metricKey);
	});

	loadEvidence();
})();
