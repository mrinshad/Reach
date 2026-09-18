/**
 * Reach — Job Outreach Automation Client Application
 */

const state = {
  activeTab: 'tabDiscovered',
  expFilter: 'ALL',
  categoryFilter: 'EMAIL_OUTREACH',
  genStatusFilter: 'PENDING',
  sourceFilter: 'ALL',
  othersFilter: 'ALL',
  pendingCancelPostId: null,
  searchQuery: '',
  searchReview: '',
  searchSent: '',
  page: 1,
  limit: 25,
  total: 0,
  posts: [],
  selectedIds: new Set(),
  reviewPosts: [],
  activeReviewPost: null,
  sentPosts: [],
  sentPage: 1,
  sentLimit: 25,
  sentTotal: 0,
  config: {},
  health: {},
  pollingTimer: null,
  healthTimer: null,
  showLogs: false,
  awaitingSentPost: null,
  analyticsDays: 30,
  analyticsData: null,
  charts: {},
};

// --- Custom Dialog System (Replaces Native Alert & Confirm) ---
let dialogResolver = null;

function showConfirm(title, message, options = {}) {
  return new Promise((resolve) => {
    dialogResolver = resolve;
    const overlay = document.getElementById('customDialogOverlay');
    const titleEl = document.getElementById('dialogTitle');
    const msgEl = document.getElementById('dialogMessage');
    const confirmBtn = document.getElementById('dialogBtnConfirm');
    const cancelBtn = document.getElementById('dialogBtnCancel');
    const iconCircle = document.getElementById('dialogIconCircle');

    titleEl.textContent = title;
    msgEl.textContent = message;
    confirmBtn.textContent = options.confirmText || 'Confirm';
    cancelBtn.textContent = options.cancelText || 'Cancel';

    if (options.danger) {
      confirmBtn.className = 'btn btn-danger';
      iconCircle.textContent = '⚠️';
      iconCircle.style.background = 'rgba(244, 63, 94, 0.15)';
    } else {
      confirmBtn.className = 'btn btn-primary';
      iconCircle.textContent = '⚡';
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
    ...options
  });
}

function closeCustomDialog(result) {
  const overlay = document.getElementById('customDialogOverlay');
  overlay.classList.add('hidden');
  if (dialogResolver) {
    dialogResolver(result);
    dialogResolver = null;
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

  // Derive heading & preview if not explicitly provided
  if (!heading) {
    if (type === 'error') {
      const lines = (message || '').split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length > 1) {
        heading = lines[0].slice(0, 45);
        preview = lines.slice(1)[0] || '';
        fullDetails = message;
      } else if (message && message.includes(':')) {
        const parts = message.split(':');
        heading = parts[0].trim();
        preview = parts.slice(1).join(':').trim();
        if (message.length > 70) fullDetails = message;
      } else {
        heading = 'Action Error';
        preview = message;
      }
    } else if (type === 'success') {
      heading = 'Success';
      preview = (message || '').replace(/^✓\s*/, '');
    } else if (type === 'warn') {
      heading = 'Notice';
      preview = message;
    } else {
      heading = 'Update';
      preview = message;
    }
  }

  // If text is long and no details given, preserve full text in expandable section
  if (!fullDetails && message && message.length > 70) {
    fullDetails = message;
  }

  const hasDetails = Boolean(fullDetails);

  // SVG Icons
  let iconSvg = '';
  if (type === 'error') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  } else if (type === 'success') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  } else if (type === 'warn') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
  } else {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
  }

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const snackbarEl = document.createElement('div');
  snackbarEl.className = `snackbar-item snackbar-${type} ${hasDetails ? 'has-details' : ''}`;
  snackbarEl.id = id;

  snackbarEl.innerHTML = `
    <div class="snackbar-header" onclick="toggleSnackbar('${id}')" title="${hasDetails ? 'Click to expand/collapse details' : ''}">
      <div class="snackbar-icon">${iconSvg}</div>
      <div class="snackbar-titles">
        <span class="snackbar-heading">${escapeHtml(heading)}</span>
        ${preview ? `<span class="snackbar-preview">${escapeHtml(preview)}</span>` : ''}
      </div>
      <div class="snackbar-controls">
        ${
          hasDetails
            ? `<span class="snackbar-expand-icon" title="Toggle details">
                 <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
               </span>`
            : ''
        }
        <button class="snackbar-close" onclick="dismissSnackbar('${id}', event)" title="Dismiss">×</button>
      </div>
    </div>
    ${
      hasDetails
        ? `<div class="snackbar-details hidden" id="details-${id}">
             <div class="snackbar-details-content">
               <pre class="snackbar-pre">${escapeHtml(fullDetails)}</pre>
             </div>
             <div class="snackbar-details-footer">
               <button class="btn btn-outline btn-xs" onclick="copySnackbarText('${id}', event)">
                 <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                 <span>Copy Details</span>
               </button>
               <span class="snackbar-timestamp">${timeStr}</span>
             </div>
           </div>`
        : ''
    }
  `;

  activeSnackbars.set(id, {
    element: snackbarEl,
    fullText: fullDetails || `${heading}: ${preview}`,
    timer: null,
  });

  container.appendChild(snackbarEl);

  // Auto-dismiss timeout: errors stay longer (14s) or until dismissed; success/info 6s
  const autoTimeout = duration !== null ? duration : (type === 'error' ? 14000 : 6000);
  if (autoTimeout > 0) {
    const timer = setTimeout(() => dismissSnackbar(id), autoTimeout);
    activeSnackbars.get(id).timer = timer;

    // Pause on hover
    snackbarEl.addEventListener('mouseenter', () => {
      const itemData = activeSnackbars.get(id);
      if (itemData && itemData.timer) {
        clearTimeout(itemData.timer);
        itemData.timer = null;
      }
    });

    snackbarEl.addEventListener('mouseleave', () => {
      const itemData = activeSnackbars.get(id);
      if (itemData && !itemData.timer && !snackbarEl.classList.contains('expanded')) {
        itemData.timer = setTimeout(() => dismissSnackbar(id), 3000);
      }
    });
  }

  // Keep max 5 stacked snackbars
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

  // When expanded, stop timer so user can read comfortably
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

  navigator.clipboard.writeText(itemData.fullText).then(() => {
    const btn = event.currentTarget;
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `<span>✓ Copied</span>`;
      setTimeout(() => { btn.innerHTML = orig; }, 1600);
    }
  });
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

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();
  fetchHealth();
  fetchScrapers();
  pollTaskStatus();
  state.healthTimer = setInterval(fetchHealth, 30000);
});

// --- Tab Switching ---
function switchTab(tabId) {
  state.activeTab = tabId;

  document.getElementById('btnTabDiscovered').classList.toggle('active', tabId === 'tabDiscovered');
  document.getElementById('btnTabReview').classList.toggle('active', tabId === 'tabReview');
  document.getElementById('btnTabSent').classList.toggle('active', tabId === 'tabSent');
  const btnAnalytics = document.getElementById('btnTabAnalytics');
  if (btnAnalytics) btnAnalytics.classList.toggle('active', tabId === 'tabAnalytics');

  document.getElementById('tabDiscovered').classList.toggle('hidden', tabId !== 'tabDiscovered');
  document.getElementById('tabReview').classList.toggle('hidden', tabId !== 'tabReview');
  document.getElementById('tabSent').classList.toggle('hidden', tabId !== 'tabSent');
  const panelAnalytics = document.getElementById('tabAnalytics');
  if (panelAnalytics) panelAnalytics.classList.toggle('hidden', tabId !== 'tabAnalytics');

  fetchStats();

  if (tabId === 'tabDiscovered') {
    fetchDiscoveredPosts();
  } else if (tabId === 'tabReview') {
    fetchReviewPosts();
  } else if (tabId === 'tabSent') {
    fetchSentPosts();
  } else if (tabId === 'tabAnalytics') {
    loadAnalytics(state.analyticsDays || 30);
  }
}

