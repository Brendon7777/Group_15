/* Rearrange dashboard tiles with drag and drop or keyboard arrows. */
(function () {
	"use strict";

	const controls = document.querySelector("[data-dashboard-layout-controls]");
	const toggleButton = controls?.querySelector("[data-layout-toggle]");
	const resetButton = controls?.querySelector("[data-layout-reset]");
	const status = controls?.querySelector("[data-layout-status]");
	const grids = Array.from(document.querySelectorAll("[data-reorderable-grid]"));
	if (!controls || !toggleButton || !resetButton || !status || !grids.length) return;

	const userId = document.body.dataset.dashboardUser || "shared";
	const states = grids.map((grid) => {
		const tiles = Array.from(grid.children).filter((child) => child.hasAttribute("data-dashboard-tile"));
		const originalTabIndex = new Map(tiles.map((tile) => [
			tile,
			tile.hasAttribute("tabindex") ? tile.getAttribute("tabindex") : null
		]));
		return {
			grid,
			key: `ltsm-dashboard-layout:v1:${userId}:${grid.dataset.reorderableGrid}`,
			originalOrder: tiles.map((tile) => tile.dataset.dashboardTile),
			originalTabIndex,
			draggedTile: null,
			dragStartOrder: null,
			dropTarget: null
		};
	});

	let rearranging = false;
	let suppressClickUntil = 0;
	let storageUnavailable = false;

	function announce(message) {
		status.textContent = message;
	}

	function reportStorageFailure() {
		storageUnavailable = true;
		announce("This browser could not save the layout. Changes will last until you leave this page.");
	}

	function orderedTiles(state) {
		return Array.from(state.grid.children).filter((child) => child.hasAttribute("data-dashboard-tile"));
	}

	function tileTitle(tile) {
		return tile.querySelector(".stat-label, h3")?.textContent.trim() || "Dashboard tile";
	}

	function moveTileToOrder(state, order) {
		const tilesById = new Map(orderedTiles(state).map((tile) => [tile.dataset.dashboardTile, tile]));
		const seen = new Set();
		for (const tileId of order) {
			const tile = tilesById.get(tileId);
			if (tile && !seen.has(tileId)) {
				state.grid.appendChild(tile);
				seen.add(tileId);
			}
		}
		for (const tileId of state.originalOrder) {
			if (!seen.has(tileId)) state.grid.appendChild(tilesById.get(tileId));
		}
	}

	function saveOrder(state) {
		try {
			window.localStorage.setItem(
				state.key,
				JSON.stringify(orderedTiles(state).map((tile) => tile.dataset.dashboardTile))
			);
			return true;
		} catch (error) {
			reportStorageFailure();
			return false;
		}
	}

	function restoreSavedOrder(state) {
		try {
			const saved = window.localStorage.getItem(state.key);
			if (!saved) return false;
			let order;
			try {
				order = JSON.parse(saved);
			} catch (error) {
				announce("A saved tile arrangement could not be read; the default order is shown.");
				return false;
			}
			if (!Array.isArray(order) || order.some((tileId) => typeof tileId !== "string")) {
				announce("A saved tile arrangement was invalid; the default order is shown.");
				return false;
			}
			moveTileToOrder(state, order);
			return true;
		} catch (error) {
			reportStorageFailure();
			return false;
		}
	}

	function setRearranging(active) {
		rearranging = active;
		document.body.classList.toggle("dashboard-layout-rearranging", active);
		toggleButton.textContent = active ? "Done rearranging" : "Rearrange tiles";
		resetButton.hidden = !active;
		for (const state of states) {
			for (const tile of orderedTiles(state)) {
				tile.draggable = active;
				tile.classList.toggle("dashboard-tile--rearranging", active);
				if (active) {
					tile.tabIndex = 0;
					tile.setAttribute("aria-keyshortcuts", "ArrowUp ArrowDown Home End");
				} else {
					const previousTabIndex = state.originalTabIndex.get(tile);
					if (previousTabIndex === null) tile.removeAttribute("tabindex");
					else tile.setAttribute("tabindex", previousTabIndex);
					tile.removeAttribute("aria-keyshortcuts");
				}
			}
		}
		announce(active
			? "Drag tiles within their group, or focus a tile and use the Up and Down arrow keys."
			: storageUnavailable ? "Layout changes could not be saved in this browser." : "Rearranging is off.");
	}

	for (const state of states) {
		for (const tile of orderedTiles(state)) {
			const grip = document.createElement("span");
			grip.className = "dashboard-tile-grip";
			grip.setAttribute("aria-hidden", "true");
			grip.textContent = "⠿";
			tile.appendChild(grip);
		}
		restoreSavedOrder(state);

		state.grid.addEventListener("dragstart", (event) => {
			const tile = event.target.closest("[data-dashboard-tile]");
			if (!rearranging || !tile || tile.parentElement !== state.grid) {
				event.preventDefault();
				return;
			}
			state.draggedTile = tile;
			state.dragStartOrder = orderedTiles(state).map((item) => item.dataset.dashboardTile);
			tile.classList.add("dashboard-tile--dragging");
			event.dataTransfer.effectAllowed = "move";
			event.dataTransfer.setData("text/plain", tile.dataset.dashboardTile);
			announce(`Moving ${tileTitle(tile)}. Drop it in the new position.`);
		});

		state.grid.addEventListener("dragover", (event) => {
			const target = event.target.closest("[data-dashboard-tile]");
			if (!rearranging || !state.draggedTile || !target || target === state.draggedTile) return;
			event.preventDefault();
			event.dataTransfer.dropEffect = "move";
			if (state.dropTarget !== target) {
				state.dropTarget?.classList.remove("dashboard-tile--drop-target");
				state.dropTarget = target;
				target.classList.add("dashboard-tile--drop-target");
			}
			const bounds = target.getBoundingClientRect();
			const horizontal = Math.abs(event.clientX - (bounds.left + bounds.width / 2))
				> Math.abs(event.clientY - (bounds.top + bounds.height / 2));
			const before = horizontal
				? event.clientX < bounds.left + bounds.width / 2
				: event.clientY < bounds.top + bounds.height / 2;
			const reference = before ? target : target.nextElementSibling;
			if (reference !== state.draggedTile) state.grid.insertBefore(state.draggedTile, reference);
		});

		state.grid.addEventListener("drop", (event) => {
			if (!state.draggedTile) return;
			event.preventDefault();
		});

		state.grid.addEventListener("dragend", () => {
			const moved = state.dragStartOrder
				&& state.dragStartOrder.some((tileId, index) => tileId !== orderedTiles(state)[index]?.dataset.dashboardTile);
			state.draggedTile?.classList.remove("dashboard-tile--dragging");
			state.dropTarget?.classList.remove("dashboard-tile--drop-target");
			state.draggedTile = null;
			state.dropTarget = null;
			state.dragStartOrder = null;
			if (moved) {
				suppressClickUntil = Date.now() + 300;
				if (saveOrder(state)) announce("Tile order saved for this account in this browser.");
			}
		});

		state.grid.addEventListener("keydown", (event) => {
			if (!rearranging) return;
			const tile = event.target.closest("[data-dashboard-tile]");
			if (!tile || tile.parentElement !== state.grid) return;
			const tiles = orderedTiles(state);
			const index = tiles.indexOf(tile);
			let reference = null;
			if (event.key === "ArrowUp" && index > 0) reference = tiles[index - 1];
			else if (event.key === "ArrowDown" && index < tiles.length - 1) reference = tiles[index + 2] || null;
			else if (event.key === "Home" && index > 0) reference = tiles[0];
			else if (event.key === "End" && index < tiles.length - 1) reference = null;
			else return;
			event.preventDefault();
			if (event.key === "ArrowDown") state.grid.insertBefore(tile, reference);
			else if (event.key === "End") state.grid.appendChild(tile);
			else state.grid.insertBefore(tile, reference);
			tile.focus();
			if (saveOrder(state)) {
				const position = orderedTiles(state).indexOf(tile) + 1;
				announce(`${tileTitle(tile)} moved to position ${position} of ${tiles.length}. Layout saved.`);
			}
		});

		state.grid.addEventListener("click", (event) => {
			if (!rearranging && Date.now() > suppressClickUntil) return;
			if (event.target.closest("a")) event.preventDefault();
		}, true);
	}

	toggleButton.addEventListener("click", () => setRearranging(!rearranging));
	resetButton.addEventListener("click", () => {
		let cleared = true;
		for (const state of states) {
			const tilesById = new Map(orderedTiles(state).map((tile) => [tile.dataset.dashboardTile, tile]));
			state.grid.replaceChildren(...state.originalOrder.map((tileId) => tilesById.get(tileId)).filter(Boolean));
			try {
				window.localStorage.removeItem(state.key);
			} catch (error) {
				cleared = false;
				reportStorageFailure();
			}
			for (const tile of orderedTiles(state)) {
				tile.classList.remove("dashboard-tile--dragging", "dashboard-tile--drop-target");
			}
		}
		if (cleared && !storageUnavailable) announce("Default tile order restored.");
	});
})();
