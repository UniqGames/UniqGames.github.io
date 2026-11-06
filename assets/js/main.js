/* Uniq Games — progressive enhancement only.
   Every page is fully readable and navigable with this file blocked. */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- Header shadow once the page has scrolled ------------------------- */
  function initHeader() {
    var header = document.querySelector(".site-header");
    if (!header) return;

    var ticking = false;
    function update() {
      header.classList.toggle("is-stuck", window.scrollY > 8);
      ticking = false;
    }
    update();
    window.addEventListener(
      "scroll",
      function () {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(update);
      },
      { passive: true }
    );
  }

  /* --- Mobile navigation ------------------------------------------------ */
  function initMobileNav() {
    var toggle = document.querySelector(".nav-toggle");
    var panel = document.getElementById("mobile-nav");
    if (!toggle || !panel) return;

    // The panel is hidden by `visibility: hidden` in CSS, which already removes
    // it from the accessibility tree and the tab order, and unlike the `hidden`
    // attribute it still allows the open and close transitions to run.
    function setOpen(open) {
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      panel.classList.toggle("is-open", open);
      document.body.classList.toggle("is-locked", open);
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    panel.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });

    // A resize past the desktop breakpoint must not leave the body locked.
    window.matchMedia("(min-width: 62rem)").addEventListener("change", function (event) {
      if (event.matches) setOpen(false);
    });
  }

  /* --- Copy to clipboard ------------------------------------------------ */
  function initCopy() {
    var buttons = document.querySelectorAll("[data-copy]");
    if (!buttons.length || !navigator.clipboard) return;

    Array.prototype.forEach.call(buttons, function (button) {
      var label = button.textContent;
      var timer;

      button.addEventListener("click", function () {
        navigator.clipboard.writeText(button.getAttribute("data-copy")).then(
          function () {
            button.textContent = "Copied";
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
              button.textContent = label;
            }, 2000);
          },
          function () {
            button.textContent = "Press \u2318C";
          }
        );
      });
    });
  }

  /* --- Reveal on scroll -------------------------------------------------- */
  function initReveal() {
    var targets = document.querySelectorAll("[data-reveal]");
    if (!targets.length) return;

    if (reduceMotion || !("IntersectionObserver" in window)) {
      Array.prototype.forEach.call(targets, function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 }
    );

    Array.prototype.forEach.call(targets, function (el, index) {
      el.style.transitionDelay = Math.min(index % 4, 3) * 80 + "ms";
      observer.observe(el);
    });
  }

  /* --- Privacy preferences ---------------------------------------------- */
  var PREF_KEY = "uniqgames.privacy-preferences";

  function readPrefs() {
    try {
      return JSON.parse(window.localStorage.getItem(PREF_KEY)) || {};
    } catch (error) {
      return {};
    }
  }

  function initPreferences() {
    var form = document.querySelector("[data-preferences]");
    if (!form) return;

    var status = form.querySelector("[data-preferences-status]");
    var inputs = form.querySelectorAll("input[type='checkbox'][name]");
    var saved = readPrefs();

    Array.prototype.forEach.call(inputs, function (input) {
      if (input.disabled) return;
      if (Object.prototype.hasOwnProperty.call(saved, input.name)) {
        input.checked = Boolean(saved[input.name]);
      }
    });

    function announce(message) {
      if (status) status.textContent = message;
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var next = {};
      Array.prototype.forEach.call(inputs, function (input) {
        next[input.name] = input.disabled ? true : input.checked;
      });
      try {
        window.localStorage.setItem(PREF_KEY, JSON.stringify(next));
        announce("Preferences saved on this device.");
      } catch (error) {
        announce("This browser is blocking storage, so preferences cannot be saved.");
      }
    });

    form.addEventListener("reset", function () {
      window.setTimeout(function () {
        try {
          window.localStorage.removeItem(PREF_KEY);
        } catch (error) {
          /* nothing to clear */
        }
        announce("Preferences reset to their defaults.");
      }, 0);
    });
  }

  /* --- Footer year ------------------------------------------------------- */
  function initYear() {
    var nodes = document.querySelectorAll("[data-year]");
    var year = String(new Date().getFullYear());
    Array.prototype.forEach.call(nodes, function (node) {
      node.textContent = year;
    });
  }

  function init() {
    initHeader();
    initMobileNav();
    initCopy();
    initReveal();
    initPreferences();
    initYear();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
