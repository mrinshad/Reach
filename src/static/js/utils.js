/**
 * Reach — UI Utilities, Dialogs, Toast Notifications, and String Formatters
 * (src/static/js/utils.js)
 */

// --- Custom Dialog System (Replaces Native Alert & Confirm) ---
function showConfirm(title, message, options = {}) {
  return new Promise((resolve) => {
    window.dialogResolver = resolve;
    const overlay = document.getElementById('customDialogOverlay');
    const titleEl = document.getElementById('dialogTitle');
    const msgEl = document.getElementById('dialogMessage');
    const confirmBtn = document.getElementById('dialogBtnConfirm');
    const cancelBtn = document.getElementById('dialogBtnCancel');
    const iconCircle = document.getElementById('dialogIconCircle');

    if (!overlay || !titleEl || !msgEl) {
      resolve(window.confirm(`${title}\n\n${message}`));
      return;
    }

    titleEl.textContent = title;
    msgEl.textContent = message;
    confirmBtn.textContent = options.confirmText || 'Confirm';
    cancelBtn.textContent = options.cancelText || 'Cancel';

    if (options.danger) {
      confirmBtn.className = 'btn btn-danger';
      iconCircle.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
      iconCircle.style.background = 'rgba(244, 63, 94, 0.15)';
    } else {
      confirmBtn.className = 'btn btn-primary';
      iconCircle.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="8"></line></svg>';
      iconCircle.style.background = 'rgba(99, 102, 241, 0.15)';
    }

    cancelBtn.style.display = options.alertOnly ? 'none' : 'inline-flex';
    overlay.classList.remove('hidden');
  });
}

function showCenterAlert(title, message, options = {}) {
  return showConfirm(title, message, {
    alertOnly: true,
    confirmText: options.confirmText || 'Dismiss',
    danger: options.danger !== undefined ? options.danger : true,
    ...options,
  });
}

function closeCustomDialog(result) {
  const overlay = document.getElementById('customDialogOverlay');
  if (overlay) overlay.classList.add('hidden');
  if (window.dialogResolver) {
    window.dialogResolver(result);
    window.dialogResolver = null;
  }
}

// --- Stacked Expandable Snackbar Notification System ---
let snackbarCounter = 0;
const activeSnackbars = new Map();

