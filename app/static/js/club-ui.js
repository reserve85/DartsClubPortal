/* Club UI kit helpers (shared by all modules): initials avatars, toasts,
 * busy buttons and the phone card layout for tables. No dependencies. */
(function () {
    "use strict";

    function initials(name) {
        var parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return "?";
        var first = Array.from(parts[0])[0] || "";
        var last = parts.length > 1 ? (Array.from(parts[parts.length - 1])[0] || "") : (Array.from(parts[0])[1] || "");
        return (first + last).toUpperCase();
    }

    // Stable colour per name: a person keeps "their" colour on every page.
    var PALETTE = ["#206bc4", "#f76707", "#2fb344", "#ae3ec9", "#0ca678", "#d6336c", "#4263eb", "#e8590c", "#1098ad", "#7048e8"];
    function avatarColor(name) {
        var s = String(name || ""), h = 0;
        for (var i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; }
        return PALETTE[h % PALETTE.length];
    }

    function avatar(name, size) {
        var el = document.createElement("span");
        el.className = "ui-avatar" + (size ? " " + size : "");
        el.setAttribute("aria-hidden", "true");
        el.textContent = initials(name);
        el.style.setProperty("--ui-av", avatarColor(name));
        return el;
    }

    function toast(message, kind) {
        var box = document.getElementById("ui-toasts");
        if (!box) return;
        var el = document.createElement("div");
        el.className = "ui-toast" + (kind === "ok" ? " is-ok" : kind === "bad" ? " is-bad" : "");
        el.setAttribute("role", kind === "bad" ? "alert" : "status");
        el.textContent = message;
        box.appendChild(el);
        requestAnimationFrame(function () { el.classList.add("show"); });
        setTimeout(function () { el.classList.remove("show"); setTimeout(function () { el.remove(); }, 250); }, kind === "bad" ? 6000 : 3000);
        el.addEventListener("click", function () { el.remove(); });
    }

    // Phone card layout: label every cell with its column header.
    function labelTables(root) {
        (root || document).querySelectorAll("main table.table").forEach(function (table) {
            if (table.classList.contains("rt-keep") || table.classList.contains("rt-auto")) return;
            if (table.querySelector(".matrix-toggle, .participant-check, input[type=checkbox]")) {
                table.classList.add("rt-keep");
                return;
            }
            var heads = Array.from(table.querySelectorAll("thead th")).map(function (th) { return th.textContent.trim(); });
            if (!heads.length) return;
            table.classList.add("rt-auto");
            table.querySelectorAll("tbody > tr").forEach(function (tr) {
                var col = 0;
                Array.from(tr.children).forEach(function (td) {
                    if (!td.hasAttribute("data-label")) td.setAttribute("data-label", heads[col] || "");
                    if (td.querySelector(".btn") && !td.textContent.replace(/\s+/g, "").replace(/[^\w€]/g, "").length) {
                        td.classList.add("rt-actions");
                    }
                    if (td.querySelector("form .btn, a.btn, button.btn") && heads[col] === "") td.classList.add("rt-actions");
                    col += parseInt(td.getAttribute("colspan") || "1", 10);
                });
            });
        });
    }

    // Initials avatar in front of every link to a player page.
    function personLinks(root) {
        (root || document).querySelectorAll('main a[href*="/players/"]:not(.btn):not([data-no-avatar])').forEach(function (a) {
            if (!/\/players\/\d+\/?$/.test(a.getAttribute("href") || "") || a.querySelector(".ui-avatar")) return;
            var name = a.textContent.trim();
            if (!name) return;
            a.classList.add("ui-person");
            a.insertBefore(avatar(name, "sm"), a.firstChild);
        });
    }

    // Disable a submit button while its form is being sent (no double submit).
    function busyForms() {
        document.addEventListener("submit", function (ev) {
            var form = ev.target;
            if (!(form instanceof HTMLFormElement) || ev.defaultPrevented) return;
            var btn = ev.submitter || form.querySelector('[type="submit"]');
            if (!btn || btn.classList.contains("nav-link") || btn.hasAttribute("data-no-busy")) return;
            setTimeout(function () { btn.classList.add("is-busy"); btn.setAttribute("aria-busy", "true"); }, 0);
        });
        // Back/forward cache: never leave a button spinning.
        window.addEventListener("pageshow", function () {
            document.querySelectorAll(".btn.is-busy").forEach(function (b) { b.classList.remove("is-busy"); b.removeAttribute("aria-busy"); });
        });
    }

    window.clubUi = { initials: initials, avatarColor: avatarColor, avatar: avatar, toast: toast, labelTables: labelTables };

    function init() {
        document.querySelectorAll(".ui-avatar[data-name]").forEach(function (el) {
            el.textContent = initials(el.getAttribute("data-name"));
            if (!el.classList.contains("is-a") && !el.classList.contains("is-b")) el.style.setProperty("--ui-av", avatarColor(el.getAttribute("data-name")));
        });
        labelTables();
        personLinks();
        busyForms();
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
