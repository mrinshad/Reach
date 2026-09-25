/**
 * Reach — Sent & Cancelled Applications History (Others Workspace)
 * (src/static/js/history.js)
 */

function setOthersFilter(filter) {
  state.othersFilter = filter;
  state.sentPage = 1;
  document.querySelectorAll('#othersPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.others === filter);
  });
  fetchSentPosts();
}

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

function clearSentFilters() {
  state.othersFilter = 'ALL';
  document.querySelectorAll('#othersPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.others === 'ALL');
  });

  state.othersReason = 'ALL';
  const reasonSel = document.getElementById('selectReasonFilter');
  if (reasonSel) reasonSel.value = 'ALL';

  state.searchSent = '';
  const searchInput = document.getElementById('inputSearchSent');
  if (searchInput) searchInput.value = '';

  state.sentPage = 1;
  fetchSentPosts();
}

async function loadRejectionReasonsFilter(selectedReason = null) {
  try {
    const res = await fetch('/api/reasons');
    if (!res.ok) return;
    const data = await res.json();
    const items = data.counts || (data.reasons || []).map((r) => ({ reason: r, count: null }));

    // Update Sent / Cancelled tab reason filter
    const sentSelect = document.getElementById('selectReasonFilter');
    if (sentSelect) {
      const currentSentVal = selectedReason || state.othersReason || 'ALL';
      let html = '<option value="ALL">All Reasons</option>';
      items.forEach((item) => {
        const countTxt = item.count !== null && item.count !== undefined ? ` (${item.count})` : '';
        const isSel = item.reason === currentSentVal ? 'selected' : '';
        html += `<option value="${escapeHtml(item.reason)}" ${isSel}>${escapeHtml(item.reason)}${countTxt}</option>`;
      });
      sentSelect.innerHTML = html;
      sentSelect.value = currentSentVal;
    }

    // Update Discovered tab reason filter
    const discSelect = document.getElementById('selectReasonFilterDiscovered');
    if (discSelect) {
      const currentDiscVal = state.discoveredReason || 'ALL';
      let html = '<option value="ALL">All Reasons</option>';
      items.forEach((item) => {
        const countTxt = item.count !== null && item.count !== undefined ? ` (${item.count})` : '';
        const isSel = item.reason === currentDiscVal ? 'selected' : '';
        html += `<option value="${escapeHtml(item.reason)}" ${isSel}>${escapeHtml(item.reason)}${countTxt}</option>`;
      });
      discSelect.innerHTML = html;
      discSelect.value = currentDiscVal;
    }

    if (selectedReason) {
      state.othersReason = selectedReason;
    }
  } catch (e) {
    console.error('Error loading rejection reasons:', e);
  }
}

function applySentReasonFilter() {
  const select = document.getElementById('selectReasonFilter');
  if (select) {
    state.othersReason = select.value;
  }
  state.sentPage = 1;
  fetchSentPosts();
}

function filterOthersByReason(reason) {
  switchTab('tabSent');
  setOthersFilter('REJECTED');
  loadRejectionReasonsFilter(reason).then(() => {
    state.othersReason = reason;
    const select = document.getElementById('selectReasonFilter');
    if (select) select.value = reason;
    state.sentPage = 1;
    fetchSentPosts();
  });
}

