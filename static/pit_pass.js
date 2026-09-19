(function () {
  var cfg = window.MXPitPassConfig || {};
  var overlay = document.getElementById("pit-pass-modal");
  var card = overlay && overlay.querySelector(".pit-pass-card");
  var form = document.getElementById("pit-pass-form");
  var loginForm = document.getElementById("pit-pass-login-form");
  var errEl = document.getElementById("pit-pass-error");
  var loginErrEl = document.getElementById("pit-pass-login-error");
  var peekBtn = document.getElementById("pit-pass-peek");
  var submitBtn = document.getElementById("pit-pass-submit");
  var loginSubmitBtn = document.getElementById("pit-pass-login-submit");
  var signupPanel = overlay && overlay.querySelector('[data-pit-panel="signup"]');
  var loginPanel = overlay && overlay.querySelector('[data-pit-panel="login"]');
  if (!overlay || !form) return;

  var peekKey = cfg.peekKey || "mx_pit_pass_peek";

  function setMode(mode) {
    var next = mode === "login" ? "login" : "signup";
    if (card) card.setAttribute("data-mode", next);
    if (signupPanel) signupPanel.hidden = next !== "signup";
    if (loginPanel) loginPanel.hidden = next !== "login";
    if (next === "login" && loginForm) {
      var userInput = loginForm.querySelector('input[name="username"]');
      if (userInput) setTimeout(function () { userInput.focus(); }, 50);
    }
  }

  function showPitPass() {
    overlay.classList.remove("is-peek");
    document.body.style.overflow = "hidden";
    setMode("signup");
  }

  function peek() {
    overlay.classList.add("is-peek");
    document.body.style.overflow = "";
    try {
      sessionStorage.setItem(peekKey, "1");
    } catch (e) {}
  }

  window.MXShowPitPass = showPitPass;
  window.MXShowPitPassLogin = function () {
    showPitPass();
    setMode("login");
  };

  overlay.querySelectorAll("[data-pit-mode]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setMode(btn.getAttribute("data-pit-mode") || "signup");
    });
  });

  try {
    if (cfg.autoShow && sessionStorage.getItem(peekKey) === "1") {
      peek();
    } else if (!cfg.startHidden) {
      showPitPass();
    }
  } catch (e) {
    if (!cfg.startHidden) showPitPass();
  }

  if (peekBtn) peekBtn.addEventListener("click", peek);

  var guardSelectors = (cfg.guardSelectors || []).join(",");
  if (guardSelectors) {
    document.addEventListener(
      "click",
      function (e) {
        if (!overlay.classList.contains("is-peek")) return;
        var t = e.target;
        if (!t || !t.closest) return;
        if (t.closest("#pit-pass-modal")) return;
        if (t.closest(guardSelectors)) {
          e.preventDefault();
          e.stopPropagation();
          showPitPass();
        }
      },
      true
    );
  }

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || overlay.classList.contains("is-peek")) return;
    if (card && card.getAttribute("data-mode") === "login") {
      setMode("signup");
      return;
    }
    peek();
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (errEl) {
      errEl.textContent = "";
      errEl.classList.add("hidden");
    }
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Skapar konto…";
    }
    try {
      var fd = new FormData(form);
      var res = await fetch(cfg.registerUrl || "/register", {
        method: "POST",
        body: fd,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
      });
      var data = {};
      try {
        data = await res.json();
      } catch (_) {}
      if (!res.ok || !data.success) {
        throw new Error((data && data.error) || "Kunde inte skapa konto");
      }
      window.location.href = data.redirect || cfg.nextUrl || "/";
    } catch (err) {
      if (errEl) {
        errEl.textContent = err.message || "Något gick fel";
        errEl.classList.remove("hidden");
      }
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Kör igång →";
      }
    }
  });

  if (loginForm) {
    loginForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (loginErrEl) {
        loginErrEl.textContent = "";
        loginErrEl.classList.add("hidden");
      }
      if (loginSubmitBtn) {
        loginSubmitBtn.disabled = true;
        loginSubmitBtn.textContent = "Loggar in…";
      }
      try {
        var fd = new FormData(loginForm);
        var res = await fetch(cfg.loginUrl || "/login", {
          method: "POST",
          body: fd,
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            Accept: "application/json",
          },
        });
        var data = {};
        try {
          data = await res.json();
        } catch (_) {}
        if (!res.ok || !data.success) {
          throw new Error((data && data.error) || "Felaktigt användarnamn eller lösenord");
        }
        try {
          sessionStorage.setItem("mx_push_prompt_login", "1");
        } catch (_) {}
        if (window.MXPushNotify && window.MXPushNotify.markLoginForPrompt) {
          window.MXPushNotify.markLoginForPrompt();
        }
        // Stay on the page that opened Pit Pass (race picks / start), not a bare home hop.
        window.location.href = data.redirect || cfg.nextUrl || window.location.pathname || "/";
      } catch (err) {
        if (loginErrEl) {
          loginErrEl.textContent = err.message || "Något gick fel";
          loginErrEl.classList.remove("hidden");
        }
        if (loginSubmitBtn) {
          loginSubmitBtn.disabled = false;
          loginSubmitBtn.textContent = "Logga in →";
        }
      }
    });
  }
})();
