/**
 * MT940 UI – API wiring for web-ui-1 and web-ui-2.
 * Expects: file input, encoding/delimiter/decimal_sep controls, tbody[data-mt940-tbody], Download CSV button.
 */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function getEncoding() {
    var el = $('select[name="encoding"]') || $('#encoding');
    return el ? el.value : 'utf-8';
  }
  function getDelimiter() {
    var radio = $('input[name="delimiter"]:checked');
    if (radio) return radio.value;
    var sel = $('select[name="delimiter"]') || $('#delimiter');
    if (sel) return sel.value === 'tab' ? '\\t' : (sel.value || ',');
    return ',';
  }
  function getDecimalSep() {
    var el = $('select[name="decimal_sep"]') || $('#decimal_sep');
    return el ? el.value : ',';
  }

  var currentRows = [];
  var currentAccount = '';

  function showError(msg) {
    var box = $('#mt940-error');
    if (!box) return;
    box.textContent = msg || '';
    box.style.display = msg ? 'block' : 'none';
  }

  function isoToDDMMYYYY(iso) {
    if (!iso || iso.length < 10) return iso || '';
    var parts = iso.substring(0, 10).split('-');
    if (parts.length !== 3) return iso;
    return parts[2] + '-' + parts[1] + '-' + parts[0];
  }

  function formatAmount(num, decimalSep) {
    if (num == null || isNaN(num)) return '';
    var s = Number(num).toFixed(2);
    return decimalSep === ',' ? s.replace('.', ',') : s;
  }

  function formatAmountWithThousands(num, decimalSep) {
    if (num == null || isNaN(num)) return '';
    var n = Number(num);
    var s = Math.abs(n).toFixed(2);
    var parts = s.split('.');
    var intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, decimalSep === ',' ? '.' : ',');
    var decPart = parts[1] || '00';
    return intPart + (decimalSep === ',' ? ',' : '.') + decPart;
  }

  function formatSignedAmount(num, decimalSep, forceSign) {
    var raw = formatAmount(num == null ? 0 : Math.abs(num), decimalSep);
    if (!raw) return raw;
    var n = Number(num);
    if (forceSign && n >= 0) return '+' + raw;
    if (n < 0) return '-' + raw;
    return raw;
  }

  function renderSummary(summary, decimalSep) {
    var container = $('#mt940-summary');
    if (!container) return;
    if (!summary) {
      container.style.display = 'none';
      return;
    }
    var dr = summary.date_range || {};
    var fromStr = isoToDDMMYYYY(dr.from);
    var toStr = isoToDDMMYYYY(dr.to);
    container.style.display = 'block';
    var sep = decimalSep || getDecimalSep();
    var fromEl = container.querySelector('[data-summary-date-from]');
    var toEl = container.querySelector('[data-summary-date-to]');
    if (fromEl) fromEl.textContent = fromStr || '—';
    if (toEl) toEl.textContent = toStr || '—';
    var incomeEl = container.querySelector('[data-summary-total-income]');
    var expenseEl = container.querySelector('[data-summary-total-expense]');
    var netEl = container.querySelector('[data-summary-net-change]');
    if (incomeEl) incomeEl.textContent = (summary.total_income > 0 ? '+ ' : '') + formatAmount(summary.total_income, sep);
    if (expenseEl) expenseEl.textContent = (summary.total_expense > 0 ? '- ' : '') + formatAmount(summary.total_expense, sep);
    if (netEl) netEl.textContent = formatSignedAmount(summary.net_change, sep, true);
    var totalCountEl = container.querySelector('[data-summary-total-count]');
    var incomeCountEl = container.querySelector('[data-summary-income-count]');
    var expenseCountEl = container.querySelector('[data-summary-expense-count]');
    if (totalCountEl) totalCountEl.textContent = summary.total_count;
    if (incomeCountEl) incomeCountEl.textContent = summary.income_count;
    if (expenseCountEl) expenseCountEl.textContent = summary.expense_count;
    var yearlyTbody = container.querySelector('[data-summary-yearly-tbody]');
    if (yearlyTbody && summary.yearly_breakdown && summary.yearly_breakdown.length) {
      yearlyTbody.innerHTML = '';
      summary.yearly_breakdown.forEach(function (row) {
        var incStr = row.income > 0 ? '+' + formatAmountWithThousands(row.income, sep) : '0';
        var expStr = row.expense > 0 ? '-' + formatAmountWithThousands(row.expense, sep) : '0';
        var tr = document.createElement('tr');
        tr.className = 'text-slate-800 dark:text-slate-200';
        tr.innerHTML =
          '<td class="py-1 text-left font-mono">' + escapeHtml(row.year) + '</td>' +
          '<td class="py-1 text-right font-mono text-green-600 dark:text-green-400">' + escapeHtml(incStr) + '</td>' +
          '<td class="py-1 text-right font-mono text-red-500 dark:text-red-400">' + escapeHtml(expStr) + '</td>';
        yearlyTbody.appendChild(tr);
      });
    } else if (yearlyTbody) {
      yearlyTbody.innerHTML = '';
    }
  }

  function renderPreview(rows) {
    var tbody = $('tbody[data-mt940-tbody]');
    if (!tbody) return;
    tbody.innerHTML = '';
    rows.forEach(function (row, i) {
      var tr = document.createElement('tr');
      tr.className = 'hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors';
      var amount = row.signed_amount || row.amount || '';
      var amountClass = (amount + '').indexOf('-') === 0
        ? 'text-red-500 dark:text-red-400'
        : 'text-green-600 dark:text-green-400';
      var description = (row.cleared_description || row.description || '').substring(0, 80);
      var cells = [
        (i + 1).toString(),
        row.value_date || row.entry_date || '',
        row.account || '',
        description,
        amount,
        row.currency || '',
        row.reference || ''
      ];
      tr.innerHTML =
        '<td class="px-6 py-3 text-slate-400">' + escapeHtml(cells[0]) + '</td>' +
        '<td class="px-6 py-3 text-slate-700 dark:text-slate-300">' + escapeHtml(cells[1]) + '</td>' +
        '<td class="px-6 py-3 text-slate-700 dark:text-slate-300">' + escapeHtml(cells[2]) + '</td>' +
        '<td class="px-6 py-3 text-slate-600 dark:text-slate-400 truncate max-w-[200px]">' + escapeHtml(cells[3]) + '</td>' +
        '<td class="px-6 py-3 text-right font-medium ' + amountClass + '">' + escapeHtml(cells[4]) + '</td>' +
        '<td class="px-6 py-3 text-slate-500">' + escapeHtml(cells[5]) + '</td>' +
        '<td class="px-6 py-3 text-slate-500">' + escapeHtml(cells[6]) + '</td>';
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function updateFooterCount(n) {
    var el = $('#mt940-row-count');
    if (el) el.textContent = n;
  }

  /**
   * Convert a single file via POST /api/convert. Returns a Promise that resolves to the JSON response.
   * options: { encoding?, delimiter?, decimal_sep? } (defaults from DOM or utf-8, comma, comma).
   * Exposed as window.MT940API.convert for use by Insights page.
   */
  function convertFile(file, options) {
    options = options || {};
    var fd = new FormData();
    fd.append('file', file);
    fd.append('encoding', options.encoding != null ? options.encoding : getEncoding());
    fd.append('delimiter', (options.delimiter != null ? options.delimiter : getDelimiter()).replace(/\\t/g, '\t'));
    fd.append('decimal_sep', options.decimal_sep != null ? options.decimal_sep : getDecimalSep());
    return fetch('/api/convert', { method: 'POST', body: fd }).then(function (r) { return r.json(); });
  }

  function onFileSelected(fileInput) {
    var file = fileInput && fileInput.files && fileInput.files[0];
    if (!file) return;
    showError('');
    convertFile(file, {
      encoding: getEncoding(),
      delimiter: getDelimiter(),
      decimal_sep: getDecimalSep()
    })
      .then(function (data) {
        if (!data) return;
        if (data.detail && !data.success) {
          showError(data.detail || 'Request failed.');
          currentRows = [];
          renderPreview([]);
          updateFooterCount(0);
          renderSummary(null);
          return;
        }
        if (!data.success) {
          showError(data.detail || 'No transactions found.');
          currentRows = [];
          renderPreview([]);
          updateFooterCount(0);
          renderSummary(null);
          return;
        }
        currentRows = data.rows || [];
        currentAccount = data.account || '';
        renderPreview(currentRows);
        updateFooterCount(data.truncated ? data.total_rows + ' (showing ' + data.row_count + ')' : data.row_count);
        renderSummary(data.summary || null, getDecimalSep());
      })
      .catch(function (e) {
        showError('Request failed: ' + (e.message || 'Unknown error'));
        currentRows = [];
        renderSummary(null);
      });
  }

  function onDownloadCsv() {
    if (currentRows.length === 0) {
      showError('No data to download. Upload an MT940 or CSV file first.');
      return;
    }
    var delimiter = getDelimiter().replace(/\\t/g, '\t');
    var decimalSep = getDecimalSep();
    fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: currentRows, delimiter: delimiter, decimal_sep: decimalSep })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.detail) { showError(data.detail); return; }
        var blob = new Blob([data.csv], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'statement.csv';
        a.click();
        URL.revokeObjectURL(a.href);
        showError('');
      })
      .catch(function (e) {
        showError('Download failed: ' + (e.message || 'Unknown error'));
      });
  }

  function init() {
    var fileInput = $('input[type="file"]');
    if (fileInput) {
      fileInput.addEventListener('change', function () { onFileSelected(fileInput); });
    }
    $$('button').forEach(function (btn) {
      if (btn.textContent.indexOf('Download CSV') !== -1) {
        btn.addEventListener('click', onDownloadCsv);
      }
      if (btn.textContent.trim() === 'Reset') {
        btn.addEventListener('click', function () {
          currentRows = [];
          renderPreview([]);
          updateFooterCount(0);
          renderSummary(null);
          showError('');
          if (fileInput) fileInput.value = '';
        });
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.MT940API = { convert: convertFile };
})();