// --- Health Status & Indicators ---
async function fetchHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    state.health = await res.json();

    updateHealthPill('healthInfopark', state.health.infopark || { connected: true, label: 'Online' });
    updateHealthPill('healthLinkedin', state.health.linkedin);
    updateHealthPill('healthChatgpt', state.health.chatgpt);
    updateHealthPill('healthGmail', state.health.gmail);
    updateHealthPill('healthDatabase', state.health.database);

    const banner = document.getElementById('systemAlertBanner');
    const msgEl = document.getElementById('systemAlertMessage');

    if (state.health.has_issues && state.health.issues.length > 0) {
      msgEl.textContent = state.health.issues.join(' | ');
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
  } catch (err) {
    console.warn('Health check error:', err);
  }
}

function updateHealthPill(elementId, serviceData) {
  const el = document.getElementById(elementId);
  if (!el || !serviceData) return;

  el.classList.remove('ok', 'warn', 'error');
  if (serviceData.connected) {
    el.classList.add('ok');
    el.title = `${serviceData.label || 'Connected'}`;
  } else {
    el.classList.add('warn');
    el.title = `${serviceData.label || 'Not Logged In'}`;
  }
}

function dismissSystemAlert() {
  document.getElementById('systemAlertBanner').classList.add('hidden');
}

