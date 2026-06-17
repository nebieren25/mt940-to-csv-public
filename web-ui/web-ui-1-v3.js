/**
 * Web UI v3 – MT940 convert, financial summary (real data), preview, download.
 * Uses /api/convert and /api/export; no mt940-api.js dependency.
 */
(function () {
  "use strict";

  var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  /** Show all rows in preview (no limit). */
  var PREVIEW_ROWS = null;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $$(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  var els = {};
  function cacheEls() {
    els.fileInput = $("#v3-file-input");
    els.error = $("#v3-error");
    els.encoding = $("#v3-encoding") || $('select[name="encoding"]');
    els.decimalSep = $("#v3-decimal-sep") || $('select[name="decimal_sep"]');
    els.formatDates = $("#v3-format-dates");
    els.dateSeparator = $('input[name="date_separator"]');
    els.periodStart = $("[data-v3-period-start]");
    els.periodEnd = $("[data-v3-period-end]");
    els.totalIncome = $("[data-v3-total-income]");
    els.totalExpense = $("[data-v3-total-expense]");
    els.netChange = $("[data-v3-net-change]");
    els.mixedCurrency = $("[data-v3-mixed-currency]");
    els.overviewBreakdown = $("#v3-overview-breakdown");
    els.volTotal = $("[data-v3-vol-total]");
    els.volIncome = $("[data-v3-vol-income]");
    els.volExpense = $("[data-v3-vol-expense]");
    els.volumeBreakdown = $("#v3-volume-breakdown");
    els.previewTbody = $("[data-v3-preview-tbody]");
    els.previewCount = $("[data-v3-preview-count]");
    els.rowCount = $("[data-v3-row-count]");
    els.copyPreview = $("[data-v3-copy-preview]");
    els.resetBtn = $("[data-v3-reset]");
    els.downloadBtn = $("[data-v3-download]");
  }

  var state = {
    rows: [],
    csvFromConvert: null,
    convertDelimiter: null,
    convertDecimalSep: null,
  };

  function getEncoding() {
    return els.encoding ? els.encoding.value : "utf-8";
  }
  function getDelimiter() {
    var radio = $('input[name="delimiter"]:checked');
    if (radio) return radio.value === "\\t" ? "\t" : radio.value;
    return ";";
  }
  function getDecimalSep() {
    return els.decimalSep ? els.decimalSep.value : ",";
  }
  function getFormatDatesIso() {
    return els.formatDates ? els.formatDates.checked : false;
  }
  function getDateSeparator() {
    var radio = $('input[name="date_separator"]:checked');
    return radio ? radio.value : "-";
  }

  function parseAmount(row, decimalSep) {
    var raw = row.signed_amount != null ? row.signed_amount : row.amount;
    if (raw == null && (row.amount != null || row.debit_credit != null)) {
      var dc = (row.debit_credit || "").toString().trim().toUpperCase();
      raw = row.amount != null ? row.amount : "";
      if (raw === "") return 0;
      var s = String(raw).trim();
      s = decimalSep === "," ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
      var n = parseFloat(s);
      return isNaN(n) ? 0 : dc === "D" ? -n : n;
    }
    if (raw == null || raw === "") return 0;
    var str = String(raw).trim();
    str = decimalSep === "," ? str.replace(/\./g, "").replace(",", ".") : str.replace(/,/g, "");
    var num = parseFloat(str);
    return isNaN(num) ? 0 : num;
  }

  function parseDate(value) {
    if (value == null || (typeof value === "string" && !value.trim())) return null;
    var s = String(value).trim();
    if (!s) return null;
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.substring(0, 10);
    var dmY = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/);
    if (dmY) {
      var d = dmY[1].padStart(2, "0");
      var m = dmY[2].padStart(2, "0");
      var y = dmY[3];
      return y + "-" + m + "-" + d;
    }
    var ymd = s.match(/^(\d{4})[-/](\d{2})[-/](\d{2})/);
    if (ymd) return ymd[1] + "-" + ymd[2] + "-" + ymd[3];
    return null;
  }

  function formatDateForDisplay(isoStr, useIso, separator) {
    if (!isoStr || isoStr.length < 10) return isoStr || "—";
    var sep = separator === "/" ? "/" : "-";
    if (useIso) return isoStr.substring(0, 10);
    var p = isoStr.substring(0, 10).split("-");
    if (p.length !== 3) return isoStr;
    return p[2] + sep + p[1] + sep + p[0];
  }

  function formatDateForCsv(isoStr, useIso, separator) {
    if (!isoStr || isoStr.length < 10) return isoStr || "";
    var sep = separator === "/" ? "/" : "-";
    var p = isoStr.substring(0, 10).split("-");
    if (p.length !== 3) return isoStr;
    if (useIso) return p[0] + sep + p[1] + sep + p[2];
    return p[2] + sep + p[1] + sep + p[0];
  }

  function computeOverviewTotals(rows) {
    var totalIncome = 0;
    var totalExpense = 0;
    var decSep = getDecimalSep();
    for (var i = 0; i < rows.length; i++) {
      var a = parseAmount(rows[i], decSep);
      if (a > 0) totalIncome += a;
      else if (a < 0) totalExpense += Math.abs(a);
    }
    return {
      totalIncome: totalIncome,
      totalExpense: totalExpense,
      netChange: totalIncome - totalExpense,
    };
  }

  function rowYQM(row) {
    var d = parseDate(row.value_date || row.entry_date);
    if (!d || d.length < 10) return { y: null, q: null, m: null };
    try {
      var y = parseInt(d.substring(0, 4), 10);
      var m = parseInt(d.substring(5, 7), 10);
      var q = Math.floor((m - 1) / 3) + 1;
      return { y: y, q: q, m: m };
    } catch (e) {
      return { y: null, q: null, m: null };
    }
  }

  function groupByYearQuarterMonthAmount(rows) {
    var decSep = getDecimalSep();
    var yearData = {};
    var quarterData = {};
    var monthData = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var yqm = rowYQM(r);
      if (yqm.y == null) continue;
      var amt = parseAmount(r, decSep);
      var inc = amt > 0 ? amt : 0;
      var exp = amt < 0 ? Math.abs(amt) : 0;
      yearData[yqm.y] = yearData[yqm.y] || { in: 0, out: 0 };
      yearData[yqm.y].in += inc;
      yearData[yqm.y].out += exp;
      var qk = yqm.y + "-" + yqm.q;
      quarterData[qk] = quarterData[qk] || { in: 0, out: 0 };
      quarterData[qk].in += inc;
      quarterData[qk].out += exp;
      var mk = yqm.y + "-" + yqm.q + "-" + yqm.m;
      monthData[mk] = monthData[mk] || { in: 0, out: 0 };
      monthData[mk].in += inc;
      monthData[mk].out += exp;
    }
    var years = Object.keys(yearData).map(Number).sort(function (a, b) { return b - a; });
    var result = [];
    for (var yi = 0; yi < years.length; yi++) {
      var y = years[yi];
      var yd = yearData[y];
      result.push({ level: 0, year: y, quarter: null, month: null, period: String(y), in: yd.in, out: yd.out, net: yd.in - yd.out });
      for (var q = 1; q <= 4; q++) {
        var qk = y + "-" + q;
        var qd = quarterData[qk] || { in: 0, out: 0 };
        result.push({ level: 1, year: y, quarter: q, month: null, period: "Q" + q + " " + y, in: qd.in, out: qd.out, net: qd.in - qd.out });
        for (var m = (q - 1) * 3 + 1; m <= q * 3; m++) {
          var mk = y + "-" + q + "-" + m;
          var md = monthData[mk] || { in: 0, out: 0 };
          result.push({ level: 2, year: y, quarter: q, month: m, period: MONTH_NAMES[m - 1], in: md.in, out: md.out, net: md.in - md.out });
        }
      }
    }
    return result;
  }

  function groupByYearQuarterMonthCounts(rows) {
    var decSep = getDecimalSep();
    var yearData = {};
    var quarterData = {};
    var monthData = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var yqm = rowYQM(r);
      if (yqm.y == null) continue;
      var amt = parseAmount(r, decSep);
      var isIn = amt > 0;
      var isOut = amt < 0;
      yearData[yqm.y] = yearData[yqm.y] || { in: 0, out: 0, total: 0 };
      yearData[yqm.y].total++;
      if (isIn) yearData[yqm.y].in++;
      if (isOut) yearData[yqm.y].out++;
      var qk = yqm.y + "-" + yqm.q;
      quarterData[qk] = quarterData[qk] || { in: 0, out: 0, total: 0 };
      quarterData[qk].total++;
      if (isIn) quarterData[qk].in++;
      if (isOut) quarterData[qk].out++;
      var mk = yqm.y + "-" + yqm.q + "-" + yqm.m;
      monthData[mk] = monthData[mk] || { in: 0, out: 0, total: 0 };
      monthData[mk].total++;
      if (isIn) monthData[mk].in++;
      if (isOut) monthData[mk].out++;
    }
    var years = Object.keys(yearData).map(Number).sort(function (a, b) { return b - a; });
    var result = [];
    for (var yi = 0; yi < years.length; yi++) {
      var y = years[yi];
      var yd = yearData[y];
      result.push({ level: 0, year: y, quarter: null, month: null, period: String(y), in: yd.in, out: yd.out, total: yd.total });
      for (var q = 1; q <= 4; q++) {
        var qk = y + "-" + q;
        var qd = quarterData[qk] || { in: 0, out: 0, total: 0 };
        result.push({ level: 1, year: y, quarter: q, month: null, period: "Q" + q + " " + y, in: qd.in, out: qd.out, total: qd.total });
        for (var m = (q - 1) * 3 + 1; m <= q * 3; m++) {
          var mk = y + "-" + q + "-" + m;
          var md = monthData[mk] || { in: 0, out: 0, total: 0 };
          result.push({ level: 2, year: y, quarter: q, month: m, period: MONTH_NAMES[m - 1], in: md.in, out: md.out, total: md.total });
        }
      }
    }
    return result;
  }

  function formatNum(n, decimalSep) {
    if (n == null || isNaN(n)) return "0";
    var s = Math.abs(n).toFixed(2);
    if (decimalSep === ",") s = s.replace(".", ",");
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, decimalSep === "," ? "." : ",");
  }
  function formatSignedNum(n, decimalSep) {
    if (n == null || isNaN(n)) return "0";
    var s = formatNum(Math.abs(n), decimalSep);
    if (n >= 0) return "+" + s;
    return "-" + s;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function renderOverviewBreakdown(container, breakdownData, decimalSep) {
    if (!container) return;
    container.innerHTML = "";
    if (!breakdownData || breakdownData.length === 0) {
      var p = document.createElement("p");
      p.className = "text-[10px] text-slate-400 py-2";
      p.textContent = "No data yet";
      container.appendChild(p);
      return;
    }
    var header = document.createElement("div");
    header.className = "grid grid-cols-4 gap-1 text-[10px] uppercase text-slate-400 font-semibold mb-2";
    header.innerHTML = '<div class="col-span-1 pl-6">Period</div><div class="text-right text-green-600/70 dark:text-green-400/70">In</div><div class="text-right text-red-500/70 dark:text-red-400/70">Out</div><div class="text-right">Net</div>';
    container.appendChild(header);
    var yearIndices = [];
    for (var i = 0; i < breakdownData.length; i++) {
      if (breakdownData[i].level === 0) yearIndices.push(i);
    }
    for (var yi = 0; yi < yearIndices.length; yi++) {
      var start = yearIndices[yi];
      var end = yi < yearIndices.length - 1 ? yearIndices[yi + 1] : breakdownData.length;
      var yearRow = breakdownData[start];
      var yearWrap = document.createElement("div");
      yearWrap.className = "group" + (yi > 0 ? " mt-1" : "");
      var yearBtn = document.createElement("button");
      yearBtn.setAttribute("aria-expanded", "false");
      yearBtn.type = "button";
      yearBtn.className = "w-full grid grid-cols-4 gap-1 items-center py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded text-xs font-medium text-slate-700 dark:text-slate-200 transition-colors text-left rotate-90-active hide-collapsed";
      yearBtn.innerHTML = '<div class="col-span-1 flex items-center gap-1"><span class="material-symbols-outlined text-sm text-slate-400 transition-transform duration-200 chevron">chevron_right</span>' + escapeHtml(yearRow.period) + '</div><div class="text-right font-mono text-green-600 dark:text-green-400">' + formatNum(yearRow.in, decimalSep) + '</div><div class="text-right font-mono text-red-500 dark:text-red-400">' + formatNum(yearRow.out, decimalSep) + '</div><div class="text-right font-mono font-bold">' + formatSignedNum(yearRow.net, decimalSep) + '</div>';
      yearWrap.appendChild(yearBtn);
      var childRows = document.createElement("div");
      childRows.className = "child-rows space-y-0.5 border-l border-slate-200 dark:border-slate-700 ml-2 pl-2";
      for (var qi = start + 1; qi < end; qi++) {
        var row = breakdownData[qi];
        if (row.level === 1) {
          var qWrap = document.createElement("div");
          qWrap.className = "group/sub";
          var qBtn = document.createElement("button");
          qBtn.setAttribute("aria-expanded", "false");
          qBtn.type = "button";
          qBtn.className = "w-full grid grid-cols-4 gap-1 items-center py-1 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded text-[11px] text-slate-600 dark:text-slate-300 text-left rotate-90-active hide-collapsed";
          qBtn.innerHTML = '<div class="col-span-1 flex items-center gap-1 pl-1"><span class="material-symbols-outlined text-xs text-slate-400 transition-transform duration-200 chevron">chevron_right</span>' + escapeHtml(row.period) + '</div><div class="text-right font-mono text-green-600/80 dark:text-green-400/80">' + formatNum(row.in, decimalSep) + '</div><div class="text-right font-mono text-red-500/80 dark:text-red-400/80">' + formatNum(row.out, decimalSep) + '</div><div class="text-right font-mono">' + formatSignedNum(row.net, decimalSep) + '</div>';
          qWrap.appendChild(qBtn);
          var monthRows = document.createElement("div");
          monthRows.className = "child-rows space-y-0.5 ml-3 border-l border-slate-200 dark:border-slate-700 pl-2 py-0.5";
          var nextQi = qi + 1;
          while (nextQi < end && breakdownData[nextQi].level === 2) {
            var mr = breakdownData[nextQi];
            var mDiv = document.createElement("div");
            mDiv.className = "grid grid-cols-4 gap-1 items-center py-0.5 text-[10px] text-slate-500 dark:text-slate-400";
            mDiv.innerHTML = '<div class="col-span-1 pl-2">' + escapeHtml(mr.period) + '</div><div class="text-right font-mono">' + formatNum(mr.in, decimalSep) + '</div><div class="text-right font-mono">' + formatNum(mr.out, decimalSep) + '</div><div class="text-right font-mono">' + formatSignedNum(mr.net, decimalSep) + '</div>';
            monthRows.appendChild(mDiv);
            nextQi++;
          }
          qWrap.appendChild(monthRows);
          childRows.appendChild(qWrap);
        }
      }
      yearWrap.appendChild(childRows);
      container.appendChild(yearWrap);
    }
    delegateExpandCollapse(container);
  }

  function renderVolumeBreakdown(container, breakdownData) {
    if (!container) return;
    container.innerHTML = "";
    if (!breakdownData || breakdownData.length === 0) {
      var p = document.createElement("p");
      p.className = "text-[10px] text-slate-400 py-2";
      p.textContent = "No data yet";
      container.appendChild(p);
      return;
    }
    var header = document.createElement("div");
    header.className = "grid grid-cols-4 gap-1 text-[10px] uppercase text-slate-400 font-semibold mb-2";
    header.innerHTML = '<div class="col-span-1 pl-6">Period</div><div class="text-right text-[#10B981]">In</div><div class="text-right text-[#EF4444]">Out</div><div class="text-right">Total</div>';
    container.appendChild(header);
    var yearIndices = [];
    for (var i = 0; i < breakdownData.length; i++) {
      if (breakdownData[i].level === 0) yearIndices.push(i);
    }
    for (var yi = 0; yi < yearIndices.length; yi++) {
      var start = yearIndices[yi];
      var end = yi < yearIndices.length - 1 ? yearIndices[yi + 1] : breakdownData.length;
      var yearRow = breakdownData[start];
      var yearWrap = document.createElement("div");
      yearWrap.className = "group" + (yi > 0 ? " mt-1" : "");
      var yearBtn = document.createElement("button");
      yearBtn.setAttribute("aria-expanded", "false");
      yearBtn.type = "button";
      yearBtn.className = "w-full grid grid-cols-4 gap-1 items-center py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded text-xs font-medium text-slate-700 dark:text-slate-200 transition-colors text-left rotate-90-active hide-collapsed";
      yearBtn.innerHTML = '<div class="col-span-1 flex items-center gap-1"><span class="material-symbols-outlined text-sm text-slate-400 transition-transform duration-200 chevron">chevron_right</span>' + escapeHtml(yearRow.period) + '</div><div class="text-right font-mono">' + yearRow.in + '</div><div class="text-right font-mono">' + yearRow.out + '</div><div class="text-right font-mono font-bold">' + yearRow.total + '</div>';
      yearWrap.appendChild(yearBtn);
      var childRows = document.createElement("div");
      childRows.className = "child-rows space-y-0.5 border-l border-slate-200 dark:border-slate-700 ml-2 pl-2";
      for (var qi = start + 1; qi < end; qi++) {
        var row = breakdownData[qi];
        if (row.level === 1) {
          var qWrap = document.createElement("div");
          qWrap.className = "group/sub";
          var qBtn = document.createElement("button");
          qBtn.setAttribute("aria-expanded", "false");
          qBtn.type = "button";
          qBtn.className = "w-full grid grid-cols-4 gap-1 items-center py-1 hover:bg-slate-100 dark:hover:bg-slate-700/50 rounded text-[11px] text-slate-600 dark:text-slate-300 text-left rotate-90-active hide-collapsed";
          qBtn.innerHTML = '<div class="col-span-1 flex items-center gap-1 pl-1"><span class="material-symbols-outlined text-xs text-slate-400 transition-transform duration-200 chevron">chevron_right</span>' + escapeHtml(row.period) + '</div><div class="text-right font-mono">' + row.in + '</div><div class="text-right font-mono">' + row.out + '</div><div class="text-right font-mono">' + row.total + '</div>';
          qWrap.appendChild(qBtn);
          var monthRows = document.createElement("div");
          monthRows.className = "child-rows space-y-0.5 ml-3 border-l border-slate-200 dark:border-slate-700 pl-2 py-0.5";
          var nextQi = qi + 1;
          while (nextQi < end && breakdownData[nextQi].level === 2) {
            var mr = breakdownData[nextQi];
            var mDiv = document.createElement("div");
            mDiv.className = "grid grid-cols-4 gap-1 items-center py-0.5 text-[10px] text-slate-500 dark:text-slate-400";
            mDiv.innerHTML = '<div class="col-span-1 pl-2">' + escapeHtml(mr.period) + '</div><div class="text-right font-mono">' + mr.in + '</div><div class="text-right font-mono">' + mr.out + '</div><div class="text-right font-mono">' + mr.total + '</div>';
            monthRows.appendChild(mDiv);
            nextQi++;
          }
          qWrap.appendChild(monthRows);
          childRows.appendChild(qWrap);
        }
      }
      yearWrap.appendChild(childRows);
      container.appendChild(yearWrap);
    }
    delegateExpandCollapse(container);
  }

  function delegateExpandCollapse(container) {
    if (!container) return;
    container.querySelectorAll("button[aria-expanded]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var expanded = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", !expanded);
      });
    });
  }

  function renderPreviewTable(rows, options) {
    options = options || {};
    var tbody = els.previewTbody;
    var formatDatesIso = options.formatDatesIso !== false;
    var dateSeparator = options.dateSeparator || getDateSeparator();
    var arr = rows || [];
    var limit = options.limit != null ? options.limit : (PREVIEW_ROWS == null ? arr.length : PREVIEW_ROWS);
    if (!tbody) return;
    tbody.innerHTML = "";
    var slice = arr.slice(0, limit);
    for (var i = 0; i < slice.length; i++) {
      var row = slice[i];
      var dateStr = row.value_date || row.entry_date || "";
      var iso = parseDate(dateStr);
      var displayDate = formatDateForDisplay(iso, formatDatesIso, dateSeparator);
      var amountRaw = row.signed_amount != null ? row.signed_amount : row.amount;
      var amountStr = amountRaw != null ? String(amountRaw) : "";
      var amountClass = (amountStr + "").indexOf("-") === 0 ? "text-red-500 dark:text-red-400" : "text-green-600 dark:text-green-400";
      var desc = (row.cleared_description || row.description || "").substring(0, 80);
      var tr = document.createElement("tr");
      tr.className = "hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors" + (i % 2 ? " bg-slate-50/30 dark:bg-slate-800/20" : "");
      tr.innerHTML =
        "<td class=\"px-6 py-3 text-slate-400\">" + escapeHtml(String(i + 1)) + "</td>" +
        "<td class=\"px-6 py-3 text-slate-700 dark:text-slate-300\">" + escapeHtml(displayDate) + "</td>" +
        "<td class=\"px-6 py-3 text-slate-700 dark:text-slate-300\">" + escapeHtml(row.account || "") + "</td>" +
        "<td class=\"px-6 py-3 text-right font-medium " + amountClass + "\">" + escapeHtml(amountStr) + "</td>" +
        "<td class=\"px-6 py-3 text-slate-500\">" + escapeHtml(row.currency || "") + "</td>" +
        "<td class=\"px-6 py-3 text-slate-600 dark:text-slate-400 truncate max-w-[200px]\">" + escapeHtml(desc) + "</td>" +
        "<td class=\"px-6 py-3 text-slate-500\">" + escapeHtml(row.reference || "") + "</td>";
      tbody.appendChild(tr);
    }
    if (els.previewCount) els.previewCount.textContent = slice.length;
  }

  function checkCurrencies(rows) {
    var set = {};
    for (var i = 0; i < rows.length; i++) {
      var c = (rows[i].currency || "").trim();
      if (c) set[c] = true;
    }
    var n = Object.keys(set).length;
    return n > 1 ? "mixed" : null;
  }

  function showError(msg) {
    if (!els.error) return;
    els.error.textContent = msg || "";
    els.error.style.display = msg ? "block" : "none";
  }

  function updateUIFromState() {
    var rows = state.rows;
    var n = rows.length;
    if (els.rowCount) els.rowCount.textContent = n;
    renderPreviewTable(rows, { formatDatesIso: getFormatDatesIso(), dateSeparator: getDateSeparator() });
    if (n === 0) {
      if (els.periodStart) els.periodStart.textContent = "—";
      if (els.periodEnd) els.periodEnd.textContent = "—";
      if (els.totalIncome) els.totalIncome.textContent = "0";
      if (els.totalExpense) els.totalExpense.textContent = "0";
      if (els.netChange) els.netChange.textContent = "0";
      if (els.mixedCurrency) { els.mixedCurrency.classList.add("hidden"); }
      if (els.overviewBreakdown) renderOverviewBreakdown(els.overviewBreakdown, [], getDecimalSep());
      if (els.volTotal) els.volTotal.textContent = "0";
      if (els.volIncome) els.volIncome.textContent = "0";
      if (els.volExpense) els.volExpense.textContent = "0";
      if (els.volumeBreakdown) renderVolumeBreakdown(els.volumeBreakdown, []);
      return;
    }
    var decSep = getDecimalSep();
    var formatIso = getFormatDatesIso();
    var dateSeparator = getDateSeparator();
    var dates = [];
    for (var i = 0; i < rows.length; i++) {
      var d = parseDate(rows[i].value_date || rows[i].entry_date);
      if (d) dates.push(d);
    }
    var minDate = dates.length ? dates.reduce(function (a, b) { return a < b ? a : b; }) : null;
    var maxDate = dates.length ? dates.reduce(function (a, b) { return a > b ? a : b; }) : null;
    if (els.periodStart) els.periodStart.textContent = formatDateForDisplay(minDate, formatIso, dateSeparator);
    if (els.periodEnd) els.periodEnd.textContent = formatDateForDisplay(maxDate, formatIso, dateSeparator);
    var totals = computeOverviewTotals(rows);
    if (els.totalIncome) els.totalIncome.textContent = formatNum(totals.totalIncome, decSep);
    if (els.totalExpense) els.totalExpense.textContent = formatNum(totals.totalExpense, decSep);
    if (els.netChange) els.netChange.textContent = formatSignedNum(totals.netChange, decSep);
    var mixed = checkCurrencies(rows);
    if (els.mixedCurrency) {
      if (mixed) els.mixedCurrency.classList.remove("hidden");
      else els.mixedCurrency.classList.add("hidden");
    }
    var amountBreakdown = groupByYearQuarterMonthAmount(rows);
    if (els.overviewBreakdown) renderOverviewBreakdown(els.overviewBreakdown, amountBreakdown, decSep);
    var incomeCount = 0;
    var expenseCount = 0;
    for (var j = 0; j < rows.length; j++) {
      var amt = parseAmount(rows[j], decSep);
      if (amt > 0) incomeCount++;
      else if (amt < 0) expenseCount++;
    }
    if (els.volTotal) els.volTotal.textContent = n;
    if (els.volIncome) els.volIncome.textContent = incomeCount;
    if (els.volExpense) els.volExpense.textContent = expenseCount;
    var countBreakdown = groupByYearQuarterMonthCounts(rows);
    if (els.volumeBreakdown) renderVolumeBreakdown(els.volumeBreakdown, countBreakdown);
  }

  function convertFile(file) {
    if (!file) return Promise.reject(new Error("No file"));
    var fd = new FormData();
    fd.append("file", file);
    fd.append("encoding", getEncoding());
    var delim = getDelimiter();
    fd.append("delimiter", delim);
    fd.append("decimal_sep", getDecimalSep());
    return fetch("/api/convert", { method: "POST", body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.detail && !data.success) {
          showError(data.detail || "Request failed.");
          state.rows = [];
          state.csvFromConvert = null;
          updateUIFromState();
          return;
        }
        if (!data.success) {
          showError(data.detail || "No transactions found.");
          state.rows = [];
          state.csvFromConvert = null;
          updateUIFromState();
          return;
        }
        state.rows = data.rows || [];
        state.csvFromConvert = data.csv || null;
        state.convertDelimiter = getDelimiter();
        state.convertDecimalSep = getDecimalSep();
        showError("");
        updateUIFromState();
      });
  }

  function rowsForExportWithDateFormat(rows) {
    var useIso = getFormatDatesIso();
    var separator = getDateSeparator();
    return (rows || []).map(function (row) {
      var out = Object.assign({}, row);
      var iso = parseDate(row.date || row.value_date || row.entry_date);
      var formatted = formatDateForCsv(iso, useIso, separator);
      if (formatted) {
        out.date = formatted;
        out.value_date = formatted;
      }
      return out;
    });
  }

  function onDownloadCsv() {
    if (state.rows.length === 0) {
      showError("No data to download. Upload an MT940 or CSV file first.");
      return;
    }
    var delim = getDelimiter();
    var decSep = getDecimalSep();
    var datesMatchBackendDefault = getFormatDatesIso() === false && getDateSeparator() === "-";
    var useCached = (
      datesMatchBackendDefault &&
      state.csvFromConvert != null &&
      state.convertDelimiter === delim &&
      state.convertDecimalSep === decSep
    );
    if (useCached) {
      var blob = new Blob([state.csvFromConvert], { type: "text/csv;charset=utf-8" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "statement.csv";
      a.click();
      URL.revokeObjectURL(a.href);
      showError("");
      return;
    }
    fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: rowsForExportWithDateFormat(state.rows), delimiter: delim, decimal_sep: decSep }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.detail) { showError(data.detail); return; }
        var blob = new Blob([data.csv], { type: "text/csv;charset=utf-8" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "statement.csv";
        a.click();
        URL.revokeObjectURL(a.href);
        showError("");
      })
      .catch(function (e) {
        showError("Download failed: " + (e.message || "Unknown error"));
      });
  }

  function copyPreviewToClipboard() {
    var rows = state.rows.slice();
    if (rows.length === 0) {
      showError("No data to copy.");
      return;
    }
    var headers = ["Row#", "Date", "Account (IBAN)", "Amount", "CCY", "Description", "Ref.ID"];
    var lines = [headers.join("\t")];
    var formatIso = getFormatDatesIso();
    var dateSeparator = getDateSeparator();
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var dateStr = r.value_date || r.entry_date || "";
      var displayDate = formatDateForDisplay(parseDate(dateStr), formatIso, dateSeparator);
      var amount = r.signed_amount != null ? r.signed_amount : r.amount;
      var cells = [
        i + 1,
        displayDate,
        r.account || "",
        amount != null ? amount : "",
        r.currency || "",
        (r.cleared_description || r.description || "").substring(0, 80),
        r.reference || "",
      ];
      lines.push(cells.join("\t"));
    }
    var text = lines.join("\n");
    navigator.clipboard.writeText(text).then(function () {
      showError("");
    }, function () {
      showError("Copy failed.");
    });
  }

  function reset() {
    state.rows = [];
    state.csvFromConvert = null;
    state.convertDelimiter = null;
    state.convertDecimalSep = null;
    showError("");
    if (els.fileInput) els.fileInput.value = "";
    updateUIFromState();
  }

  function init() {
    cacheEls();
    updateUIFromState();
    if (els.fileInput) {
      els.fileInput.addEventListener("change", function () {
        var file = els.fileInput.files && els.fileInput.files[0];
        if (file) convertFile(file).catch(function (e) { showError("Request failed: " + (e.message || "Unknown error")); });
      });
      els.fileInput.addEventListener("dragover", function (e) { e.preventDefault(); e.stopPropagation(); });
      els.fileInput.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        var file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) convertFile(file).catch(function (err) { showError("Request failed: " + (err.message || "Unknown error")); });
      });
    }
    if (els.downloadBtn) els.downloadBtn.addEventListener("click", onDownloadCsv);
    if (els.resetBtn) els.resetBtn.addEventListener("click", reset);
    if (els.copyPreview) els.copyPreview.addEventListener("click", copyPreviewToClipboard);
    if (els.formatDates) els.formatDates.addEventListener("change", updateUIFromState);
    $$('input[name="date_separator"]').forEach(function (radio) {
      radio.addEventListener("change", updateUIFromState);
    });
    delegateExpandCollapse(document.body);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
