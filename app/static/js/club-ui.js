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

/* Small dependency-free SVG line chart: clubUi.lineChart(el, points, opts)
 * points: [{x: "2026-01-31", y: 1234.5, id: 7}], opts: {zero: bool, href: fn(p)} */
(function () {
    "use strict";
    var NS = "http://www.w3.org/2000/svg";
    function el(name, attrs) {
        var n = document.createElementNS(NS, name);
        Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        return n;
    }
    function lineChart(box, points, opts) {
        opts = opts || {};
        box.innerHTML = "";
        if (!points || points.length < 2) {
            var empty = document.createElement("div");
            empty.className = "ui-chart-empty";
            empty.textContent = box.getAttribute("data-empty") || "–";
            box.appendChild(empty);
            return;
        }
        var W = 600, H = 190, L = 38, R = 8, T = 10, B = 22;
        var ys = points.map(function (p) { return p.y; });
        var min = Math.min.apply(null, ys), max = Math.max.apply(null, ys);
        if (opts.zero) { min = Math.min(min, 0); max = Math.max(max, 0); }
        if (min === max) { min -= 1; max += 1; }
        var pad = (max - min) * 0.08; min -= pad; max += pad;
        var x = function (i) { return L + (W - L - R) * (points.length === 1 ? 0.5 : i / (points.length - 1)); };
        var y = function (v) { return T + (H - T - B) * (1 - (v - min) / (max - min)); };
        var svg = el("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none", role: "img" });
        var defs = el("defs"), grad = el("linearGradient", { id: "ui-chart-fill", x1: 0, y1: 0, x2: 0, y2: 1 });
        grad.appendChild(el("stop", { offset: "0%", "stop-color": opts.color || "#206bc4", "stop-opacity": 0.28 }));
        grad.appendChild(el("stop", { offset: "100%", "stop-color": opts.color || "#206bc4", "stop-opacity": 0 }));
        defs.appendChild(grad); svg.appendChild(defs);
        for (var g = 0; g <= 3; g++) {
            var v = min + (max - min) * g / 3, gy = y(v);
            svg.appendChild(el("line", { x1: L, x2: W - R, y1: gy, y2: gy, "class": "grid" }));
            var t = el("text", { x: L - 6, y: gy + 3, "text-anchor": "end", "class": "axis" });
            t.textContent = Math.round(v);
            svg.appendChild(t);
        }
        if (opts.zero) svg.appendChild(el("line", { x1: L, x2: W - R, y1: y(0), y2: y(0), "class": "zero" }));
        var d = points.map(function (p, i) { return (i ? "L" : "M") + x(i).toFixed(1) + " " + y(p.y).toFixed(1); }).join(" ");
        svg.appendChild(el("path", { d: d + " L" + x(points.length - 1) + " " + (H - B) + " L" + x(0) + " " + (H - B) + " Z", "class": "area" }));
        svg.appendChild(el("path", { d: d, "class": "line" }));
        [0, points.length - 1].forEach(function (i) {
            var lab = el("text", { x: x(i), y: H - 6, "text-anchor": i ? "end" : "start", "class": "axis" });
            lab.textContent = String(points[i].x).split("-").reverse().join(".");
            svg.appendChild(lab);
        });
        if (points.length <= 60) {
            points.forEach(function (p, i) {
                var c = el("circle", { cx: x(i), cy: y(p.y), r: 3.2, "class": "dot" });
                var tip = el("title"); tip.textContent = String(p.x).split("-").reverse().join(".") + ": " + (Math.round(p.y * 10) / 10);
                c.appendChild(tip);
                if (opts.href && p.id) {
                    var a = el("a", { href: opts.href(p) }); a.appendChild(c); svg.appendChild(a);
                } else { svg.appendChild(c); }
            });
        }
        box.appendChild(svg);
    }
    window.clubUi = window.clubUi || {};
    window.clubUi.lineChart = lineChart;
    function init() {
        document.querySelectorAll(".ui-chart[data-points]").forEach(function (box) {
            var src = document.getElementById(box.getAttribute("data-points"));
            if (!src) return;
            var raw = JSON.parse(src.textContent), key = box.getAttribute("data-key") || "y";
            var pts = raw.map(function (r) { return { x: r.date, y: r[key], id: r.match_id }; });
            var tpl = box.getAttribute("data-href");
            lineChart(box, pts, {
                zero: box.hasAttribute("data-zero"),
                color: box.classList.contains("is-b") ? "#f76707" : "#206bc4",
                href: tpl ? function (p) { return tpl.replace("/0/", "/" + p.id + "/"); } : null
            });
        });
        // Switches that toggle a query parameter (e.g. "show inactive").
        document.querySelectorAll("input[data-toggle-param]").forEach(function (sw) {
            sw.addEventListener("change", function () {
                var u = new URL(window.location.href), key = sw.getAttribute("data-toggle-param");
                if (sw.checked) u.searchParams.set(key, "1"); else u.searchParams.delete(key);
                window.location.href = u.toString();
            });
        });
        // Selects that submit their form on change (head-to-head pickers).
        document.querySelectorAll("select[data-autosubmit]").forEach(function (sel) {
            sel.addEventListener("change", function () {
                var form = sel.form;
                if (!form) return;
                if (sel.name === "a" && form.elements.b) form.elements.b.value = "";
                form.submit();
            });
        });
        // Score steppers (match entry)
        document.querySelectorAll("[data-step]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var input = document.getElementById(btn.getAttribute("data-target"));
                if (!input) return;
                var v = parseInt(input.value || "0", 10) + parseInt(btn.getAttribute("data-step"), 10);
                var max = parseInt(input.getAttribute("max") || "99", 10);
                input.value = Math.max(0, Math.min(max, v));
                input.dispatchEvent(new Event("input", { bubbles: true }));
            });
        });
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
