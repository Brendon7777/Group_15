/* Keep the South Africa 24-hour clock visible in the shared portal header. */
(function () {
	"use strict";

	const clock = document.querySelector("[data-live-clock]");
	if (!clock) return;

	const formatter = new Intl.DateTimeFormat("en-GB", {
		timeZone: "Africa/Johannesburg",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
		hourCycle: "h23"
	});

	const update = () => {
		const now = new Date();
		clock.textContent = formatter.format(now);
		clock.dateTime = now.toISOString();
	};

	update();
	window.setInterval(update, 1000);
})();