function showSnackbar({
  title,
  message = '',
  type = 'info', // 'info' | 'success' | 'warn' | 'error'
  details = null,
  duration = null,
}) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const id = `sb-${Date.now()}-${++snackbarCounter}`;

  let heading = title;
  let preview = message;
  let fullDetails = details;

  if (!heading) {
    if (type === 'error') {
      const lines = (message || '').split('\n').map((l) => l.trim()).filter(Boolean);
      if (lines.length > 1) {
        heading = lines[0].slice(0, 45);
        preview = lines.slice(1)[0] || '';
        fullDetails = message;
      } else {
        heading = 'Task Encountered an Error';
      }
    } else if (type === 'warn') {
      heading = 'Notice';
    } else if (type === 'success') {
      heading = 'Completed';
    } else {
      heading = 'Information';
    }
  }

  const hasExpandableContent = !!fullDetails && fullDetails.trim() !== preview.trim();

  let autoDismissMs = duration;
  if (autoDismissMs === null) {
    if (type === 'error') autoDismissMs = 0;
    else if (type === 'warn') autoDismissMs = 8000;
    else if (type === 'success') autoDismissMs = 4500;
    else autoDismissMs = 4000;
  }

  const icons = {
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="16 9 10 15 7 12"/></svg>`,
    warn: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  };

  const item = document.createElement('div');
  item.className = `snackbar-item snackbar-${type}`;
  item.id = id;

  item.innerHTML = `
    <div class="snackbar-header" onclick="${hasExpandableContent ? `toggleSnackbar('${id}')` : ''}">
      <div class="snackbar-icon">${icons[type] || icons.info}</div>
      <div class="snackbar-content">
        <div class="snackbar-title">${escapeHtml(heading)}</div>
        ${preview ? `<div class="snackbar-preview">${escapeHtml(preview)}</div>` : ''}
      </div>
      <div class="snackbar-actions">
        <button class="snackbar-btn snackbar-copy-btn" title="Copy message" onclick="copySnackbarText('${id}', event)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
        ${hasExpandableContent ? `<button class="snackbar-btn snackbar-toggle-btn" title="View details" onclick="event.stopPropagation(); toggleSnackbar('${id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
        </button>` : ''}
        <button class="snackbar-btn snackbar-close-btn" title="Dismiss" onclick="dismissSnackbar('${id}', event)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    </div>
    ${hasExpandableContent ? `
      <div class="snackbar-details hidden" id="details-${id}">
        <pre class="snackbar-pre">${escapeHtml(fullDetails)}</pre>
        <div class="snackbar-detail-actions">
          <button class="btn btn-secondary btn-xs" onclick="copySnackbarText('${id}', event)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>Copy Log</span>
          </button>
        </div>
      </div>
    ` : ''}
    ${autoDismissMs > 0 ? `<div class="snackbar-progress" style="animation-duration: ${autoDismissMs}ms;"></div>` : ''}
  `;

  container.appendChild(item);

  let timer = null;
  if (autoDismissMs > 0) {
    timer = setTimeout(() => dismissSnackbar(id), autoDismissMs);
  }

  const copyParts = [];
  if (heading) copyParts.push(heading);
  if (preview && preview !== heading) copyParts.push(preview);
  if (fullDetails && fullDetails !== preview) copyParts.push(fullDetails);
  const fullText = copyParts.join('\n\n').trim() || message || '';

  activeSnackbars.set(id, {
    timer,
    fullText,
  });

  const items = container.querySelectorAll('.snackbar-item');
  if (items.length > 5) {
    dismissSnackbar(items[0].id);
  }
}

function toggleSnackbar(id) {
  const item = document.getElementById(id);
  if (!item) return;
  const detailsEl = document.getElementById(`details-${id}`);
  if (!detailsEl) return;

  const isExpanded = item.classList.toggle('expanded');
  detailsEl.classList.toggle('hidden', !isExpanded);

  const itemData = activeSnackbars.get(id);
  if (itemData && itemData.timer && isExpanded) {
    clearTimeout(itemData.timer);
    itemData.timer = null;
  }
}

function dismissSnackbar(id, event) {
  if (event) event.stopPropagation();
  const item = document.getElementById(id);
  if (!item) return;

  const itemData = activeSnackbars.get(id);
  if (itemData && itemData.timer) {
    clearTimeout(itemData.timer);
  }
  activeSnackbars.delete(id);

  item.style.opacity = '0';
  item.style.transform = 'translateX(45px) scale(0.95)';
  item.style.transition = 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)';
  setTimeout(() => item.remove(), 230);
}

function copySnackbarText(id, event) {
  if (event) event.stopPropagation();
  const itemData = activeSnackbars.get(id);
  if (!itemData) return;

  const textToCopy = itemData.fullText || '';
  const btn = event.currentTarget;

  const showSuccessFeedback = () => {
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
      btn.title = 'Copied to clipboard!';
      setTimeout(() => {
        btn.innerHTML = orig;
        btn.title = 'Copy message';
      }, 1800);
    }
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(textToCopy).then(showSuccessFeedback).catch(() => {
      fallbackCopy(textToCopy, showSuccessFeedback);
    });
  } else {
    fallbackCopy(textToCopy, showSuccessFeedback);
  }
}

function fallbackCopy(text, callback) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand('copy');
    if (callback) callback();
  } catch (_) {}
  document.body.removeChild(ta);
}

function showToast(message, type = 'info') {
  showSnackbar({ message, type });
}

function showAlert(title, message, options = {}) {
  const isErr = title.toLowerCase().includes('error') || title.toLowerCase().includes('failed') || title.toLowerCase().includes('stopped');
  showSnackbar({
    title: title,
    message: (message || '').split('\n')[0],
    details: (message && (message.includes('\n') || message.length > 70)) ? message : null,
    type: isErr ? 'error' : 'warn',
  });
  if (options.centerPopup || isErr) {
    showCenterAlert(title, message, { danger: isErr });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatRelativeLabel(raw) {
  if (!raw) return '';
  const trimmed = raw.trim();
  const match = trimmed.match(/^(\d+)\s*([a-zA-Z]+)$/);
  if (!match) return trimmed;
  const num = parseInt(match[1], 10);
  const unit = match[2].toLowerCase();
  if (unit === 'h' || unit.startsWith('hr')) {
    return num === 1 ? '1 hr' : `${num} hrs`;
  }
  if (unit === 'm' || unit.startsWith('min')) {
    return num === 1 ? '1 min' : `${num} mins`;
  }
  if (unit === 'd' || unit.startsWith('day')) {
    return num === 1 ? '1 day' : `${num} days`;
  }
  if (unit === 'w' || unit.startsWith('wk') || unit.startsWith('week')) {
    return num === 1 ? '1 week' : `${num} weeks`;
  }
  if (unit === 'mo' || unit.startsWith('mon') || unit.startsWith('month')) {
    return num === 1 ? '1 mo' : `${num} mos`;
  }
  if (unit === 'y' || unit.startsWith('yr') || unit.startsWith('year')) {
    return num === 1 ? '1 yr' : `${num} yrs`;
  }
  return trimmed;
}

function formatPostDateTimeWithRelative(post) {
  if (!post) return '—';

  let baseDate = null;
  if (post.created_at) {
    baseDate = new Date(post.created_at);
  }
  if (!baseDate || isNaN(baseDate.getTime())) {
    baseDate = new Date();
  }

  const raw = (post.posted_date_raw || '').trim();
  let computedDate = new Date(baseDate.getTime());
  let relativeLabel = '';

  if (raw) {
    if (/^\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}/.test(raw)) {
      relativeLabel = '';
    } else {
      const match = raw.match(/^(\d+)\s*([a-zA-Z]+)$/);
      if (match) {
        const val = parseInt(match[1], 10);
        const unit = match[2].toLowerCase();
        let msOffset = 0;

        if (unit.startsWith('m') && !unit.startsWith('mo')) {
          msOffset = val * 60 * 1000;
        } else if (unit.startsWith('h')) {
          msOffset = val * 60 * 60 * 1000;
        } else if (unit.startsWith('d')) {
          msOffset = val * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('w')) {
          msOffset = val * 7 * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('mo')) {
          msOffset = val * 30 * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('y')) {
          msOffset = val * 365 * 24 * 60 * 60 * 1000;
        }

        if (msOffset > 0) {
          computedDate = new Date(baseDate.getTime() - msOffset);
        }
        relativeLabel = formatRelativeLabel(raw);
      } else {
        relativeLabel = raw;
      }
    }
  }

  const day = String(computedDate.getDate()).padStart(2, '0');
  const month = String(computedDate.getMonth() + 1).padStart(2, '0');
  const year = computedDate.getFullYear();

  let hours = computedDate.getHours();
  const minutes = String(computedDate.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const hoursStr = String(hours).padStart(2, '0');

  const formattedDate = `${day}/${month}/${year} ${hoursStr}:${minutes} ${ampm}`;
  if (relativeLabel) {
    return `${formattedDate} (${relativeLabel})`;
  }
  return formattedDate;
}

function formatDateTime(dateVal) {
  if (!dateVal) return '—';
  const d = new Date(dateVal);
  if (isNaN(d.getTime())) return String(dateVal);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  let hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const hoursStr = String(hours).padStart(2, '0');
  return `${day}/${month}/${year} ${hoursStr}:${minutes} ${ampm}`;
}

function formatDate(dateVal) {
  return formatDateTime(dateVal);
}

function copyEmailToClipboard(email) {
  navigator.clipboard.writeText(email).then(() => {
    showToast(`Copied: ${email}`, 'success');
  });
}

async function copyJobDescription() {
  const textEl = document.getElementById('reviewFullText');
  const text = textEl ? textEl.textContent : '';
  if (!text) {
    showToast('No job description text to copy.', 'warn');
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById('btnCopyJd');
    if (btn) {
      btn.classList.add('copied');
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>`;
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span>Copy JD</span>`;
      }, 1800);
    }
    showToast('✓ Job description copied to clipboard', 'success');
  } catch (err) {
    showAlert('Copy Failed', err.message);
  }
}

async function copyEmailDraft() {
  const subject = (document.getElementById('draftSubject')?.value || '').trim();
  const body = (document.getElementById('draftBody')?.value || '').trim();
  if (!subject && !body) {
    showToast('No draft content to copy.', 'warn');
    return;
  }
  const fullDraftText = `Subject: ${subject}\n\n${body}`;
  try {
    await navigator.clipboard.writeText(fullDraftText);
    const btn = document.getElementById('btnCopyDraft');
    if (btn) {
      btn.classList.add('copied');
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>`;
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span>Copy Email</span>`;
      }, 1800);
    }
    showToast('✓ Email draft copied to clipboard', 'success');
  } catch (err) {
    showAlert('Copy Failed', err.message);
  }
}

// Bind utilities globally
window.showConfirm = showConfirm;
window.showCenterAlert = showCenterAlert;
window.closeCustomDialog = closeCustomDialog;
window.showSnackbar = showSnackbar;
window.toggleSnackbar = toggleSnackbar;
window.dismissSnackbar = dismissSnackbar;
window.copySnackbarText = copySnackbarText;
window.showToast = showToast;
window.showAlert = showAlert;
window.escapeHtml = escapeHtml;
window.formatRelativeLabel = formatRelativeLabel;
window.formatPostDateTimeWithRelative = formatPostDateTimeWithRelative;
window.formatDateTime = formatDateTime;
window.formatDate = formatDate;
window.copyEmailToClipboard = copyEmailToClipboard;
window.copyJobDescription = copyJobDescription;
window.copyEmailDraft = copyEmailDraft;
