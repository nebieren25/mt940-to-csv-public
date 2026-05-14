/**
 * Insights dashboard: client state, scope filter, metrics, breakdown, top 5.
 * Uses same aggregation rules as src/core/insights.py (JS port).
 */
(function () {
  "use strict";

  var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function parseDate(value) {
    if (value == null || (typeof value === "string" && !value.trim())) return null;
    var s = String(value).trim();
    if (!s) return null;
    var iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    if (iso) return iso[1] + "-" + iso[2] + "-" + iso[3];
    var dmy = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})/.exec(s);
    if (dmy) {
      var d = dmy[1].padStart(2, "0");
      var m = dmy[2].padStart(2, "0");
      return dmy[3] + "-" + m + "-" + d;
    }
    return null;
  }

  function parseAmount(row) {
    var raw = row.signed_amount != null ? row.signed_amount : row.amount;
    if (raw === "" || raw == null) {
      var dc = (row.debit_credit || "").trim().toUpperCase();
      raw = row.amount || "";
      if (!raw) return 0;
      var n = parseFloat(String(raw).replace(",", "."));
      return isNaN(n) ? 0 : dc === "D" ? -n : n;
    }
    var n = parseFloat(String(raw).replace(",", "."));
    return isNaN(n) ? 0 : n;
  }

  function rowYearQuarterMonth(row) {
    var d = parseDate(row.value_date || row.entry_date);
    if (!d || d.length < 10) return [null, null, null];
    var y = parseInt(d.slice(0, 4), 10);
    var m = parseInt(d.slice(5, 7), 10);
    var q = Math.floor((m - 1) / 3) + 1;
    return [y, q, m];
  }

  function filterRowsByScope(rows, scope) {
    var wantYear = scope.year;
    var wantQuarter = scope.quarter;
    var wantMonth = scope.month;
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var yqm = rowYearQuarterMonth(r);
      var y = yqm[0], q = yqm[1], m = yqm[2];
      if (y == null) continue;
      if (wantYear != null && y !== wantYear) continue;
      if (wantQuarter != null && q !== wantQuarter) continue;
      if (wantMonth != null && m !== wantMonth) continue;
      out.push(r);
    }
    return out;
  }

  function computeMetrics(rows) {
    if (!rows.length) {
      return {
        min_date: null,
        max_date: null,
        total_income: 0,
        total_expense: 0,
        net: 0,
        total_count: 0,
        income_count: 0,
        expense_count: 0,
        avg_income_txn: 0,
        avg_expense_txn: 0,
        most_frequent_description: null
      };
    }
    var totalIncome = 0, totalExpense = 0, incomeCount = 0, expenseCount = 0;
    var incomeSum = 0, expenseSum = 0;
    var dates = [];
    var descCounts = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var amt = parseAmount(r);
      var d = parseDate(r.value_date || r.entry_date);
      if (d) dates.push(d);
      if (amt > 0) {
        totalIncome += amt;
        incomeCount++;
        incomeSum += amt;
      } else if (amt < 0) {
        totalExpense += Math.abs(amt);
        expenseCount++;
        expenseSum += Math.abs(amt);
      }
      var desc = (r.cleared_description || r.description || "").trim();
      if (desc) {
        var key = desc.toLowerCase().replace(/\s+/g, " ");
        descCounts[key] = (descCounts[key] || 0) + 1;
      }
    }
    var minDate = dates.length ? dates.reduce(function (a, b) { return a < b ? a : b; }) : null;
    var maxDate = dates.length ? dates.reduce(function (a, b) { return a > b ? a : b; }) : null;
    var mostFreq = null;
    var bestCount = 0;
    for (var k in descCounts) {
      if (descCounts[k] > bestCount) {
        bestCount = descCounts[k];
        mostFreq = k;
      }
    }
    return {
      min_date: minDate,
      max_date: maxDate,
      total_income: totalIncome,
      total_expense: totalExpense,
      net: totalIncome - totalExpense,
      total_count: rows.length,
      income_count: incomeCount,
      expense_count: expenseCount,
      avg_income_txn: incomeCount ? incomeSum / incomeCount : 0,
      avg_expense_txn: expenseCount ? expenseSum / expenseCount : 0,
      most_frequent_description: mostFreq
    };
  }

  function computeBreakdown(rows) {
    if (!rows.length) return [];
    var yearTotals = {};
    var quarterTotals = {};
    var monthTotals = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      var yqm = rowYearQuarterMonth(r);
      var y = yqm[0], q = yqm[1], m = yqm[2];
      if (y == null) continue;
      var amt = parseAmount(r);
      var inc = amt > 0 ? amt : 0;
      var exp = amt < 0 ? Math.abs(amt) : 0;
      if (!yearTotals[y]) yearTotals[y] = { inc: 0, exp: 0, count: 0 };
      yearTotals[y].inc += inc;
      yearTotals[y].exp += exp;
      yearTotals[y].count += 1;
      if (q != null) {
        var qk = y + "-" + q;
        if (!quarterTotals[qk]) quarterTotals[qk] = { inc: 0, exp: 0, count: 0 };
        quarterTotals[qk].inc += inc;
        quarterTotals[qk].exp += exp;
        quarterTotals[qk].count += 1;
      }
      if (q != null && m != null) {
        var mk = y + "-" + q + "-" + m;
        if (!monthTotals[mk]) monthTotals[mk] = { inc: 0, exp: 0, count: 0 };
        monthTotals[mk].inc += inc;
        monthTotals[mk].exp += exp;
        monthTotals[mk].count += 1;
      }
    }
    var result = [];
    var years = Object.keys(yearTotals).map(Number).sort(function (a, b) { return a - b; });
    for (var yi = 0; yi < years.length; yi++) {
      var year = years[yi];
      var yt = yearTotals[year];
      var yNet = yt.inc - yt.exp;
      var yAvg = yt.count ? (yt.inc + yt.exp) / yt.count : 0;
      result.push({
        level: 0,
        period: String(year),
        year: year,
        quarter: null,
        month: null,
        income: yt.inc,
        expense: yt.exp,
        net: yNet,
        count: yt.count,
        avg_txn: yAvg
      });
      for (var quarter = 1; quarter <= 4; quarter++) {
        var qk = year + "-" + quarter;
        var qt = quarterTotals[qk] || { inc: 0, exp: 0, count: 0 };
        var qNet = qt.inc - qt.exp;
        var qAvg = qt.count ? (qt.inc + qt.exp) / qt.count : 0;
        result.push({
          level: 1,
          period: "Q" + quarter + " " + year,
          year: year,
          quarter: quarter,
          month: null,
          income: qt.inc,
          expense: qt.exp,
          net: qNet,
          count: qt.count,
          avg_txn: qAvg
        });
        for (var month = (quarter - 1) * 3 + 1; month <= quarter * 3; month++) {
          var mk = year + "-" + quarter + "-" + month;
          var mt = monthTotals[mk] || { inc: 0, exp: 0, count: 0 };
          var mNet = mt.inc - mt.exp;
          var mAvg = mt.count ? (mt.inc + mt.exp) / mt.count : 0;
          result.push({
            level: 2,
            period: MONTH_NAMES[month - 1],
            year: year,
            quarter: quarter,
            month: month,
            income: mt.inc,
            expense: mt.exp,
            net: mNet,
            count: mt.count,
            avg_txn: mAvg
          });
        }
      }
    }
    return result;
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

  function getTop5(rows) {
    var withAmount = rows.slice().filter(function (r) {
      var a = parseAmount(r);
      return a !== 0;
    });
    withAmount.sort(function (a, b) { return parseAmount(b) - parseAmount(a); });
    var incomes = withAmount.filter(function (r) { return parseAmount(r) > 0; }).slice(0, 5);
    var expenses = withAmount.filter(function (r) { return parseAmount(r) < 0; }).slice(-5).reverse();
    return { incomes: incomes, expenses: expenses };
  }

  function formatDateShort(iso) {
    if (!iso || iso.length < 10) return "—";
    var parts = iso.slice(0, 10).split("-");
    return MONTH_NAMES[parseInt(parts[1], 10) - 1] + " " + parseInt(parts[2], 10);
  }

  function formatDateRange(from, to) {
    if (!from && !to) return "—";
    if (!from) return "— — " + (to || "—");
    if (!to) return (from || "—") + " — —";
    return from + " - " + to;
  }

  function formatMoney(n, decimalSep) {
    if (n == null || isNaN(n)) return "—";
    var s = Math.abs(n).toFixed(2);
    var sep = decimalSep || ".";
    if (sep === ",") s = s.replace(".", ",");
    var prefix = n < 0 ? "-" : "";
    return prefix + s;
  }

  function formatMoneySigned(n, decimalSep) {
    if (n == null || isNaN(n)) return "—";
    var s = Math.abs(n).toFixed(2);
    if (decimalSep === ",") s = s.replace(".", ",");
    if (n >= 0) return "+ " + s;
    return "- " + s;
  }

  function escapeHtml(s) {
    if (s == null) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  // ——— State ———
  var state = {
    files: [],
    scope: { year: null, quarter: null, month: null },
    decimalSep: ".",
    expandedYears: {},
    expandedQuarters: {}
  };

  function nextId() {
    return "f-" + Date.now() + "-" + Math.random().toString(36).slice(2, 9);
  }

  function getAllRows() {
    var out = [];
    for (var i = 0; i < state.files.length; i++) {
      for (var j = 0; j < state.files[i].rows.length; j++) {
        out.push(state.files[i].rows[j]);
      }
    }
    return out;
  }

  function getFilteredRows() {
    var rows = getAllRows();
    return filterRowsByScope(rows, state.scope);
  }

  function getUniqueYears(rows) {
    var set = {};
    for (var i = 0; i < rows.length; i++) {
      var d = parseDate(rows[i].value_date || rows[i].entry_date);
      if (d && d.length >= 4) set[d.slice(0, 4)] = true;
    }
    return Object.keys(set).map(Number).sort(function (a, b) { return a - b; });
  }

  function updateScopeControls() {
    var yearSelect = document.getElementById("insights-year-select");
    var quarterWrap = document.getElementById("insights-scope-quarter-wrap");
    var quarterSelect = document.getElementById("insights-quarter-select");
    var monthWrap = document.getElementById("insights-scope-month-wrap");
    var monthSelect = document.getElementById("insights-month-select");
    var rows = getAllRows();
    var years = getUniqueYears(rows);

    if (!yearSelect) return;
    var currentYear = yearSelect.value ? parseInt(yearSelect.value, 10) : null;
    yearSelect.innerHTML = '<option value="">All Time</option>';
    years.forEach(function (y) {
      var opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      if (y === currentYear) opt.selected = true;
      yearSelect.appendChild(opt);
    });

    if (state.scope.year == null) {
      quarterWrap.classList.add("opacity-50", "pointer-events-none");
      quarterWrap.classList.remove("cursor-not-allowed");
      quarterSelect.disabled = true;
      monthWrap.classList.add("opacity-50", "pointer-events-none");
      monthSelect.disabled = true;
    } else {
      quarterWrap.classList.remove("opacity-50", "pointer-events-none");
      quarterSelect.disabled = false;
      if (state.scope.quarter == null) {
        monthWrap.classList.add("opacity-50", "pointer-events-none");
        monthSelect.disabled = true;
      } else {
        monthWrap.classList.remove("opacity-50", "pointer-events-none");
        monthSelect.disabled = false;
      }
    }
  }

  function getScopeLabel() {
    var s = state.scope;
    if (s.year == null) return "Scope: All Data";
    if (s.quarter == null) return "Scope: " + s.year;
    if (s.month == null) return "Scope: " + s.year + " / Q" + s.quarter;
    return "Scope: " + s.year + " / Q" + s.quarter + " / " + MONTH_NAMES[s.month - 1];
  }

  function renderFilesList() {
    var list = document.getElementById("insights-files-list");
    var countEl = document.getElementById("insights-files-count");
    if (!list || !countEl) return;
    list.innerHTML = "";
    state.files.forEach(function (f) {
      var row = document.createElement("div");
      row.className = "flex items-center justify-between p-2 hover:bg-slate-50 dark:hover:bg-slate-800 rounded";
      var fromTo = formatDateRange(f.min_date, f.max_date);
      if (fromTo === "—" && f.min_date) fromTo = f.min_date + " - " + (f.max_date || f.min_date);
      row.innerHTML =
        '<div><p class="text-xs font-medium text-slate-800 dark:text-white">' + escapeHtml(f.filename) + "</p>" +
        '<p class="text-[10px] text-slate-400">' + f.row_count + " rows • " + escapeHtml(fromTo) + "</p></div>" +
        '<button type="button" class="insights-remove-file text-slate-400 hover:text-rose-500" data-file-id="' + escapeHtml(f.id) + '"><span class="material-icons text-sm">close</span></button>';
      list.appendChild(row);
    });
    countEl.textContent = "Files loaded: " + state.files.length;

    list.querySelectorAll(".insights-remove-file").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-file-id");
        state.files = state.files.filter(function (f) { return f.id !== id; });
        renderFilesList();
        refreshAll();
      });
    });
  }

  function renderMetrics(metrics, currencyWarning) {
    var sep = state.decimalSep;
    var set = function (id, text) {
      var el = document.getElementById(id);
      if (el) el.textContent = text;
    };
    set("insights-date-range", formatDateRange(metrics.min_date, metrics.max_date));
    set("insights-avg-inc", "Inc: " + (metrics.income_count ? formatMoney(metrics.avg_income_txn, sep) : "—"));
    set("insights-avg-exp", "Exp: " + (metrics.expense_count ? formatMoney(metrics.avg_expense_txn, sep) : "—"));
    set("insights-total-income", "+ " + formatMoney(metrics.total_income, sep));
    set("insights-total-income-count", "Across " + metrics.income_count + " transactions");
    set("insights-total-expense", "- " + formatMoney(metrics.total_expense, sep));
    set("insights-total-expense-count", "Across " + metrics.expense_count + " transactions");
    set("insights-net", formatMoney(metrics.net, sep));
    set("insights-txn-total", String(metrics.total_count));
    set("insights-txn-in", "In: " + metrics.income_count);
    set("insights-txn-out", "Out: " + metrics.expense_count);

    var warn = document.getElementById("insights-currency-warning");
    if (warn) {
      warn.classList.toggle("hidden", !currencyWarning);
    }
  }

  function renderBreakdown(breakdownRows) {
    var tbody = document.getElementById("insights-breakdown-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!breakdownRows.length) {
      var tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="6" class="px-4 py-6 text-center text-slate-400">No data</td>';
      tbody.appendChild(tr);
      return;
    }

    var sep = state.decimalSep;
    breakdownRows.forEach(function (row, idx) {
      var tr = document.createElement("tr");
      tr.setAttribute("data-level", String(row.level));
      tr.setAttribute("data-year", String(row.year));
      if (row.quarter != null) tr.setAttribute("data-quarter", String(row.quarter));
      if (row.month != null) tr.setAttribute("data-month", String(row.month));

      var isYear = row.level === 0;
      var isQuarter = row.level === 1;
      var isMonth = row.level === 2;
      var expanded = isYear && state.expandedYears[row.year];
      var qExpanded = isQuarter && state.expandedQuarters[row.year + "-" + row.quarter];
      var hidden = isQuarter && !state.expandedYears[row.year];
      if (isMonth) hidden = !state.expandedQuarters[row.year + "-" + row.quarter];

      if (hidden) tr.classList.add("hidden");

      var periodCell = document.createElement("td");
      periodCell.className = "px-4 py-2 font-display text-slate-700 dark:text-slate-300";
      if (isYear) {
        periodCell.className = "px-4 py-3 font-display font-semibold text-slate-900 dark:text-white flex items-center gap-2";
        periodCell.innerHTML = '<span class="material-icons text-base text-slate-400 breakdown-chevron">play_arrow</span> ' + escapeHtml(row.period);
        periodCell.style.paddingLeft = "1rem";
      } else if (isQuarter) {
        periodCell.className = "px-4 py-2 font-display font-medium text-slate-700 dark:text-slate-300 pl-10 flex items-center gap-2";
        periodCell.innerHTML = '<span class="material-icons text-base text-slate-400 breakdown-chevron">play_arrow</span> ' + escapeHtml(row.period);
      } else {
        periodCell.className = "px-4 py-2 font-display text-slate-600 dark:text-slate-400 pl-16";
        periodCell.textContent = row.period;
      }

      if (isYear) tr.classList.add("bg-slate-50/80", "dark:bg-slate-800/40", "hover:bg-slate-100", "dark:hover:bg-slate-800", "cursor-pointer", "breakdown-year-row");
      if (isQuarter) tr.classList.add("bg-white", "dark:bg-card-dark", "hover:bg-slate-50", "dark:hover:bg-slate-800/30", "cursor-pointer", "breakdown-quarter-row");
      if (isMonth) tr.classList.add("bg-slate-50/30", "dark:bg-slate-800/10");

      tr.appendChild(periodCell);
      tr.appendChild(createCell(formatMoney(row.income, sep), "text-emerald-600 dark:text-emerald-400", row.level));
      tr.appendChild(createCell("-" + formatMoney(row.expense, sep), "text-rose-600 dark:text-rose-400", row.level));
      tr.appendChild(createCell(formatMoney(row.net, sep), "text-slate-700 dark:text-slate-300", row.level));
      tr.appendChild(createCell(String(row.count), "text-slate-500", row.level, true));
      tr.appendChild(createCell(row.count ? formatMoney(row.avg_txn, sep) : "—", "text-slate-500", row.level));

      tbody.appendChild(tr);
    });

    tbody.querySelectorAll(".breakdown-year-row").forEach(function (tr) {
      tr.addEventListener("click", function () {
        var y = parseInt(tr.getAttribute("data-year"), 10);
        state.expandedYears[y] = !state.expandedYears[y];
        renderBreakdown(computeBreakdown(getFilteredRows()));
      });
    });
    tbody.querySelectorAll(".breakdown-quarter-row").forEach(function (tr) {
      tr.addEventListener("click", function () {
        var y = parseInt(tr.getAttribute("data-year"), 10);
        var q = parseInt(tr.getAttribute("data-quarter"), 10);
        var k = y + "-" + q;
        state.expandedQuarters[k] = !state.expandedQuarters[k];
        renderBreakdown(computeBreakdown(getFilteredRows()));
      });
    });

    tbody.querySelectorAll(".breakdown-chevron").forEach(function (chevron, i) {
      var tr = chevron.closest("tr");
      if (!tr) return;
      var level = parseInt(tr.getAttribute("data-level"), 10);
      var isExpanded = level === 0 && state.expandedYears[parseInt(tr.getAttribute("data-year"), 10)] ||
        level === 1 && state.expandedQuarters[tr.getAttribute("data-year") + "-" + tr.getAttribute("data-quarter")];
      chevron.style.transform = isExpanded ? "rotate(90deg)" : "rotate(0deg)";
    });
  }

  function createCell(text, colorClass, level, center) {
    var td = document.createElement("td");
    td.className = "px-2 py-2 text-right font-mono " + colorClass;
    if (level === 0) td.className = "px-2 py-3 text-right font-bold " + colorClass;
    if (center) td.classList.add("text-center");
    td.textContent = text;
    return td;
  }

  function renderTop5(rows) {
    var top5 = getTop5(rows);
    var sep = state.decimalSep;
    function renderList(ulId, list, sign) {
      var ul = document.getElementById(ulId);
      if (!ul) return;
      ul.innerHTML = "";
      list.forEach(function (r) {
        var amt = parseAmount(r);
        var li = document.createElement("li");
        li.className = "px-4 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors flex justify-between items-center group";
        var desc = (r.cleared_description || r.description || "").trim();
        if (desc.length > 40) desc = desc.slice(0, 37) + "...";
        var dateStr = formatDateShort(r.value_date || r.entry_date);
        li.innerHTML =
          '<div class="min-w-0 pr-2"><p class="text-xs font-medium text-slate-900 dark:text-white truncate">' + escapeHtml(desc || "—") + "</p>" +
          '<p class="text-[10px] text-slate-400 font-mono">' + escapeHtml(dateStr) + "</p></div>" +
          '<span class="text-xs font-bold font-mono ' + (sign > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400") + '">' +
          (sign > 0 ? "+" : "") + formatMoney(amt, sep) + "</span>";
        ul.appendChild(li);
      });
    }
    renderList("insights-top5-incomes", top5.incomes, 1);
    renderList("insights-top5-expenses", top5.expenses, -1);
  }

  function refreshAll() {
    var rows = getFilteredRows();
    var metrics = computeMetrics(rows);
    var breakdown = computeBreakdown(rows);
    var currencyWarning = checkCurrencies(getAllRows()) === "mixed";

    updateScopeControls();
    var labelEl = document.getElementById("insights-scope-label");
    if (labelEl) labelEl.textContent = getScopeLabel();
    renderMetrics(metrics, currencyWarning);
    renderBreakdown(breakdown);
    renderTop5(rows);
  }

  function uploadFile(file) {
    var fd = new FormData();
    fd.append("file", file);
    fd.append("encoding", "utf-8");
    fd.append("delimiter", ",");
    fd.append("decimal_sep", state.decimalSep);
    return fetch("/api/convert", { method: "POST", body: fd }).then(function (r) { return r.json(); });
  }

  function addFile(file, apiResult) {
    if (!apiResult || !apiResult.success || !apiResult.rows) return;
    var rows = apiResult.rows;
    var summary = apiResult.summary;
    var minDate = summary && summary.date_range && summary.date_range.from ? summary.date_range.from : null;
    var maxDate = summary && summary.date_range && summary.date_range.to ? summary.date_range.to : null;
    if (!minDate && rows.length) {
      var first = parseDate(rows[0].value_date || rows[0].entry_date);
      var last = first;
      for (var i = 1; i < rows.length; i++) {
        var d = parseDate(rows[i].value_date || rows[i].entry_date);
        if (d) { if (!minDate || d < minDate) minDate = d; if (d > last) last = d; }
      }
      if (!maxDate) maxDate = last;
    }
    state.files.push({
      id: nextId(),
      filename: file.name,
      row_count: rows.length,
      min_date: minDate,
      max_date: maxDate,
      rows: rows
    });
    renderFilesList();
    refreshAll();
  }

  function init() {
    var fileInput = document.getElementById("insights-file-input");
    var importBtn = document.getElementById("insights-import-btn");
    var exportBtn = document.getElementById("insights-export-btn");
    var resetBtn = document.getElementById("insights-reset");
    var yearSelect = document.getElementById("insights-year-select");
    var quarterSelect = document.getElementById("insights-quarter-select");
    var monthSelect = document.getElementById("insights-month-select");

    if (importBtn && fileInput) {
      importBtn.addEventListener("click", function () { fileInput.click(); });
      fileInput.addEventListener("change", function () {
        var files = fileInput.files;
        if (!files || !files.length) return;
        var chain = Promise.resolve();
        for (var i = 0; i < files.length; i++) {
          (function (file) {
            chain = chain.then(function () {
              return uploadFile(file).then(function (data) {
                addFile(file, data);
              });
            });
          })(files[i]);
        }
        chain.then(function () {
          fileInput.value = "";
        }).catch(function (err) {
          console.error("Upload error", err);
        });
      });
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        var rows = getFilteredRows();
        var metrics = computeMetrics(rows);
        var breakdown = computeBreakdown(rows);
        var payload = {
          scope: getScopeLabel(),
          metrics: metrics,
          breakdown_row_count: breakdown.length,
          exported_at: new Date().toISOString()
        };
        var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "insights-summary.json";
        a.click();
        URL.revokeObjectURL(a.href);
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        state.scope = { year: null, quarter: null, month: null };
        if (yearSelect) yearSelect.value = "";
        if (quarterSelect) quarterSelect.value = "";
        if (monthSelect) monthSelect.value = "";
        state.expandedYears = {};
        state.expandedQuarters = {};
        updateScopeControls();
        refreshAll();
      });
    }

    function onScopeChange() {
      state.scope = {
        year: yearSelect && yearSelect.value ? parseInt(yearSelect.value, 10) : null,
        quarter: quarterSelect && quarterSelect.value ? parseInt(quarterSelect.value, 10) : null,
        month: monthSelect && monthSelect.value ? parseInt(monthSelect.value, 10) : null
      };
      var quarterWrap = document.getElementById("insights-scope-quarter-wrap");
      var monthWrap = document.getElementById("insights-scope-month-wrap");
      if (state.scope.year == null) {
        quarterWrap.classList.add("opacity-50", "pointer-events-none");
        quarterSelect.disabled = true;
        monthWrap.classList.add("opacity-50", "pointer-events-none");
        monthSelect.disabled = true;
      } else {
        quarterWrap.classList.remove("opacity-50", "pointer-events-none");
        quarterSelect.disabled = false;
        if (state.scope.quarter == null) {
          monthWrap.classList.add("opacity-50", "pointer-events-none");
          monthSelect.disabled = true;
        } else {
          monthWrap.classList.remove("opacity-50", "pointer-events-none");
          monthSelect.disabled = false;
        }
      }
      refreshAll();
    }

    if (yearSelect) yearSelect.addEventListener("change", onScopeChange);
    if (quarterSelect) quarterSelect.addEventListener("change", onScopeChange);
    if (monthSelect) monthSelect.addEventListener("change", onScopeChange);

    refreshAll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
