(function () {
	"use strict";

	const directory = "/static/images/inventory/";
	const categoryImages = {
		Textbooks: "mathematics-textbook.jpg",
		Stationery: "learner stationary pack.jpg",
		Consumables: "learner stationary pack.jpg",
		Equipment: "laptop-type A.webp",
		Other: "abacus.webp"
	};
	const resourceImages = [
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

	function imageFor(item) {
		const name = item.name.toLocaleLowerCase();
		const match = resourceImages.find(({ match: terms }) => terms.every((term) => name.includes(term)));
		const fallback = categoryImages[item.category] || categoryImages.Other;
		return {
			src: directory + encodeURIComponent(match ? match.file : fallback),
			fallback: directory + encodeURIComponent(fallback)
		};
	}

	document.addEventListener("error", (event) => {
		const image = event.target;
		if (!(image instanceof HTMLImageElement) || !image.dataset.imageFallback) return;
		const fallback = image.dataset.imageFallback;
		delete image.dataset.imageFallback;
		if (image.src !== new URL(fallback, window.location.href).href) image.src = fallback;
	}, true);

	window.LTSMResourceImages = { imageFor };
})();
