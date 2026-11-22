(function () {
	"use strict";

	const overlay = document.querySelector(".page-loading");
	if (!overlay) return;

	function showLoader() {
		overlay.hidden = false;
	}

	function hideLoader() {
		overlay.hidden = true;
	}

	if (document.readyState === "complete") {
		hideLoader();
	} else {
		showLoader();
		window.addEventListener("load", hideLoader, { once: true });
	}

	document.addEventListener("click", (event) => {
		if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
		const link = event.target.closest("a[href]");
		if (!link || link.hasAttribute("download") || link.target && link.target !== "_self" || link.dataset.noTransition !== undefined) return;

		const destination = new URL(link.href, window.location.href);
		if (
			destination.origin !== window.location.origin
			|| (destination.pathname === window.location.pathname && destination.search === window.location.search)
		) return;

		event.preventDefault();
		showLoader();
		window.setTimeout(() => window.location.assign(destination.href), 80);
	});

	window.addEventListener("pageshow", (event) => {
		if (event.persisted) hideLoader();
	});
})();
