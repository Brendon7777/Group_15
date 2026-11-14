/* Sign-in and registration forms -> POST /api/login and POST /api/register (Task 3A). */
(function () {
	"use strict";
	const { api, ui } = window.LTSM;

	/* Sign in */
	const loginForm = document.getElementById("login-form");
	if (loginForm) {
		const feedback = document.getElementById("login-feedback");
		const button = loginForm.querySelector('button[type="submit"]');

		loginForm.addEventListener("submit", async (event) => {
			event.preventDefault();
			if (!loginForm.reportValidity()) return;
			ui.hideFeedback(feedback);
			ui.setBusy(button, true, "Signing in…");
			try {
				const data = await api.post("/api/login", {
					role: loginForm.elements["role"].value,
					username: loginForm.elements["username"].value.trim(),
					password: loginForm.elements["password"].value
				});
				window.location.assign(data.redirect);
			} catch (error) {
				ui.showFeedback(feedback, "error", error.message);
				ui.setBusy(button, false);
			}
		});
	}

	/* Create an account */
	const registerForm = document.getElementById("register-form");
	if (registerForm) {
		ui.bindForm(registerForm, {
			feedbackId: "register-feedback",
			endpoint: "/api/register",
			busyText: "Creating account…",
			payload: (v) => ({
				full_name: v.full_name.trim(),
				account_type: v.account_type,
				school_id: v.school_id.trim(),
				email: v.email.trim(),
				password: v.password,
				confirm_password: v.confirm_password
			}),
			success: () => "Account created. Taking you to sign in…",
			onSuccess: () => { setTimeout(() => window.location.assign("/login"), 1200); }
		});
	}
})();