async function fetchSentPosts() {
  const tbody = document.getElementById('sentTableBody');
  if (!tbody) return;
  if (!state.sentPosts || state.sentPosts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem;">Loading history...</td></tr>';
  }

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
    if (state.othersReason && state.othersReason !== 'ALL') {
      params.append('reason', state.othersReason);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    state.sentPosts = data.posts || [];
    state.sentTotal = data.total !== undefined ? data.total : (data.posts ? data.posts.length : 0);

    const appBadge = document.getElementById('badgeApplicationsCount');
    if (appBadge) appBadge.textContent = state.sentTotal;

    const sentBadge = document.getElementById('sentResultsBadge');
    const isSentFiltered = state.othersFilter !== 'ALL' || (state.searchSent && state.searchSent.trim() !== '') || (state.othersReason && state.othersReason !== 'ALL');
    if (sentBadge) {
      if (isSentFiltered) {
        sentBadge.textContent = `${state.sentTotal} result${state.sentTotal === 1 ? '' : 's'}`;
        sentBadge.classList.remove('hidden');
      } else {
        sentBadge.classList.add('hidden');
      }
    }

    const clearSentBtn = document.getElementById('btnClearSentFilters');
    if (clearSentBtn) {
      clearSentBtn.classList.toggle('hidden', !isSentFiltered);
    }

    tbody.innerHTML = '';
    if (state.sentPosts.length === 0) {
      const emptyMsg = state.searchSent
        ? `No applications matching "${escapeHtml(state.searchSent)}" found.`
        : 'No applications in Others history yet.';
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #64748b;">${emptyMsg}</td></tr>`;
      renderSentPagination();
      updateSelectedSentUI();
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
      const updatedDate = formatDateTime(post.sent_at || post.updated_at || post.created_at);

      const isSent = post.status === 'SENT';
      const isRejected = post.status === 'REJECTED';

      let statusBadge = '';
      if (isSent) {
        statusBadge = `<span class="badge-status-sent" style="display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>Sent</span>`;
      } else if (isRejected) {
        statusBadge = `<span class="badge-status-rejected" style="display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Cancelled</span>`;
        if (post.rejection_reason) {
          statusBadge += `<span class="badge-rejection-reason" title="${escapeHtml(post.rejection_reason)}">${escapeHtml(post.rejection_reason)}</span>`;
        }
      } else {
        statusBadge = `<span class="pill-badge badge-none">${escapeHtml(post.status)}</span>`;
      }

      const noteOrSubject = escapeHtml(post.generated_subject || (post.full_text ? post.full_text.slice(0, 65) + '...' : '—'));

      const isChecked = state.selectedSentIds && state.selectedSentIds.has(post.id);

      tr.innerHTML = `
        <td onclick="event.stopPropagation()">
          <input type="checkbox" class="sent-checkbox" value="${post.id}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelectSent('${post.id}')" title="Select application" />
        </td>
        <td>
          <div class="recruiter-cell" onclick="openPostModal('${post.id}')" title="Click to view full application details" style="cursor: pointer;">
            <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
              <strong>${escapeHtml(post.author_name)}</strong>
              ${getSourceBadgeHtml(post)}
              ${post.location ? `<span class="pill-badge badge-location" style="display: inline-flex; align-items: center; gap: 0.2rem;" title="Location: ${escapeHtml(post.location)}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>${escapeHtml(post.location)}</span>` : ''}
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
            ${
              post.post_url && !post.post_url.startsWith('manual://') && !post.post_url.startsWith('direct://')
                ? `<a href="${post.post_url}" target="_blank" class="icon-btn sm" title="Open source post">
                     <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                   </a>`
                : ''
            }
            <button class="btn btn-outline btn-sm" onclick="openPostModal('${post.id}')" title="View details">
              <span>View</span>
            </button>
            <button class="btn btn-outline btn-sm" onclick="revertPostToDraft('${post.id}')" title="Restore back to active drafts/discovered">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              <span>Restore</span>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    renderSentPagination();
    updateSelectedSentUI();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem;">Error: ${escapeHtml(err.message)}</td></tr>`;
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

  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '‹';
  prevBtn.disabled = state.sentPage <= 1;
  prevBtn.onclick = () => goToSentPage(state.sentPage - 1);
  container.appendChild(prevBtn);

  const startPage = Math.max(1, state.sentPage - 2);
  const endPage = Math.min(totalPages, state.sentPage + 2);

  for (let p = startPage; p <= endPage; p++) {
    const pBtn = document.createElement('button');
    pBtn.className = `page-btn ${p === state.sentPage ? 'active' : ''}`;
    pBtn.textContent = String(p);
    pBtn.onclick = () => goToSentPage(p);
    container.appendChild(pBtn);
  }

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
      if (typeof fetchReviewPosts === 'function') fetchReviewPosts();
      if (typeof fetchStats === 'function') fetchStats();
      if (state.activeTab === 'tabDiscovered' && typeof fetchDiscoveredPosts === 'function') {
        fetchDiscoveredPosts();
      }
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Failed to revert post.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function toggleSelectSent(postId) {
  if (!state.selectedSentIds) state.selectedSentIds = new Set();
  if (state.selectedSentIds.has(postId)) {
    state.selectedSentIds.delete(postId);
  } else {
    state.selectedSentIds.add(postId);
  }
  updateSelectedSentUI();
}

function toggleSelectAllSent(checked) {
  if (!state.selectedSentIds) state.selectedSentIds = new Set();
  const pagePosts = state.sentPosts || [];
  if (checked) {
    pagePosts.forEach((p) => state.selectedSentIds.add(p.id));
  } else {
    pagePosts.forEach((p) => state.selectedSentIds.delete(p.id));
  }
  updateSelectedSentUI();
}

function updateSelectedSentUI() {
  const count = state.selectedSentIds ? state.selectedSentIds.size : 0;
  const countEl = document.getElementById('selectedSentCount');
  const btnBatch = document.getElementById('btnBatchRestoreSent');
  const checkAll = document.getElementById('selectAllSentCheckbox');

  if (countEl) countEl.textContent = String(count);
  if (btnBatch) {
    btnBatch.classList.toggle('hidden', count === 0);
  }

  const pagePosts = state.sentPosts || [];
  if (checkAll) {
    const pageSelectedCount = pagePosts.filter((p) => state.selectedSentIds && state.selectedSentIds.has(p.id)).length;
    checkAll.checked = pagePosts.length > 0 && pageSelectedCount === pagePosts.length;
    checkAll.indeterminate = pageSelectedCount > 0 && pageSelectedCount < pagePosts.length;
  }

  document.querySelectorAll('.sent-checkbox').forEach((cb) => {
    cb.checked = !!(state.selectedSentIds && state.selectedSentIds.has(cb.value));
  });
}

async function restoreBatchSelectedSent() {
  const count = state.selectedSentIds ? state.selectedSentIds.size : 0;
  if (count === 0) return;

  const confirmed = await showConfirm(
    'Restore Multiple Applications?',
    `This will return ${count} selected application${count === 1 ? '' : 's'} back to the Review & Drafts workspace, allowing you to edit the email draft and re-send or modify it.`,
    { confirmText: `Restore ${count} Application${count === 1 ? '' : 's'}` }
  );
  if (!confirmed) return;

  try {
    const postIds = Array.from(state.selectedSentIds);
    const res = await fetch('/api/posts/revert-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: postIds }),
    });

    if (res.ok) {
      const data = await res.json();
      showToast(`✓ Reverted ${data.count || count} applications to Review & Drafts`, 'success');
      state.selectedSentIds.clear();
      updateSelectedSentUI();
      await fetchSentPosts();
      if (typeof fetchReviewPosts === 'function') fetchReviewPosts();
      if (typeof fetchStats === 'function') fetchStats();
      if (typeof loadDashboardData === 'function') loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Restore Error', err.detail || 'Failed to revert applications.');
    }
  } catch (err) {
    showAlert('Restore Error', err.message);
  }
}

// Global Bindings
window.setOthersFilter = setOthersFilter;
window.handleSearchSentKeyUp = handleSearchSentKeyUp;
window.clearSentFilters = clearSentFilters;
window.loadRejectionReasonsFilter = loadRejectionReasonsFilter;
window.applySentReasonFilter = applySentReasonFilter;
window.filterOthersByReason = filterOthersByReason;
window.fetchSentPosts = fetchSentPosts;
window.renderSentPagination = renderSentPagination;
window.goToSentPage = goToSentPage;
window.changeSentRowsPerPage = changeSentRowsPerPage;
window.revertPostToDraft = revertPostToDraft;
window.toggleSelectSent = toggleSelectSent;
window.toggleSelectAllSent = toggleSelectAllSent;
window.updateSelectedSentUI = updateSelectedSentUI;
window.restoreBatchSelectedSent = restoreBatchSelectedSent;

// Activity Run Logs Global Bindings
window.switchHistoryView = switchHistoryView;
window.openActivityLogsView = openActivityLogsView;
window.setActivityLogTypeFilter = setActivityLogTypeFilter;
window.applyActivityLogStatusFilter = applyActivityLogStatusFilter;
window.changeActivityLogsRowsPerPage = changeActivityLogsRowsPerPage;
window.goToActivityLogsPage = goToActivityLogsPage;
window.fetchActivityLogs = fetchActivityLogs;
window.renderActivityLogs = renderActivityLogs;
window.openRunLogsModal = openRunLogsModal;
window.closeRunLogsModal = closeRunLogsModal;
window.copyRunLogs = copyRunLogs;

// =====================================================================
// ACTIVITY & RUN LOGS WORKSPACE
// =====================================================================

let currentHistoryView = 'applications';
let activityLogsPage = 1;
let activityLogsLimit = 25;
let activityLogsTotal = 0;
let activityLogTypeFilter = 'ALL';
let activityLogStatusFilter = 'ALL';
let currentViewingRun = null;

function switchHistoryView(view) {
  currentHistoryView = view;
  const isApps = view === 'applications';

  const btnApps = document.getElementById('btnViewApplications');
  const btnLogs = document.getElementById('btnViewActivityLogs');
  if (btnApps) btnApps.classList.toggle('active', isApps);
  if (btnLogs) btnLogs.classList.toggle('active', !isApps);

  const secApps = document.getElementById('sectionApplicationsHistory');
  const secLogs = document.getElementById('sectionActivityLogs');
  if (secApps) secApps.classList.toggle('hidden', !isApps);
  if (secLogs) secLogs.classList.toggle('hidden', isApps);

  if (isApps) {
    fetchSentPosts();
  } else {
    fetchActivityLogs();
  }
}

function openActivityLogsView() {
  if (typeof switchTab === 'function') {
    switchTab('tabSent');
  }
  switchHistoryView('logs');
}

function setActivityLogTypeFilter(type) {
  activityLogTypeFilter = type;
  activityLogsPage = 1;
  document.querySelectorAll('#activityLogPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.actType === type);
  });
  fetchActivityLogs();
}

function applyActivityLogStatusFilter() {
  const select = document.getElementById('selectActivityLogStatus');
  if (select) {
    activityLogStatusFilter = select.value;
  }
  activityLogsPage = 1;
  fetchActivityLogs();
}

function changeActivityLogsRowsPerPage(limit) {
  activityLogsLimit = parseInt(limit, 10) || 25;
  activityLogsPage = 1;
  fetchActivityLogs();
}

function goToActivityLogsPage(page) {
  activityLogsPage = page;
  fetchActivityLogs();
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '< 1s';
  const sec = Math.round(seconds);
  if (sec < 60) return `${sec}s`;
  const mins = Math.floor(sec / 60);
  const remSec = sec % 60;
  return `${mins}m ${remSec.toString().padStart(2, '0')}s`;
}

function getActivityIconAndLabel(taskType, taskName) {
  const typeLower = (taskType || '').toLowerCase();
  const nameLower = (taskName || '').toLowerCase();

  if (typeLower.includes('easy_apply') || nameLower.includes('easy apply')) {
    return { icon: '⚡', label: 'Easy Apply Crawler' };
  }
  if (typeLower.includes('chatgpt') || nameLower.includes('chatgpt') || nameLower.includes('draft')) {
    return { icon: '🤖', label: 'AI Email Drafts' };
  }
  if (typeLower.includes('infopark') || nameLower.includes('infopark')) {
    return { icon: '🏢', label: 'Infopark IT Crawler' };
  }
  if (typeLower.includes('gmail') || nameLower.includes('gmail') || nameLower.includes('send')) {
    return { icon: '✉️', label: 'Gmail Dispatch' };
  }
  if (typeLower.includes('login') || nameLower.includes('login')) {
    return { icon: '🔑', label: 'Interactive Login' };
  }
  if (typeLower.includes('crawler') || typeLower.includes('scraper') || nameLower.includes('linkedin')) {
    return { icon: '💼', label: 'LinkedIn Posts Crawler' };
  }
  return { icon: '⚙️', label: 'Automation Run' };
}

async function fetchActivityLogs() {
  const tbody = document.getElementById('activityLogsTableBody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2.5rem; color: #94a3b8;">Loading activity run logs...</td></tr>';

  try {
    const params = new URLSearchParams({
      limit: String(activityLogsLimit),
      offset: String((activityLogsPage - 1) * activityLogsLimit),
    });
    if (activityLogTypeFilter && activityLogTypeFilter !== 'ALL') {
      params.append('type', activityLogTypeFilter);
    }
    if (activityLogStatusFilter && activityLogStatusFilter !== 'ALL') {
      params.append('status', activityLogStatusFilter);
    }

    const res = await fetch(`/api/activity-logs?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const runs = data.runs || [];
    activityLogsTotal = data.total || 0;

    const countAllEl = document.getElementById('countLogsAll');
    if (countAllEl) countAllEl.textContent = activityLogsTotal;

    const badgeLogsCount = document.getElementById('badgeActivityLogsCount');
    if (badgeLogsCount) badgeLogsCount.textContent = activityLogsTotal;

    renderActivityLogs(runs);
    renderActivityLogsPagination();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2.5rem; color: #fb7185;">Error loading activity logs: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderActivityLogs(runs) {
  const tbody = document.getElementById('activityLogsTableBody');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (runs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; padding: 3rem; color: #64748b;">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📜</div>
          <div style="font-weight: 600; color: #94a3b8; margin-bottom: 0.25rem;">No Activity Run Logs Found</div>
          <div style="font-size: 0.8rem; color: #64748b;">Automated crawl and application tasks will appear here as they run.</div>
        </td>
      </tr>
    `;
    return;
  }

  runs.forEach((run) => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-card activity-log-row';

    const { icon, label } = getActivityIconAndLabel(run.task_type, run.task_name);

    // Format parameters
    const params = run.parameters || {};
    let paramPillsHtml = '';
    if (params.query || params.keywords) {
      const q = params.query || params.keywords;
      paramPillsHtml += `<span class="param-pill"><strong>Query:</strong> ${escapeHtml(q)}</span>`;
    }
    if (params.location) {
      paramPillsHtml += `<span class="param-pill"><strong>Location:</strong> ${escapeHtml(params.location)}</span>`;
    }
    if (params.time_filter) {
      paramPillsHtml += `<span class="param-pill"><strong>Time:</strong> ${escapeHtml(params.time_filter)}</span>`;
    }
    if (params.max_jobs) {
      paramPillsHtml += `<span class="param-pill"><strong>Limit:</strong> ${escapeHtml(String(params.max_jobs))}</span>`;
    }
    if (params.count) {
      paramPillsHtml += `<span class="param-pill"><strong>Batch:</strong> ${escapeHtml(String(params.count))} items</span>`;
    }
    if (params.author) {
      paramPillsHtml += `<span class="param-pill"><strong>Candidate:</strong> ${escapeHtml(params.author)}</span>`;
    }
    if (!paramPillsHtml) {
      paramPillsHtml = `<span class="param-pill text-muted">Standard config</span>`;
    }

    // Status Badge
    const st = (run.status || 'completed').toLowerCase();
    let statusClass = 'completed';
    let statusText = '✓ Completed';
    if (st === 'running') {
      statusClass = 'running';
      statusText = '⚡ Running';
    } else if (st === 'error') {
      statusClass = 'error';
      statusText = '✗ Failed';
    } else if (st === 'stopped') {
      statusClass = 'stopped';
      statusText = '🛑 Stopped';
    }

    const summaryText = run.result_summary || (st === 'running' ? 'Execution in progress...' : 'Execution finished.');
    const durationText = formatDuration(run.duration_seconds);
    const whenText = typeof formatDateTime === 'function' ? formatDateTime(run.created_at) : (run.created_at || '—');

    tr.innerHTML = `
      <td>
        <div class="activity-name-cell">
          <div class="activity-icon-box">${icon}</div>
          <div>
            <div class="activity-title-text">${escapeHtml(run.short_name || run.task_name)}</div>
            <div class="activity-type-tag">${escapeHtml(label)}</div>
          </div>
        </div>
      </td>
      <td>
        <div class="params-chip-wrap">
          ${paramPillsHtml}
        </div>
      </td>
      <td>
        <div class="run-result-summary">
          <span class="run-status-badge ${statusClass}">${statusText}</span>
          <span class="run-result-text">${escapeHtml(summaryText)}</span>
        </div>
      </td>
      <td>
        <span style="font-family: var(--font-mono, monospace); font-size: 0.8rem; color: #cbd5e1;">${durationText}</span>
      </td>
      <td>
        <span style="font-size: 0.78rem; color: #94a3b8;">${whenText}</span>
      </td>
      <td style="text-align: right;">
        <button class="btn-view-run-logs" onclick="openRunLogsModal('${escapeHtml(run.id)}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          <span>View Logs</span>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderActivityLogsPagination() {
  const footer = document.getElementById('activityLogsTableFooter');
  const info = document.getElementById('activityLogsPaginationInfo');
  const buttonsContainer = document.getElementById('activityLogsPageButtons');
  if (!footer || !info || !buttonsContainer) return;

  const total = activityLogsTotal;
  const totalPages = Math.max(1, Math.ceil(total / activityLogsLimit));
  const start = total === 0 ? 0 : (activityLogsPage - 1) * activityLogsLimit + 1;
  const end = Math.min(total, activityLogsPage * activityLogsLimit);

  info.textContent = `Showing ${start}–${end} of ${total} activity runs`;

  let html = '';
  html += `<button class="page-btn" ${activityLogsPage <= 1 ? 'disabled' : ''} onclick="goToActivityLogsPage(${activityLogsPage - 1})">‹ Prev</button>`;

  const maxPagesToShow = 5;
  let startP = Math.max(1, activityLogsPage - Math.floor(maxPagesToShow / 2));
  let endP = Math.min(totalPages, startP + maxPagesToShow - 1);
  if (endP - startP + 1 < maxPagesToShow) {
    startP = Math.max(1, endP - maxPagesToShow + 1);
  }

  for (let i = startP; i <= endP; i++) {
    html += `<button class="page-btn ${i === activityLogsPage ? 'active' : ''}" onclick="goToActivityLogsPage(${i})">${i}</button>`;
  }

  html += `<button class="page-btn" ${activityLogsPage >= totalPages ? 'disabled' : ''} onclick="goToActivityLogsPage(${activityLogsPage + 1})">Next ›</button>`;
  buttonsContainer.innerHTML = html;
}

async function openRunLogsModal(runId) {
  const modal = document.getElementById('modalRunTerminalLogs');
  if (!modal) return;

  try {
    const res = await fetch(`/api/activity-logs/${runId}`);
    if (!res.ok) throw new Error('Could not fetch run log details.');
    const data = await res.json();
    currentViewingRun = data;

    const { icon, label } = getActivityIconAndLabel(data.task_type, data.task_name);
    document.getElementById('runLogsModalIcon').textContent = icon;
    document.getElementById('runLogsModalTitle').textContent = data.task_name || 'Activity Console Log';
    document.getElementById('runLogsModalSubtitle').textContent = `${label} · ${data.id}`;

    const st = (data.status || 'completed').toLowerCase();
    const statusEl = document.getElementById('runLogsMetaStatus');
    if (statusEl) {
      statusEl.className = `run-meta-pill run-status-badge ${st}`;
      statusEl.textContent = st.toUpperCase();
    }

    const durationEl = document.getElementById('runLogsMetaDuration');
    if (durationEl) durationEl.textContent = `Duration: ${formatDuration(data.duration_seconds)}`;

    const dateEl = document.getElementById('runLogsMetaDate');
    if (dateEl) {
      dateEl.textContent = `Date: ${typeof formatDateTime === 'function' ? formatDateTime(data.created_at) : (data.created_at || '—')}`;
    }

    const terminalBody = document.getElementById('runLogsTerminalBody');
    if (terminalBody) {
      const logs = data.logs || [];
      if (logs.length > 0) {
        terminalBody.textContent = logs.join('\n');
      } else {
        terminalBody.textContent = `// No console log lines captured for this run.\n// Result: ${data.result_summary || 'Finished'}`;
      }
    }

    modal.classList.remove('hidden');
  } catch (err) {
    if (typeof showAlert === 'function') {
      showAlert('Error', err.message);
    } else {
      alert(err.message);
    }
  }
}

function closeRunLogsModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('close-x') && !e.target.classList.contains('btn-secondary')) {
    return;
  }
  const modal = document.getElementById('modalRunTerminalLogs');
  if (modal) modal.classList.add('hidden');
}

function copyRunLogs() {
  if (!currentViewingRun || !currentViewingRun.logs) return;
  const text = currentViewingRun.logs.join('\n');
  navigator.clipboard.writeText(text).then(() => {
    if (typeof showToast === 'function') {
      showToast('✓ Console terminal logs copied to clipboard!', 'success');
    }
  }).catch(() => {
    if (typeof showToast === 'function') {
      showToast('Failed to copy to clipboard', 'error');
    }
  });
}