// --- Dashboard Data Loading ---
async function loadDashboardData() {
  await Promise.all([
    fetchStats(),
    fetchSettings(),
  ]);

  if (state.activeTab === 'tabDiscovered') {
    await fetchDiscoveredPosts();
  } else if (state.activeTab === 'tabReview') {
    await fetchReviewPosts();
  } else if (state.activeTab === 'tabSent') {
    await fetchSentPosts();
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const stats = await res.json();

    const discoveredTotal = stats.discovered_total !== undefined ? stats.discovered_total : stats.total_posts || 0;
    const pendingGen = stats.pending_generation || 0;
    const draftsReady = stats.emails_generated || 0;
    const othersCount = stats.others_total !== undefined ? stats.others_total : ((stats.applications_sent || 0) + (stats.rejected_total || 0));

    document.getElementById('statDiscovered').textContent = discoveredTotal;
    document.getElementById('statPending').textContent = pendingGen;
    document.getElementById('statGenerated').textContent = draftsReady;
    document.getElementById('statSent').textContent = othersCount;

    document.getElementById('countDiscovered').textContent = discoveredTotal;
    document.getElementById('countReview').textContent = draftsReady;
    document.getElementById('countSent').textContent = othersCount;

    const sentCount = stats.applications_sent || 0;
    const cancelledCount = stats.rejected_total || 0;

    const elOthersAll = document.getElementById('countOthersAll');
    if (elOthersAll) elOthersAll.textContent = othersCount;

    const elOthersSent = document.getElementById('countOthersSent');
    if (elOthersSent) elOthersSent.textContent = sentCount;

    const elOthersCancelled = document.getElementById('countOthersCancelled');
    if (elOthersCancelled) elOthersCancelled.textContent = cancelledCount;
  } catch (err) {
    console.error('Error fetching stats:', err);
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    state.config = await res.json();

    const resumePath = state.config.resume_path || '';
    const filename = resumePath.split('/').pop() || 'No Resume Selected';
    document.getElementById('resumeFileName').textContent = filename;
    document.getElementById('resumePill').title = `Active Resume: ${resumePath}`;
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

// --- Resume Replacement Upload ---
async function handleResumeUpload(files) {
  if (!files || files.length === 0) return;
  const file = files[0];

  const formData = new FormData();
  formData.append('file', file);

  showToast(`Uploading ${file.name}...`, 'info');

  try {
    const res = await fetch('/api/resume/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (res.ok) {
      showToast(`✓ Resume replaced: ${data.filename}`, 'success');
      state.config.resume_path = data.resume_path;
      document.getElementById('resumeFileName').textContent = data.filename;
      document.getElementById('settingResumePath').value = data.resume_path;
    } else {
      showAlert('Upload Error', data.detail || 'Could not upload resume.');
    }
  } catch (err) {
    showAlert('Upload Error', err.message);
  } finally {
    document.getElementById('resumeFileInput').value = '';
  }
}

// --- TAB 1: Discovered Posts (Paginated Table) ---
async function fetchDiscoveredPosts() {
  renderSkeletonRows();

  try {
    const offset = (state.page - 1) * state.limit;
    const params = new URLSearchParams({
      limit: String(state.limit),
      offset: String(offset),
      category: state.categoryFilter,
    });

    if (state.genStatusFilter && state.genStatusFilter !== 'ALL') {
      params.append('gen_status', state.genStatusFilter);
    }

    if (state.sourceFilter && state.sourceFilter !== 'ALL') {
      params.append('source', state.sourceFilter);
    }

    if (state.searchQuery) {
      params.append('search', state.searchQuery);
    }

    if (state.expFilter === 'FRESHER') {
      params.append('max_exp', '1.0');
    } else if (state.expFilter === 'MID') {
      params.append('min_exp', '1.0');
      params.append('max_exp', '3.0');
    } else if (state.expFilter === 'SENIOR') {
      params.append('min_exp', '3.0');
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();

    state.posts = data.posts || [];
    state.total = data.total || 0;

    renderPostsTable();
    renderPagination();
  } catch (err) {
    const tbody = document.getElementById('postsTableBody');
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem;">Error loading posts: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderSkeletonRows() {
  const tbody = document.getElementById('postsTableBody');
  let rowsHtml = '';
  for (let i = 0; i < 6; i++) {
    rowsHtml += `
      <tr class="skeleton-row">
        <td><div class="skeleton-bar" style="width: 18px;"></div></td>
        <td><div class="skeleton-bar" style="width: 140px;"></div></td>
        <td><div class="skeleton-bar" style="width: 80px;"></div></td>
        <td><div class="skeleton-bar" style="width: 120px;"></div></td>
        <td><div class="skeleton-bar" style="width: 220px;"></div></td>
        <td style="text-align: right;"><div class="skeleton-bar" style="width: 70px; margin-left: auto;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = rowsHtml;
}

function getSourceBadgeHtml(postUrl, isPotentialSpam = false) {
  const url = postUrl || '';
  let badge = '';
  if (url.includes('infopark.in')) {
    badge = `<span class="source-pill source-infopark" title="Source: Infopark Kochi Portal">⚡ Infopark Kochi</span>`;
  } else if (url.startsWith('manual://') || url.includes('manual')) {
    badge = `<span class="source-pill source-manual" title="Source: Manually Added">✍️ Manual</span>`;
  } else {
    badge = `<span class="source-pill source-linkedin" title="Source: LinkedIn Job Post">in LinkedIn</span>`;
  }
  if (isPotentialSpam) {
    badge += `<span class="badge-spam-warning" title="Potential Spam: Another contact email with same corporate domain already exists in database">⚠️ Potential Spam</span>`;
  }
  return badge;
}

function renderPostsTable() {
  const tbody = document.getElementById('postsTableBody');
  tbody.innerHTML = '';

  if (state.posts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 3rem; color: #64748b;">No matching jobs found. Try adjusting filters or scrape today's Infopark jobs.</td></tr>`;
    return;
  }

  state.posts.forEach((post) => {
    const tr = document.createElement('tr');
    tr.id = `row-${post.id}`;
    if (state.selectedIds.has(post.id)) tr.classList.add('selected');

    // Experience badge
    let expClass = 'badge-none';
    let expText = post.raw_experience || 'Not Stated';
    if (post.is_fresher) {
      expClass = 'badge-fresher';
      expText = 'Fresher';
    } else if (post.min_experience !== null && post.min_experience !== undefined) {
      const min = post.min_experience;
      const max = post.max_experience ? `–${post.max_experience}` : '+';
      expText = `${min}${max} yrs`;
      expClass = min < 3 ? 'badge-mid' : 'badge-senior';
    }

    // Email cell
    const primaryEmail = (post.contact_emails && post.contact_emails[0]) || '';
    const emailHtml = primaryEmail
      ? `<span class="email-copy-pill" onclick="copyEmailToClipboard('${escapeHtml(primaryEmail)}')" title="Click to copy email">
           <span>✉</span> ${escapeHtml(primaryEmail)}
         </span>`
      : `<span style="color: #64748b; font-size: 0.72rem;">—</span>`;

    const isGenerated = post.status === 'EMAIL_GENERATED';

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="table-cb" data-id="${post.id}" ${state.selectedIds.has(post.id) ? 'checked' : ''} onchange="toggleSelectPost('${post.id}', this.checked)" />
      </td>
      <td>
        <div class="recruiter-cell">
          <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
            <span class="recruiter-name">${escapeHtml(post.author_name)}</span>
            ${getSourceBadgeHtml(post.post_url, post.is_potential_spam)}
          </div>
          <span class="recruiter-headline">${escapeHtml(post.author_headline || '')}</span>
        </div>
      </td>
      <td>
        <span class="pill-badge ${expClass}">${escapeHtml(expText)}</span>
      </td>
      <td>
        ${emailHtml}
      </td>
      <td>
        <div class="table-snippet" onclick="openPostModal('${post.id}')" title="Click to view full job description">
          ${escapeHtml(post.full_text)}
        </div>
      </td>
      <td style="text-align: right;">
        <div class="table-actions">
          ${
            post.post_url && !post.post_url.startsWith('manual://')
              ? `<a href="${post.post_url}" target="_blank" class="icon-btn sm" title="Open source page (${post.post_url.includes('infopark.in') ? 'Infopark' : 'LinkedIn'})">
                   <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                 </a>`
              : ''
          }
          ${
            post.status === 'SENT'
              ? `<span class="pill-badge" style="background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.25); font-size: 0.72rem; padding: 0.2rem 0.5rem;">✓ Sent</span>
                 <button class="btn btn-outline btn-sm" onclick="switchTab('tabSent')" title="View in Sent History">
                   <span>Sent</span>
                 </button>`
              : post.status === 'REJECTED'
                ? `<span class="badge-status-rejected" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;">🚫 Cancelled</span>
                   <button class="btn btn-outline btn-sm" onclick="revertPostToDraft('${post.id}')" title="Restore Post">
                     <span>Restore</span>
                   </button>`
                : isGenerated
                  ? `<button class="btn btn-outline btn-sm" onclick="openPostInReview('${post.id}')" title="Review Generated Draft">
                       <span>Review Draft</span>
                     </button>
                     <button class="btn btn-spam-quick" onclick="markPostAsSpam('${post.id}')" title="Mark as Spam / Scam">
                       <span>🚫 Spam</span>
                     </button>
                     <button class="btn btn-cancel-quick" onclick="cancelDiscoveredPost('${post.id}')" title="Cancel opening with reason">
                       <span>✕ Cancel</span>
                     </button>`
                  : `
                     ${primaryEmail ? `<button class="btn btn-primary btn-sm" onclick="generateSingleChatGPT('${post.id}')" title="Generate with ChatGPT"><span>Generate</span></button>` : ''}
                     <button class="btn btn-outline btn-sm" onclick="movePostToReview('${post.id}')" title="Move directly to Review & Drafts">
                       <span>Move to Review</span>
                     </button>
                     <button class="btn btn-spam-quick" onclick="markPostAsSpam('${post.id}')" title="Mark as Spam / Scam">
                       <span>🚫 Spam</span>
                     </button>
                     <button class="btn btn-cancel-quick" onclick="cancelDiscoveredPost('${post.id}')" title="Cancel opening with reason">
                       <span>✕ Cancel</span>
                     </button>
                  `
          }
        </div>
      </td>
    `;

    tbody.appendChild(tr);
  });

  updateSelectedCountUI();
}

function copyEmailToClipboard(email) {
  navigator.clipboard.writeText(email).then(() => {
    showToast(`Copied: ${email}`, 'success');
  });
}

function renderPagination() {
  const totalPages = Math.ceil(state.total / state.limit) || 1;
  const startRow = state.total === 0 ? 0 : (state.page - 1) * state.limit + 1;
  const endRow = Math.min(state.page * state.limit, state.total);

  document.getElementById('paginationInfo').textContent = `Showing ${startRow}–${endRow} of ${state.total} posts`;

  const container = document.getElementById('pageButtons');
  container.innerHTML = '';

  // Prev Button
  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '‹';
  prevBtn.disabled = state.page <= 1;
  prevBtn.onclick = () => goToPage(state.page - 1);
  container.appendChild(prevBtn);

  // Page Numbers (up to 5 pages around current)
  const startPage = Math.max(1, state.page - 2);
  const endPage = Math.min(totalPages, state.page + 2);

  for (let p = startPage; p <= endPage; p++) {
    const pBtn = document.createElement('button');
    pBtn.className = `page-btn ${p === state.page ? 'active' : ''}`;
    pBtn.textContent = String(p);
    pBtn.onclick = () => goToPage(p);
    container.appendChild(pBtn);
  }

  // Next Button
  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = '›';
  nextBtn.disabled = state.page >= totalPages;
  nextBtn.onclick = () => goToPage(state.page + 1);
  container.appendChild(nextBtn);
}

function goToPage(p) {
  state.page = p;
  fetchDiscoveredPosts();
}

function changeRowsPerPage(val) {
  state.limit = parseInt(val, 10) || 25;
  state.page = 1;
  fetchDiscoveredPosts();
}

// --- Filters & Selection ---
function setExpFilter(tier) {
  state.expFilter = tier;
  state.page = 1;
  document.querySelectorAll('#expPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.exp === tier);
  });
  fetchDiscoveredPosts();
}

function applyFilters() {
  state.categoryFilter = document.getElementById('selectCategory').value;
  const genSelect = document.getElementById('selectGenStatus');
  if (genSelect) {
    state.genStatusFilter = genSelect.value;
  }
  const srcSelect = document.getElementById('selectSource');
  if (srcSelect) {
    state.sourceFilter = srcSelect.value;
  }
  state.searchQuery = document.getElementById('inputSearch').value.trim();
  state.page = 1;
  fetchDiscoveredPosts();
}

function handleSearchKeyUp(e) {
  if (e.key === 'Enter') {
    applyFilters();
  }
}

function filterPendingGeneration() {
  switchTab('tabDiscovered');
  document.getElementById('selectCategory').value = 'EMAIL_OUTREACH';
  state.categoryFilter = 'EMAIL_OUTREACH';
  const genSelect = document.getElementById('selectGenStatus');
  if (genSelect) {
    genSelect.value = 'PENDING';
    state.genStatusFilter = 'PENDING';
  }
  const srcSelect = document.getElementById('selectSource');
  if (srcSelect) {
    srcSelect.value = 'ALL';
    state.sourceFilter = 'ALL';
  }
  setExpFilter('ALL');
}

async function movePostToReview(postId) {
  try {
    const res = await fetch(`/api/posts/${postId}/move-to-review`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast('✓ Moved to Review & Drafts', 'success');
      await loadDashboardData();
      await openPostInReview(postId);
    } else {
      showAlert('Error', data.detail || 'Could not move post to review.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function toggleSelectPost(postId, checked) {
  if (checked) {
    state.selectedIds.add(postId);
  } else {
    state.selectedIds.delete(postId);
  }
  const row = document.getElementById(`row-${postId}`);
  if (row) row.classList.toggle('selected', checked);
  updateSelectedCountUI();
}

function toggleSelectAll(checked) {
  state.posts.forEach((p) => {
    if (checked) {
      state.selectedIds.add(p.id);
    } else {
      state.selectedIds.delete(p.id);
    }
  });

  document.querySelectorAll('.table-cb').forEach((cb) => {
    cb.checked = checked;
  });

  document.querySelectorAll('.reach-table tbody tr').forEach((tr) => {
    tr.classList.toggle('selected', checked);
  });

  updateSelectedCountUI();
}

function updateSelectedCountUI() {
  const count = state.selectedIds.size;
  const batchBtn = document.getElementById('btnBatchGenerate');
  const countBadge = document.getElementById('batchCountBadge');

  if (count > 0) {
    batchBtn.classList.remove('hidden');
    countBadge.textContent = String(count);
  } else {
    batchBtn.classList.add('hidden');
  }
}

// --- TAB 2: Review & Drafts Workspace ---
let reviewSearchDebounce = null;
function handleSearchReview(val) {
  clearTimeout(reviewSearchDebounce);
  reviewSearchDebounce = setTimeout(() => {
    state.searchReview = (val || '').trim();
    fetchReviewPosts();
  }, 250);
}

async function fetchReviewPosts() {
  const container = document.getElementById('reviewQueueList');
  container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #64748b;">Loading drafts...</div>';

  try {
    const params = new URLSearchParams({
      status: 'EMAIL_GENERATED',
      limit: '100',
    });
    if (state.searchReview) {
      params.append('search', state.searchReview);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    state.reviewPosts = data.posts || [];

    document.getElementById('reviewQueueCount').textContent = String(state.reviewPosts.length);
    container.innerHTML = '';

    if (state.reviewPosts.length === 0) {
      const emptyMsg = state.searchReview
        ? `No drafts matching "${escapeHtml(state.searchReview)}" found.`
        : 'No emails generated yet. Generate emails or click Move to Review on Discovered Posts!';
      container.innerHTML = `<div style="text-align: center; padding: 2rem; font-size: 0.78rem; color: #64748b;">${emptyMsg}</div>`;
      document.getElementById('emptyReviewState').classList.remove('hidden');
      document.getElementById('workspacePanel').classList.add('hidden');
      return;
    }

    state.reviewPosts.forEach((post) => {
      const item = document.createElement('div');
      item.className = 'queue-item' + (state.activeReviewPost && state.activeReviewPost.id === post.id ? ' active' : '');
      item.id = `queue-item-${post.id}`;
      item.onclick = () => selectReviewPost(post);

      const email = (post.contact_emails && post.contact_emails[0]) || 'No email';

      item.innerHTML = `
        <span class="queue-author">${escapeHtml(post.author_name)}</span>
        <span class="queue-email">✉ ${escapeHtml(email)}</span>
      `;

      container.appendChild(item);
    });

    if (!state.activeReviewPost && state.reviewPosts.length > 0) {
      selectReviewPost(state.reviewPosts[0]);
    } else if (state.activeReviewPost) {
      const exists = state.reviewPosts.find(p => p.id === state.activeReviewPost.id);
      if (exists) selectReviewPost(exists);
      else if (state.reviewPosts.length > 0) selectReviewPost(state.reviewPosts[0]);
    }
  } catch (err) {
    container.innerHTML = `<div style="text-align: center; padding: 2rem;">Error: ${escapeHtml(err.message)}</div>`;
  }
}

function selectReviewPost(post) {
  state.activeReviewPost = post;
  state.activePostId = post ? post.id : null;

  document.querySelectorAll('.queue-item').forEach((el) => el.classList.remove('active'));
  const activeCard = document.getElementById(`queue-item-${post.id}`);
  if (activeCard) activeCard.classList.add('active');

  document.getElementById('emptyReviewState').classList.add('hidden');
  document.getElementById('workspacePanel').classList.remove('hidden');

  document.getElementById('reviewAuthorName').textContent = post.author_name;
  document.getElementById('reviewHeadline').textContent = post.author_headline || 'N/A';
  document.getElementById('reviewTargetEmail').textContent = (post.contact_emails || []).join(', ') || 'None';

  const expLabel = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
  document.getElementById('reviewExpPill').textContent = expLabel;

  document.getElementById('reviewFullText').textContent = post.full_text;

  const postLink = document.getElementById('reviewPostLink');
  if (post.post_url) {
    postLink.href = post.post_url;
    postLink.style.display = 'inline';
    if (post.post_url.includes('infopark.in')) {
      postLink.textContent = 'Infopark Kochi ↗';
    } else if (post.post_url.startsWith('manual://')) {
      postLink.textContent = 'Manual JD';
    } else {
      postLink.textContent = 'LinkedIn ↗';
    }
  } else {
    postLink.style.display = 'none';
  }

  document.getElementById('draftSubject').value = post.generated_subject || '';
  document.getElementById('draftBody').value = post.generated_body || '';

  const resume = state.config.resume_path || '';
  document.getElementById('draftResumeFilename').textContent = resume.split('/').pop() || 'None';
}

async function openPostInReview(postId) {
  switchTab('tabReview');
  let post = state.reviewPosts.find(p => p.id === postId) || state.posts.find(p => p.id === postId);
  if (!post) {
    try {
      const res = await fetch(`/api/posts/${postId}`);
      if (res.ok) post = await res.json();
    } catch (_) {}
  }
  if (post) selectReviewPost(post);
}

async function saveActiveDraftEdits() {
  if (!state.activeReviewPost) return;

  const subject = document.getElementById('draftSubject').value.trim();
  const body = document.getElementById('draftBody').value.trim();

  try {
    const res = await fetch(`/api/posts/${state.activeReviewPost.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, body }),
    });
    if (res.ok) {
      showToast('✓ Draft changes saved', 'success');
      state.activeReviewPost.generated_subject = subject;
      state.activeReviewPost.generated_body = body;
    } else {
      const err = await res.json();
      showAlert('Save Error', err.detail || 'Could not save draft.');
    }
  } catch (err) {
    showAlert('Save Error', err.message);
  }
}

async function openActivePostInGmail() {
  if (!state.activeReviewPost) return;

  const confirmed = await showConfirm(
    'Open in Gmail Draft',
    `This will launch headed Firefox, populate the compose window for ${state.activeReviewPost.author_name} with your formatted body and attached resume, and leave it open for your review. Proceed?`,
    { confirmText: 'Open Gmail' }
  );
  if (!confirmed) return;

  await saveActiveDraftEdits();

  try {
    state.awaitingSentPost = { ...state.activeReviewPost };
    const res = await fetch(`/api/open-gmail/${state.activeReviewPost.id}`, { method: 'POST' });
    if (res.ok) {
      showToast('Launching Gmail compose in headed Firefox...', 'info');
      startTaskPolling();
    } else {
      state.awaitingSentPost = null;
      const err = await res.json();
      showAlert('Gmail Error', err.detail || 'Cannot open Gmail compose.');
    }
  } catch (err) {
    state.awaitingSentPost = null;
    showAlert('Error', err.message);
  }
}

async function markActivePostSent() {
  if (!state.activeReviewPost) return;

  const confirmed = await showConfirm(
    'Mark as Sent',
    `Confirm that the application to ${state.activeReviewPost.author_name} was sent? This will move it to your Sent History.`,
    { confirmText: 'Mark Sent' }
  );
  if (!confirmed) return;

  await markPostSentById(state.activeReviewPost.id);
}

async function markPostSentById(postId) {
  try {
    const res = await fetch(`/api/posts/${postId}/mark-sent`, { method: 'POST' });
    if (res.ok) {
      showToast(`✓ Marked application as SENT`, 'success');
      if (state.activeReviewPost && state.activeReviewPost.id === postId) {
        state.activeReviewPost = null;
      }
      loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Failed to mark as sent.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function cancelActiveApplication() {
  if (!state.activeReviewPost) return;
  openCancelReasonModal(state.activeReviewPost.id, state.activeReviewPost.author_name, '', false);
}

function openCancelReasonModal(postId, candidateName, defaultReason = '', isSpamMode = false) {
  state.pendingCancelPostId = postId;
  state.isSpamCancelMode = !!isSpamMode;

  // Resolve candidate name if not provided
  if (!candidateName) {
    const p = (state.discoveredPosts || []).find(item => item.id === postId)
           || (state.posts || []).find(item => item.id === postId)
           || (state.reviewPosts || []).find(item => item.id === postId);
    candidateName = p?.author_name || '';
  }

  const titleEl = document.getElementById('cancelModalTitle');
  if (titleEl) {
    titleEl.textContent = isSpamMode ? 'Cancel Job as Spam / Scam' : 'Cancel Application';
  }

  const descEl = document.getElementById('cancelModalDesc');
  if (descEl) {
    descEl.innerHTML = isSpamMode
      ? 'This job will be cancelled and marked as <strong>Scam</strong> in your records. Confirm below or customize the comment:'
      : 'Select a ready suggestion below or type a custom comment. This will be saved to your <strong>Others</strong> history.';
  }

  const btnConfirm = document.getElementById('btnConfirmCancelModal');
  if (btnConfirm) {
    btnConfirm.textContent = isSpamMode ? '✕ Cancel as Scam' : '✕ Cancel & Discard';
  }

  const nameEl = document.getElementById('cancelModalCandidate');
  if (nameEl) nameEl.textContent = candidateName ? `for ${candidateName}` : '';

  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = defaultReason || '';
  }

  // Update chip active states
  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach(c => {
    const chipVal = c.getAttribute('data-reason') || c.textContent.trim();
    c.classList.toggle('active', !!(defaultReason && chipVal.toLowerCase() === defaultReason.toLowerCase()));
  });

  document.getElementById('cancelReasonModal')?.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
    if (defaultReason) input?.select();
  }, 50);
}

function closeCancelReasonModal() {
  state.pendingCancelPostId = null;
  state.isSpamCancelMode = false;
  document.getElementById('cancelReasonModal')?.classList.add('hidden');
}

function selectPreMadeReason(reason) {
  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = reason;
    input.focus();
  }
  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach(chip => {
    const chipVal = chip.getAttribute('data-reason') || chip.textContent.trim();
    chip.classList.toggle('active', chipVal.toLowerCase() === reason.toLowerCase());
  });
}

async function confirmCancelWithReason() {
  const postId = state.pendingCancelPostId;
  if (!postId) return;
  const input = document.getElementById('inputCancelReason');
  const reason = (input?.value || '').trim() || (state.isSpamCancelMode ? 'Scam' : 'Unspecified');

  try {
    const endpoint = (state.isSpamCancelMode || reason.toLowerCase() === 'scam' || reason.toLowerCase().includes('spam'))
      ? `/api/posts/${postId}/spam`
      : `/api/posts/${postId}/reject`;

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    if (res.ok) {
      showToast(`✕ Application cancelled: ${reason}`, 'info');
      closeCancelReasonModal();
      if (state.activeReviewPost && state.activeReviewPost.id === postId) {
        state.activeReviewPost = null;
      }
      await loadDashboardData();

      // If in Review workspace, move to next or show empty state
      if (state.currentTab === 'review' || (state.reviewPosts && state.reviewPosts.length > 0)) {
        const remaining = state.reviewPosts.filter(p => p.id !== postId);
        if (remaining.length > 0) {
          await openPostInReview(remaining[0].id);
        } else {
          document.getElementById('workspacePanel')?.classList.add('hidden');
          document.getElementById('emptyReviewState')?.classList.remove('hidden');
        }
      }
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Could not cancel application.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function rejectActivePost() {
  return cancelActiveApplication();
}

// Mail Return Prompt: Detect window focus after returning from Gmail compose
window.addEventListener('focus', async () => {
  if (state.awaitingSentPost) {
    const candidate = state.awaitingSentPost;
    state.awaitingSentPost = null;
    setTimeout(async () => {
      const email = (candidate.contact_emails && candidate.contact_emails[0]) || '';
      const emailNote = email ? ` (${email})` : '';
      const markSent = await showConfirm(
        'Mark Outreach as Sent?',
        `Welcome back from Gmail! Did you finish sending the email application${emailNote} for ${candidate.author_name}? Click 'Mark Sent' to move to Others history, or 'Cancel / Not Sent' to review options.`,
        { confirmText: 'Mark Sent', cancelText: 'Cancel / Not Sent' }
      );
      if (markSent) {
        await markPostSentById(candidate.id);
      } else {
        const wantCancel = await showConfirm(
          'Discard Application?',
          `Would you like to cancel and discard this application for ${candidate.author_name} (e.g. unsuitable opening)? Click 'Cancel Application' to choose a reason, or 'Keep in Drafts' to leave it ready.`,
          { confirmText: 'Cancel Application', cancelText: 'Keep in Drafts', danger: true }
        );
        if (wantCancel) {
          openCancelReasonModal(candidate.id, candidate.author_name);
        }
      }
    }, 450);
  }
});

function setOthersFilter(filter) {
  state.othersFilter = filter;
  state.sentPage = 1;
  document.querySelectorAll('#othersPills .pill').forEach(pill => {
    pill.classList.toggle('active', pill.dataset.others === filter);
  });
  fetchSentPosts();
}

// --- TAB 3: Others (Sent & Cancelled Applications History) ---
let sentSearchDebounce = null;
function handleSearchSentKeyUp(e) {
  if (e.key === 'Enter') {
    state.searchSent = (document.getElementById('inputSearchSent')?.value || '').trim();
    state.sentPage = 1;
    fetchSentPosts();
  } else {
    clearTimeout(sentSearchDebounce);
    sentSearchDebounce = setTimeout(() => {
      state.searchSent = (document.getElementById('inputSearchSent')?.value || '').trim();
      state.sentPage = 1;
      fetchSentPosts();
    }, 300);
  }
}

async function fetchSentPosts() {
  const tbody = document.getElementById('sentTableBody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem;">Loading history...</td></tr>';

  try {
    const statusVal = state.othersFilter === 'ALL' ? 'OTHERS' : state.othersFilter;
    const params = new URLSearchParams({
      status: statusVal,
      order_by: 'updated_at',
      limit: String(state.sentLimit),
      offset: String((state.sentPage - 1) * state.sentLimit),
    });
    if (state.searchSent) {
      params.append('search', state.searchSent);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    state.sentPosts = data.posts || [];
    state.sentTotal = data.total !== undefined ? data.total : (data.posts ? data.posts.length : 0);

    tbody.innerHTML = '';
    if (state.sentPosts.length === 0) {
      const emptyMsg = state.searchSent
        ? `No applications matching "${escapeHtml(state.searchSent)}" found.`
        : 'No applications in Others history yet.';
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 3rem; color: #64748b;">${emptyMsg}</td></tr>`;
      renderSentPagination();
      return;
    }

    state.sentPosts.forEach((post) => {
      const tr = document.createElement('tr');
      tr.className = 'clickable-card sent-table-row';
      tr.onclick = (e) => {
        if (!e.target.closest('button, a, input')) {
          openPostModal(post.id);
        }
      };

      const email = (post.contact_emails && post.contact_emails[0]) || 'N/A';
      const updatedDate = post.updated_at
        ? new Date(post.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : 'Recently';

      const isSent = post.status === 'SENT';
      const isRejected = post.status === 'REJECTED';

      let statusBadge = '';
      if (isSent) {
        statusBadge = `<span class="badge-status-sent">✉ Sent</span>`;
      } else if (isRejected) {
        statusBadge = `<span class="badge-status-rejected">🚫 Cancelled</span>`;
        if (post.rejection_reason) {
          statusBadge += `<span class="badge-rejection-reason" title="${escapeHtml(post.rejection_reason)}">${escapeHtml(post.rejection_reason)}</span>`;
        }
      } else {
        statusBadge = `<span class="pill-badge badge-none">${escapeHtml(post.status)}</span>`;
      }

      const noteOrSubject = escapeHtml(post.generated_subject || (post.full_text ? post.full_text.slice(0, 65) + '...' : '—'));

      tr.innerHTML = `
        <td>
          <div class="recruiter-cell" onclick="openPostModal('${post.id}')" title="Click to view full application details" style="cursor: pointer;">
            <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
              <strong>${escapeHtml(post.author_name)}</strong>
              ${getSourceBadgeHtml(post.post_url, post.is_potential_spam)}
            </div>
            <span class="recruiter-headline">${escapeHtml(post.author_headline || '')}</span>
          </div>
        </td>
        <td><code>${escapeHtml(email)}</code></td>
        <td>
          <div style="font-size: 0.78rem; color: var(--text-dim); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer;" title="Click to view details: ${noteOrSubject}" onclick="openPostModal('${post.id}')">
            ${noteOrSubject}
          </div>
        </td>
        <td>${statusBadge}</td>
        <td style="font-size: 0.76rem; color: var(--text-muted); white-space: nowrap;">${updatedDate}</td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end; gap: 0.35rem;">
            <button class="btn btn-outline btn-sm" onclick="openPostModal('${post.id}')" title="View details">
              <span>View</span>
            </button>
            <button class="btn btn-outline btn-sm" onclick="revertPostToDraft('${post.id}')" title="Restore back to active drafts/discovered">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              <span>Restore</span>
            </button>
            ${
              post.post_url && !post.post_url.startsWith('manual://')
                ? `<a href="${post.post_url}" target="_blank" class="icon-btn sm" title="Open source post">
                     <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                   </a>`
                : ''
            }
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    renderSentPagination();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem;">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderSentPagination() {
  const totalPages = Math.ceil(state.sentTotal / state.sentLimit) || 1;
  const startRow = state.sentTotal === 0 ? 0 : (state.sentPage - 1) * state.sentLimit + 1;
  const endRow = Math.min(state.sentPage * state.sentLimit, state.sentTotal);

  const info = document.getElementById('sentPaginationInfo');
  if (info) {
    info.textContent = `Showing ${startRow}–${endRow} of ${state.sentTotal} applications`;
  }

  const container = document.getElementById('sentPageButtons');
  if (!container) return;
  container.innerHTML = '';

  // Prev Button
  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '‹';
  prevBtn.disabled = state.sentPage <= 1;
  prevBtn.onclick = () => goToSentPage(state.sentPage - 1);
  container.appendChild(prevBtn);

  // Page Numbers (up to 5 pages around current)
  const startPage = Math.max(1, state.sentPage - 2);
  const endPage = Math.min(totalPages, state.sentPage + 2);

  for (let p = startPage; p <= endPage; p++) {
    const pBtn = document.createElement('button');
    pBtn.className = `page-btn ${p === state.sentPage ? 'active' : ''}`;
    pBtn.textContent = String(p);
    pBtn.onclick = () => goToSentPage(p);
    container.appendChild(pBtn);
  }

  // Next Button
  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = '›';
  nextBtn.disabled = state.sentPage >= totalPages;
  nextBtn.onclick = () => goToSentPage(state.sentPage + 1);
  container.appendChild(nextBtn);
}

function goToSentPage(p) {
  state.sentPage = p;
  fetchSentPosts();
}

function changeSentRowsPerPage(val) {
  state.sentLimit = parseInt(val, 10) || 25;
  state.sentPage = 1;
  fetchSentPosts();
}

async function revertPostToDraft(postId) {
  const confirmed = await showConfirm(
    'Revert Sent Application?',
    'This will return this application back to the Review & Drafts workspace, allowing you to edit the email draft and re-send or modify it.',
    { confirmText: 'Revert to Draft' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/posts/${postId}/revert`, { method: 'POST' });
    if (res.ok) {
      showToast('Application reverted back to Review & Drafts', 'success');
      await fetchSentPosts();
      await fetchReviewPosts();
      switchTab('tabReview');
      const target = state.reviewPosts.find(p => p.id === postId);
      if (target) selectReviewPost(target);
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Failed to revert post.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Automation Triggers ---
async function triggerInfoparkScrape() {
  const confirmed = await showConfirm(
    'Scrape Today\'s Infopark Jobs',
    'Fetch today\'s job postings directly from infopark.in/companies-job? The scraper visits each details page, extracting the complete job description (JD) and company recruiter emails.',
    { confirmText: 'Scrape Infopark' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/scrape/infopark', { method: 'POST' });
    if (res.ok) {
      showToast('Infopark scraper started', 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Scraper Busy', err.detail || 'Cannot start scraper.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function fetchScrapers() {
  try {
    const res = await fetch('/api/scrapers');
    if (!res.ok) return;
    const scrapers = await res.json();
    const select = document.getElementById('crawlerSourceSelect');
    if (select && scrapers && scrapers.length > 0) {
      const saved = localStorage.getItem('reach_selected_crawler_source');
      select.innerHTML = scrapers.map(s => `
        <option value="${escapeHtml(s.id)}" ${saved === s.id ? 'selected' : ''}>
          ${escapeHtml(s.icon || '🌐')} ${escapeHtml(s.name)}
        </option>
      `).join('');
      select.onchange = () => {
        localStorage.setItem('reach_selected_crawler_source', select.value);
      };
    }
  } catch (err) {
    console.error('Error fetching scrapers:', err);
  }
}

async function triggerSelectedCrawl() {
  const select = document.getElementById('crawlerSourceSelect');
  const sourceId = select ? select.value : 'linkedin';
  const sourceName = select ? select.options[select.selectedIndex]?.text.trim() : 'Selected Source';

  const confirmed = await showConfirm(
    `Start Crawling: ${sourceName}`,
    `Launch the ${sourceName} scraper? It will run visibly with a 90-second inactivity watchdog and automatically save discovered jobs to the database.`,
    { confirmText: `Start Crawl` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: sourceId }),
    });
    if (res.ok) {
      showToast(`${sourceName} crawler started`, 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Scraper Busy', err.detail || 'Cannot start scraper.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function triggerLinkedInScrape() {
  const select = document.getElementById('crawlerSourceSelect');
  if (select) select.value = 'linkedin';
  await triggerSelectedCrawl();
}

function markPostAsSpam(postId) {
  const p = (state.discoveredPosts || []).find(item => item.id === postId)
         || (state.posts || []).find(item => item.id === postId);
  openCancelReasonModal(postId, p?.author_name || '', 'Scam', true);
}

function cancelDiscoveredPost(postId, authorName) {
  const p = (state.discoveredPosts || []).find(item => item.id === postId)
         || (state.posts || []).find(item => item.id === postId);
  openCancelReasonModal(postId, authorName || p?.author_name || '', '', false);
}

function markActivePostSpam() {
  const active = state.activeReviewPost || (state.reviewPosts && state.reviewPosts.length > 0 ? state.reviewPosts[0] : null);
  if (!active) {
    showToast('No active post selected in Review workspace', 'warning');
    return;
  }
  state.activeReviewPost = active;
  state.activePostId = active.id;
  openCancelReasonModal(active.id, active.author_name || 'Job Post', 'Scam', true);
}

function markPostModalSpam() {
  const postId = state.currentModalPostId;
  if (!postId) return;
  const p = (state.posts && state.posts.find(item => item.id === postId)) ||
            (state.reviewPosts && state.reviewPosts.find(item => item.id === postId)) ||
            (state.sentPosts && state.sentPosts.find(item => item.id === postId));
  closePostModal();
  openCancelReasonModal(postId, p?.author_name || 'Job Post', 'Scam', true);
}

async function generateSingleChatGPT(postId) {
  try {
    const res = await fetch(`/api/generate-email/${postId}`, { method: 'POST' });
    if (res.ok) {
      showToast('ChatGPT email generation launched in headed Firefox', 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail);
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function generateBatchChatGPT() {
  const ids = Array.from(state.selectedIds);
  if (ids.length === 0) return;

  const confirmed = await showConfirm(
    'Generate Outreach Emails',
    `Generate tailored outreach emails for ${ids.length} selected post(s) using ChatGPT in headed Firefox?`,
    { confirmText: `Generate ${ids.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/generate-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids }),
    });

    if (res.ok) {
      state.selectedIds.clear();
      updateSelectedCountUI();
      showToast(`Batch generation started for ${ids.length} posts`, 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail);
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Real-Data Task Polling & Animations ---
function startTaskPolling() {
  if (state.pollingTimer) clearInterval(state.pollingTimer);
  state.pollingTimer = setInterval(pollTaskStatus, 1500);
  pollTaskStatus();
}

function stopTaskPolling() {
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
    state.pollingTimer = null;
  }
}

async function pollTaskStatus() {
  try {
    const res = await fetch('/api/tasks/status');
    if (!res.ok) return;
    const task = await res.json();

    const card = document.getElementById('liveTaskCard');
    const titleEl = document.getElementById('taskTitle');
    const subEl = document.getElementById('taskSubtitle');
    const countEl = document.getElementById('taskCounterPill');
    const fillEl = document.getElementById('taskProgressFill');
    const logsEl = document.getElementById('logsStream');

    if (task.status === 'running') {
      if (!state.pollingTimer) {
        state.pollingTimer = setInterval(pollTaskStatus, 1500);
      }
      card.classList.remove('hidden');
      titleEl.textContent = task.task_name;
      subEl.textContent = task.current_step;

      const total = task.total_items || 1;
      const done = task.completed_items || 0;
      countEl.textContent = `${done} / ${total}`;

      const pct = Math.min(100, Math.round((done / total) * 100));
      fillEl.style.width = `${Math.max(5, pct)}%`;

      logsEl.innerHTML = (task.logs || []).map(l => `<div>${escapeHtml(l)}</div>`).join('');
      logsEl.scrollTop = logsEl.scrollHeight;

      // Reset handled task event key while running
      state.lastHandledTaskKey = null;
    } else if (task.status === 'completed' || task.status === 'error') {
      const taskEventKey = `${task.task_name}_${task.started_at}_${task.status}`;
      if (state.lastHandledTaskKey === taskEventKey) {
        // Already handled! Stop polling and do not reload again
        stopTaskPolling();
        return;
      }
      state.lastHandledTaskKey = taskEventKey;
      stopTaskPolling();

      if (task.status === 'completed') {
        fillEl.style.width = '100%';
        subEl.textContent = '✓ Completed successfully';
        setTimeout(() => {
          card.classList.add('hidden');
          fetch('/api/tasks/clear', { method: 'POST' }).catch(() => {});
          loadDashboardData();
        }, 1500);
      } else {
        const firstLine = (task.error || 'Operation failed').split('\n')[0];
        subEl.textContent = `✗ Failed: ${firstLine}`;
        showSnackbar({
          title: `Task Error: ${task.task_name || 'Automation'}`,
          message: firstLine,
          details: task.error,
          type: 'error',
        });
        showCenterAlert(
          `Automation Stopped: ${task.task_name || 'Task'}`,
          task.error || 'The automation task encountered an issue and stopped.'
        );
        setTimeout(() => {
          card.classList.add('hidden');
          fetch('/api/tasks/clear', { method: 'POST' }).catch(() => {});
          loadDashboardData();
        }, 2000);
      }
    } else {
      card.classList.add('hidden');
      stopTaskPolling();
    }
  } catch (err) {
    console.error('Task poll error:', err);
    stopTaskPolling();
  }
}

function toggleTaskLogs() {
  state.showLogs = !state.showLogs;
  document.getElementById('taskLogsDrawer').classList.toggle('hidden', !state.showLogs);
}

// --- Post Full Text Modal ---
function openPostModal(postId) {
  state.currentModalPostId = postId;
  const post = (state.posts && state.posts.find(p => p.id === postId)) ||
               (state.reviewPosts && state.reviewPosts.find(p => p.id === postId)) ||
               (state.sentPosts && state.sentPosts.find(p => p.id === postId));
  if (!post) return;

  const modalSpamBtn = document.getElementById('modalPostSpamBtn');
  if (modalSpamBtn) {
    if (post.status !== 'REJECTED' && post.status !== 'SENT') {
      modalSpamBtn.classList.remove('hidden');
    } else {
      modalSpamBtn.classList.add('hidden');
    }
  }

  const postUrl = post.post_url || '';
  let sourceBadge = 'LinkedIn';
  if (postUrl.includes('infopark.in')) sourceBadge = 'Infopark Kochi';
  else if (postUrl.startsWith('manual://') || postUrl.includes('manual')) sourceBadge = 'Manual JD';

  document.getElementById('modalPostAuthor').textContent = `${post.author_name} — [${sourceBadge}]`;
  const metaEl = document.getElementById('modalPostMeta');
  if (metaEl) {
    const email = (post.contact_emails && post.contact_emails[0]) ? `Email: ${post.contact_emails[0]}` : 'No email detected';
    const exp = post.raw_experience ? ` • Exp: ${post.raw_experience}` : '';
    metaEl.textContent = `${email}${exp}`;
  }

  // Status Banner (for Sent / Cancelled applications)
  const bannerEl = document.getElementById('modalPostStatusBanner');
  const restoreBtn = document.getElementById('modalPostRestoreBtn');
  if (bannerEl) {
    if (post.status === 'REJECTED') {
      bannerEl.className = '';
      bannerEl.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; padding: 0.65rem 0.85rem; color: #f87171; font-size: 0.82rem;">
          <strong>🚫 Application Cancelled / Discarded</strong>
          ${post.rejection_reason ? `<div style="margin-top: 0.25rem; color: #fca5a5;">Reason: <strong>${escapeHtml(post.rejection_reason)}</strong></div>` : ''}
        </div>
      `;
    } else if (post.status === 'SENT') {
      bannerEl.className = '';
      const sentTime = post.sent_at ? ` on ${new Date(post.sent_at).toLocaleString()}` : '';
      bannerEl.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 0.65rem 0.85rem; color: #34d399; font-size: 0.82rem;">
          <strong>✉ Outreach Email Sent${sentTime}</strong>
          ${post.generated_subject ? `<div style="margin-top: 0.25rem; color: #a7f3d0;">Subject: <em>${escapeHtml(post.generated_subject)}</em></div>` : ''}
        </div>
      `;
    } else {
      bannerEl.className = 'hidden';
      bannerEl.innerHTML = '';
    }
  }

  if (restoreBtn) {
    if (post.status === 'SENT' || post.status === 'REJECTED') {
      restoreBtn.classList.remove('hidden');
      restoreBtn.onclick = () => {
        closePostModal();
        revertPostToDraft(post.id);
      };
    } else {
      restoreBtn.classList.add('hidden');
    }
  }

  const linkEl = document.getElementById('modalPostLink');
  if (linkEl) {
    if (post.post_url && !post.post_url.startsWith('manual://')) {
      linkEl.href = post.post_url;
      linkEl.style.display = 'inline-flex';
      linkEl.textContent = post.post_url.includes('infopark.in') ? 'View on Infopark ↗' : 'View on LinkedIn ↗';
    } else {
      linkEl.style.display = 'none';
    }
  }
  document.getElementById('modalPostContent').textContent = post.full_text;
  document.getElementById('postModal').classList.remove('hidden');
}

function closePostModal() {
  document.getElementById('postModal').classList.add('hidden');
}

// --- Manual JD Entry Modal ---
function openAddJdModal() {
  document.getElementById('manualJdTitle').value = '';
  document.getElementById('manualJdCompany').value = '';
  document.getElementById('manualJdContent').value = '';
  document.getElementById('modalAddJd').classList.remove('hidden');
}

function closeAddJdModal() {
  document.getElementById('modalAddJd').classList.add('hidden');
}

async function submitManualJd() {
  const content = (document.getElementById('manualJdContent').value || '').trim();
  if (!content) {
    showAlert('Missing Content', 'Please paste the job description text.');
    return;
  }
  const title = (document.getElementById('manualJdTitle').value || '').trim();
  const company = (document.getElementById('manualJdCompany').value || '').trim();

  try {
    const res = await fetch('/api/posts/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title || 'Job Opening',
        company: company || 'Recruiter',
        content: content,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      closeAddJdModal();
      showToast(`✓ Added manual JD: ${data.post?.author_name || 'Job Opening'}`, 'success');
      loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Could not save manual JD.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Settings Modal ---
function openSettingsModal() {
  document.getElementById('settingResumePath').value = state.config.resume_path || '';
  document.getElementById('settingSearchQuery').value = state.config.search_query || '';
  document.getElementById('settingChatGptUrl').value = state.config.chatgpt_url || '';
  document.getElementById('settingsModal').classList.remove('hidden');
}

function closeSettingsModal() {
  document.getElementById('settingsModal').classList.add('hidden');
}

async function saveSettings() {
  const payload = {
    resume_path: document.getElementById('settingResumePath').value.trim(),
    search_query: document.getElementById('settingSearchQuery').value.trim(),
    chatgpt_url: document.getElementById('settingChatGptUrl').value.trim(),
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeSettingsModal();
      await fetchSettings();
      showToast('✓ Settings updated successfully', 'success');
    } else {
      showAlert('Save Error', 'Could not save settings.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Utilities ---
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==========================================================================
// Analytics & Trend Graph Engine
// ==========================================================================

const chartDefaultOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#94a3b8',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: '500' }
      }
    },
    tooltip: {
      backgroundColor: '#0f172a',
      titleColor: '#f8fafc',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 1,
      padding: 10,
      boxPadding: 4,
      usePointStyle: true,
    }
  }
};

function renderDailyAppliedChart(timeline) {
  const canvas = document.getElementById('chartDailyApplied');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.dailyApplied) {
    state.charts.dailyApplied.destroy();
  }
  const ctx = canvas.getContext('2d');
  
  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.35)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  state.charts.dailyApplied = new Chart(ctx, {
    type: 'line',
    data: {
      labels: timeline.map(d => d.label),
      datasets: [{
        label: 'Applications Applied',
        data: timeline.map(d => d.count),
        borderColor: '#10b981',
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#10b981',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1.5,
        pointRadius: timeline.length > 30 ? 2 : 4,
        pointHoverRadius: 6,
      }]
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        }
      }
    }
  });
}

function renderDailyScrapedChart(timeline) {
  const canvas = document.getElementById('chartDailyScraped');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.dailyScraped) {
    state.charts.dailyScraped.destroy();
  }
  const ctx = canvas.getContext('2d');

  state.charts.dailyScraped = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: timeline.map(d => d.label),
      datasets: [{
        label: 'JDs Discovered',
        data: timeline.map(d => d.count),
        backgroundColor: 'rgba(14, 165, 233, 0.75)',
        hoverBackgroundColor: '#38bdf8',
        borderRadius: 4,
      }]
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        }
      }
    }
  });
}

function renderStatusBreakdownChart(statuses) {
  const canvas = document.getElementById('chartStatusBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.statusBreakdown) {
    state.charts.statusBreakdown.destroy();
  }
  state.charts.statusBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: statuses.map(s => s.label),
      datasets: [{
        data: statuses.map(s => s.count),
        backgroundColor: statuses.map(s => s.color),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderSourceBreakdownChart(sources) {
  const canvas = document.getElementById('chartSourceBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.sourceBreakdown) {
    state.charts.sourceBreakdown.destroy();
  }
  const colors = ['#0ea5e9', '#6366f1', '#10b981', '#f59e0b'];
  state.charts.sourceBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: sources.map(s => s.source),
      datasets: [{
        data: sources.map(s => s.total_scraped),
        backgroundColor: colors.slice(0, sources.length),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderExperienceBreakdownChart(experiences) {
  const canvas = document.getElementById('chartExperienceBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.experienceBreakdown) {
    state.charts.experienceBreakdown.destroy();
  }
  const colors = ['#8b5cf6', '#3b82f6', '#10b981', '#64748b'];
  state.charts.experienceBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: experiences.map(e => e.exp_tier),
      datasets: [{
        data: experiences.map(e => e.count),
        backgroundColor: colors.slice(0, experiences.length),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderRejectionReasonsChart(reasons) {
  const canvas = document.getElementById('chartRejectionReasons');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.rejectionReasons) {
    state.charts.rejectionReasons.destroy();
  }
  const cleanReasons = (reasons && reasons.length > 0) ? reasons : [{ reason: 'No cancellations recorded', count: 0 }];
  state.charts.rejectionReasons = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: cleanReasons.map(r => r.reason),
      datasets: [{
        label: 'Screened / Cancelled Count',
        data: cleanReasons.map(r => r.count),
        backgroundColor: 'rgba(244, 63, 94, 0.75)',
        hoverBackgroundColor: '#fb7185',
        borderRadius: 4,
      }]
    },
    options: {
      ...chartDefaultOptions,
      indexAxis: 'y',
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#cbd5e1', font: { size: 11 } }
        }
      }
    }
  });
}

async function loadAnalytics(days = 30) {
  state.analyticsDays = days;
  const param = (days && days > 0) ? `days=${days}` : `days=0`;
  try {
    const res = await fetch(`/api/analytics?${param}`);
    if (!res.ok) throw new Error('Failed to fetch analytics data');
    const data = await res.json();
    state.analyticsData = data;

    // Update KPI metrics
    if (data.summary) {
      document.getElementById('kpiApplied').textContent = data.summary.total_sent || 0;
      document.getElementById('kpiConversionRate').textContent = `${data.summary.sent_conversion_pct || 0}% conversion`;
      document.getElementById('kpiScraped').textContent = data.summary.total_scraped || 0;
      document.getElementById('kpiEmailRate').textContent = `${data.summary.email_rate_pct || 0}% emails found`;
      document.getElementById('kpiDirectEmails').textContent = `${data.summary.with_emails || 0} outreach ready`;
      document.getElementById('kpiDrafted').textContent = data.summary.total_drafted || 0;
      document.getElementById('kpiDraftReady').textContent = `${data.summary.total_drafted || 0} ready to send`;
      document.getElementById('kpiPendingGen').textContent = `${data.summary.pending_review || 0} pending AI`;
      document.getElementById('kpiRejected').textContent = data.summary.total_rejected || 0;
      document.getElementById('kpiSpamFlagged').textContent = `${data.summary.potential_spam_total || 0} potential spam`;
    }

    // Update timeline badges
    const totalAppliedInPeriod = (data.timeline_applied || []).reduce((acc, curr) => acc + curr.count, 0);
    const totalScrapedInPeriod = (data.timeline_scraped || []).reduce((acc, curr) => acc + curr.count, 0);
    const badgeApplied = document.getElementById('chartAppliedTotalBadge');
    if (badgeApplied) badgeApplied.textContent = `${totalAppliedInPeriod} Applications`;
    const badgeScraped = document.getElementById('chartScrapedTotalBadge');
    if (badgeScraped) badgeScraped.textContent = `${totalScrapedInPeriod} Discovered`;

    // Render Charts
    renderDailyAppliedChart(data.timeline_applied || []);
    renderDailyScrapedChart(data.timeline_scraped || []);
    renderStatusBreakdownChart(data.status_breakdown || []);
    renderSourceBreakdownChart(data.source_breakdown || []);
    renderExperienceBreakdownChart(data.experience_breakdown || []);
    renderRejectionReasonsChart(data.rejection_reasons || []);
  } catch (err) {
    console.error('Analytics load error:', err);
  }
}

function setAnalyticsTimeframe(days) {
  state.analyticsDays = days;
  const pills = document.querySelectorAll('#timeframePills .pill');
  pills.forEach(p => {
    p.classList.toggle('active', parseInt(p.getAttribute('data-days')) === days);
  });
  loadAnalytics(days);
}

