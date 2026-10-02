/**
 * Reach — LinkedIn Easy Apply & Job Portal Subsystem
 * (src/static/js/easy_apply.js)
 */

let easyApplyPosts = [];
let easyApplyStatusFilter = 'ALL';
let easyTableSearchQuery = '';
const selectedEasyJobIds = new Set();
let activeEasyModalPost = null;

async function fetchEasyApplyPosts() {
  const tbody = document.getElementById('easyApplyTableBody');
  if (!tbody) return;

  if (!easyApplyPosts || easyApplyPosts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #64748b;">Loading Easy Apply opportunities...</td></tr>';
  }

  try {
    const params = new URLSearchParams({
      category: 'EASY_APPLY',
      status: 'ALL',
      limit: '200',
    });

    if (state.fromEasyDate) {
      params.append('from_date', state.fromEasyDate);
    }
    if (state.toEasyDate) {
      params.append('to_date', state.toEasyDate);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    if (!res.ok) return;

    const data = await res.json();
    easyApplyPosts = data.posts || [];

    updateEasyKPIs(easyApplyPosts);
    renderEasyApplyTable();
    checkRateLimitSafeguard();
    fetchQuestionBank(false);
    initEasyCyclesPersistence();
  } catch (err) {
    console.error('Error fetching Easy Apply posts:', err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #ef4444;">Error loading jobs: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function initEasyCyclesPersistence() {
  const input = document.getElementById('easyCrawlerCycles');
  if (!input || input.dataset.persisted) return;
  input.dataset.persisted = 'true';

  const saved = localStorage.getItem('reach_easy_apply_cycles');
  if (saved) input.value = saved;

  const onCyclesUpdate = (e) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val) && val >= 1) {
      localStorage.setItem('reach_easy_apply_cycles', val);
      if (typeof persistCyclesSetting === 'function') {
        persistCyclesSetting('easy_apply_cycles', val);
      }
    }
  };

  input.addEventListener('change', onCyclesUpdate);
  input.addEventListener('input', onCyclesUpdate);
}

function applyEasyDateFilter() {
  const fromEl = document.getElementById('easyDateFrom');
  const toEl = document.getElementById('easyDateTo');
  state.fromEasyDate = fromEl ? fromEl.value.trim() : '';
  state.toEasyDate = toEl ? toEl.value.trim() : '';
  fetchEasyApplyPosts();
}

function updateEasyKPIs(posts = easyApplyPosts) {
  const list = posts || easyApplyPosts || [];
  const total = list.length;
  const applied = list.filter((p) => p.status === 'APPLIED').length;
  const questionnaire = list.filter((p) => p.status === 'REQUIRES_QUESTIONNAIRE').length;
  const ready = list.filter((p) => p.status === 'DISCOVERED').length;
  const notFound = list.filter((p) => p.status === 'NOT_FOUND').length;

  const totalEl = document.getElementById('easyKpiTotal');
  if (totalEl) totalEl.textContent = total;

  const appliedEl = document.getElementById('easyKpiApplied');
  if (appliedEl) appliedEl.textContent = applied;

  const qEl = document.getElementById('easyKpiQuestionnaire');
  if (qEl) qEl.textContent = questionnaire;

  const readyEl = document.getElementById('easyKpiReady');
  if (readyEl) readyEl.textContent = ready;

  const notFoundEl = document.getElementById('easyKpiNotFound');
  if (notFoundEl) notFoundEl.textContent = notFound;

  // Filter Pill Counter Badges
  const countAll = document.getElementById('countPillAll');
  if (countAll) countAll.textContent = total;

  const countReady = document.getElementById('countPillReady');
  if (countReady) countReady.textContent = ready;

  const countScreening = document.getElementById('countPillScreening');
  if (countScreening) countScreening.textContent = questionnaire;

  const countApplied = document.getElementById('countPillApplied');
  if (countApplied) countApplied.textContent = applied;

  const countNF = document.getElementById('countPillNotFound');
  if (countNF) countNF.textContent = notFound;

  const badgeEl = document.getElementById('countEasyApply');
  if (badgeEl) {
    badgeEl.textContent = ready;
    badgeEl.title = `${ready} Easy Apply jobs ready`;
  }
}

function filterEasyApplyStatus(status) {
  easyApplyStatusFilter = status;

  // Update pills
  const pills = {
    ALL: document.getElementById('pillEasyAll'),
    DISCOVERED: document.getElementById('pillEasyDiscovered'),
    REQUIRES_QUESTIONNAIRE: document.getElementById('pillEasyQuestionnaire'),
    APPLIED: document.getElementById('pillEasyApplied'),
    NOT_FOUND: document.getElementById('pillEasyNotFound'),
  };

  Object.entries(pills).forEach(([key, el]) => {
    if (el) el.classList.toggle('active', key === status);
  });

  renderEasyApplyTable();
}

function handleEasyTableSearch(query) {
  easyTableSearchQuery = (query || '').trim().toLowerCase();
  renderEasyApplyTable();
}

function renderEasyApplyTable() {
  const tbody = document.getElementById('easyApplyTableBody');
  if (!tbody) return;

  let filtered = easyApplyPosts;
  if (easyApplyStatusFilter !== 'ALL') {
    filtered = filtered.filter((p) => p.status === easyApplyStatusFilter);
  }

  if (easyTableSearchQuery) {
    filtered = filtered.filter((p) => {
      const headline = (p.author_headline || '').toLowerCase();
      const company = (p.author_name || '').toLowerCase();
      const location = (p.location || '').toLowerCase();
      const text = (p.full_text || '').toLowerCase();
      return (
        headline.includes(easyTableSearchQuery) ||
        company.includes(easyTableSearchQuery) ||
        location.includes(easyTableSearchQuery) ||
        text.includes(easyTableSearchQuery)
      );
    });
  }

  if (filtered.length === 0) {
    let emptyMsg = 'No LinkedIn Easy Apply jobs scraped yet. Click "Crawl & Auto-Apply" to discover jobs!';
    if (easyTableSearchQuery) {
      emptyMsg = `No jobs matched search "${escapeHtml(easyTableSearchQuery)}".`;
    } else if (easyApplyStatusFilter !== 'ALL') {
      emptyMsg = `No jobs found with status "${easyApplyStatusFilter}".`;
    }
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #64748b; font-size: 0.82rem;">${emptyMsg}</td></tr>`;
    return;
  }

  tbody.innerHTML = '';
  filtered.forEach((post) => {
    const tr = document.createElement('tr');
    tr.id = `easy-row-${post.id}`;
    const isSelected = selectedEasyJobIds.has(post.id);

    // Status Badge with Interactive Dropdown Menu
    let statusBadgeText = '⚡ Ready';
    let statusBadgeClass = 'discovered';
    if (post.status === 'APPLIED') {
      statusBadgeText = '✓ Applied';
      statusBadgeClass = 'applied';
    } else if (post.status === 'REQUIRES_QUESTIONNAIRE') {
      statusBadgeText = '📋 Screening';
      statusBadgeClass = 'questionnaire';
    } else if (post.status === 'REJECTED') {
      statusBadgeText = '✕ Dismissed';
      statusBadgeClass = 'rejected';
    } else if (post.status === 'NOT_FOUND') {
      statusBadgeText = '🚫 Not Found';
      statusBadgeClass = 'not-found';
    }

    const statusDropdown = `
      <div class="easy-status-wrap" id="status-wrap-${post.id}">
        <span class="tag-easy-status ${statusBadgeClass} tag-easy-status-btn" onclick="toggleEasyStatusMenu('${post.id}', event)" title="Click to change status">
          <span>${statusBadgeText}</span>
          <span class="status-caret">▾</span>
        </span>
        <div class="easy-status-menu" id="status-menu-${post.id}">
          <button class="status-menu-opt opt-ready" onclick="setEasyPostStatus('${post.id}', 'DISCOVERED', event)">
            <span>⚡</span><span>Ready (Queue)</span>
          </button>
          <button class="status-menu-opt opt-screening" onclick="setEasyPostStatus('${post.id}', 'REQUIRES_QUESTIONNAIRE', event)">
            <span>📋</span><span>Screening Required</span>
          </button>
          <button class="status-menu-opt opt-applied" onclick="setEasyPostStatus('${post.id}', 'APPLIED', event)">
            <span>✓</span><span>Mark Applied</span>
          </button>
          <button class="status-menu-opt opt-not-found" onclick="setEasyPostStatus('${post.id}', 'NOT_FOUND', event)">
            <span>🚫</span><span>Not Found / Closed</span>
          </button>
        </div>
      </div>
    `;

    const expText = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
    const dateText = typeof formatPostDateTimeWithRelative === 'function'
      ? formatPostDateTimeWithRelative(post)
      : (typeof formatDateTime === 'function' ? formatDateTime(post.created_at) : (post.created_at || '—'));
    const locText = escapeHtml(post.location || 'India');

    let actionBtn = `<button class="btn btn-primary btn-xs" onclick="triggerSingleEasyApply('${post.id}')" title="Run Easy Apply submission"><span>⚡ Apply</span></button>`;
    if (post.status === 'APPLIED') {
      actionBtn = `<span class="tag-easy-status applied" style="opacity: 0.9; font-size: 0.68rem; cursor: default;">✓ Submitted</span>`;
    } else if (post.status === 'REQUIRES_QUESTIONNAIRE') {
      actionBtn = `<button class="btn btn-outline btn-xs" onclick="openScreeningModal('${post.id}')" title="View screening questions" style="color: #fbbf24; border-color: rgba(245, 158, 11, 0.4);"><span>📋 Screen</span></button>`;
    } else if (post.status === 'NOT_FOUND') {
      actionBtn = `<span class="tag-easy-status not-found" style="opacity: 0.8; font-size: 0.68rem; cursor: default;">🚫 Closed</span>`;
    }

    tr.innerHTML = `
      <td class="col-check">
        <input type="checkbox" class="easy-checkbox" value="${post.id}" ${isSelected ? 'checked' : ''} onchange="toggleSelectEasyJob('${post.id}', this.checked)" />
      </td>
      <td class="col-role">
        <div class="easy-role-cell">
          <a href="javascript:void(0)" onclick="openEasyDetailsModal('${post.id}')" class="easy-job-title-link" title="Click to view full job details">
            ${escapeHtml(post.author_headline || 'Software Role')}
          </a>
          <span class="easy-company-name">
            <span style="opacity: 0.7;">🏢</span>
            <span>${escapeHtml(post.author_name || 'Company')}</span>
          </span>
          <span class="easy-role-subline">
            <span class="col-mobile-loc">📍 ${locText}</span>
            <span class="col-mobile-date">⏱ ${escapeHtml(dateText)}</span>
          </span>
        </div>
      </td>
      <td class="col-location">
        <span class="easy-location-text" title="${escapeHtml(post.location || 'India')}">
          <span style="opacity: 0.7;">📍</span>
          <span>${locText}</span>
        </span>
      </td>
      <td class="col-exp">
        <span class="pill-badge badge-exp" style="font-size: 0.7rem;">${escapeHtml(expText)}</span>
      </td>
      <td class="col-status">
        ${statusDropdown}
      </td>
      <td class="col-date">
        <span class="easy-date-text" title="${escapeHtml(post.created_at || '')}">${escapeHtml(dateText)}</span>
      </td>
      <td class="col-actions">
        <div class="easy-actions-cell">
          <button class="icon-btn sm" onclick="copyEasyJobLink('${post.id}')" title="Copy LinkedIn Job Link">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
          <a href="${post.post_url}" target="_blank" rel="noopener noreferrer" class="icon-btn sm" title="Open Job on LinkedIn">
            <span style="font-size: 0.72rem; line-height: 1;">↗</span>
          </a>
          ${actionBtn}
        </div>
      </td>
    `;

    tbody.appendChild(tr);
  });

  updateSelectedEasyBatchUI();
}

async function triggerEasyApplyCrawl() {
  const query = (document.getElementById('easySearchQuery')?.value || 'Full Stack Developer').trim();
  const location = (document.getElementById('easySearchLocation')?.value || 'India').trim();
  const timeFilter = document.getElementById('easyTimeFilter')?.value || '24h';
  const cycles = parseInt(document.getElementById('easyCrawlerCycles')?.value || '8', 10);
  const pacing = document.getElementById('selectEasyPacing')?.value || 'safe';

  const btn = document.getElementById('btnLaunchEasyApplyCrawl');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `
      <svg class="spin-fast" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
      <span>Crawling...</span>
    `;
  }

  try {
    const res = await fetch('/api/scrape/easy-apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        search_query: query,
        location: location,
        time_filter: timeFilter,
        cycles: isNaN(cycles) ? 8 : cycles,
        pacing: pacing,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      showToast(`⚡ Enqueued LinkedIn Easy Apply Crawler (${location})`, 'info');
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start Crawler', err.detail || 'Failed to start Easy Apply crawler.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          <span>Crawl & Auto-Apply</span>
        `;
      }
    }, 2000);
  }
}

async function triggerSingleEasyApply(postId) {
  const post = easyApplyPosts.find((p) => p.id === postId);
  const title = post ? post.author_headline : 'job';

  const confirmed = await showConfirm(
    'Submit Easy Apply',
    `Submit automated Easy Apply application for "${title}" using your saved resume?`,
    { confirmText: 'Apply Now' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/easy-apply/${postId}`, { method: 'POST' });
    if (res.ok) {
      showToast(`⚡ Easy Apply launched for ${title}`, 'info');
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Could not start Easy Apply.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function copyEasyJobLink(postId) {
  const post = easyApplyPosts.find((p) => p.id === postId);
  if (!post || !post.post_url) {
    showToast('No job URL available', 'warn');
    return;
  }
  navigator.clipboard.writeText(post.post_url).then(() => {
    showToast('✓ Direct job link copied to clipboard for screening!', 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'error');
  });
}

function openEasyDetailsModal(postId) {
  const post = easyApplyPosts.find((p) => p.id === postId);
  if (!post) return;
  activeEasyModalPost = post;

  const modal = document.getElementById('modalEasyDetails');
  if (!modal) return;

  const comp = post.author_name || 'N/A';
  const loc = post.location || 'India';

  document.getElementById('easyModalJobTitle').textContent = post.author_headline || 'Job Details';
  const headerComp = document.getElementById('easyModalHeaderCompany');
  const headerLoc = document.getElementById('easyModalHeaderLocation');
  if (headerComp) headerComp.textContent = comp;
  if (headerLoc) headerLoc.textContent = loc;

  document.getElementById('easyModalCompany').textContent = comp;
  document.getElementById('easyModalLocation').textContent = loc;
  const expText = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
  document.getElementById('easyModalExp').textContent = expText;
  document.getElementById('easyModalStatus').textContent = post.status;
  updateModalStatusChips(post.status);
  document.getElementById('easyModalFullText').textContent = post.full_text || 'No description extracted.';

  const linkEl = document.getElementById('easyModalLink');
  if (linkEl) {
    linkEl.href = post.post_url || '#';
  }

  // Questionnaire box
  const qBox = document.getElementById('easyModalQuestionnaireBox');
  const qNotes = document.getElementById('easyModalQuestionnaireNotes');
  const viewQBtn = document.getElementById('btnEasyModalViewQuestions');
  if (post.status === 'REQUIRES_QUESTIONNAIRE' && post.rejection_reason) {
    if (qBox) qBox.classList.remove('hidden');
    if (qNotes) qNotes.textContent = post.rejection_reason;
    if (viewQBtn) viewQBtn.classList.remove('hidden');
  } else {
    if (qBox) qBox.classList.add('hidden');
    if (viewQBtn) viewQBtn.classList.add('hidden');
  }

  modal.classList.remove('hidden');
}

function closeEasyDetailsModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('close-x') && !e.target.classList.contains('modal-close-btn') && !e.target.classList.contains('close-dialog-btn')) {
    return;
  }
  const modal = document.getElementById('modalEasyDetails');
  if (modal) modal.classList.add('hidden');
  activeEasyModalPost = null;
}

function copyEasyModalLink() {
  if (activeEasyModalPost && activeEasyModalPost.post_url) {
    copyEasyJobLink(activeEasyModalPost.id);
  }
}

function triggerEasyModalApply() {
  if (activeEasyModalPost) {
    const id = activeEasyModalPost.id;
    closeEasyDetailsModal();
    triggerSingleEasyApply(id);
  }
}

// Batch actions
function toggleSelectEasyJob(postId, checked) {
  if (checked) {
    selectedEasyJobIds.add(postId);
  } else {
    selectedEasyJobIds.delete(postId);
  }
  updateSelectedEasyBatchUI();
}

function toggleSelectAllEasyJobs(checked) {
  let filtered = easyApplyPosts;
  if (easyApplyStatusFilter !== 'ALL') {
    filtered = easyApplyPosts.filter((p) => p.status === easyApplyStatusFilter);
  }

  if (checked) {
    filtered.forEach((p) => selectedEasyJobIds.add(p.id));
  } else {
    selectedEasyJobIds.clear();
  }

  document.querySelectorAll('.easy-checkbox').forEach((cb) => {
    cb.checked = checked;
  });

  updateSelectedEasyBatchUI();
}

function updateSelectedEasyBatchUI() {
  const toolbar = document.getElementById('easyBatchToolbar');
  const countEl = document.getElementById('easySelectedCount');
  const size = selectedEasyJobIds.size;

  if (toolbar) {
    toolbar.classList.toggle('hidden', size === 0);
  }
  if (countEl) {
    countEl.textContent = `${size} selected`;
  }

  const checkAll = document.getElementById('easyCheckAll');
  if (checkAll) {
    const visibleCount = document.querySelectorAll('.easy-checkbox').length;
    checkAll.checked = visibleCount > 0 && size === visibleCount;
    checkAll.indeterminate = size > 0 && size < visibleCount;
  }
}

function clearEasySelection() {
  selectedEasyJobIds.clear();
  document.querySelectorAll('.easy-checkbox').forEach((cb) => {
    cb.checked = false;
  });
  const checkAll = document.getElementById('easyCheckAll');
  if (checkAll) {
    checkAll.checked = false;
    checkAll.indeterminate = false;
  }
  updateSelectedEasyBatchUI();
}

function batchCopyEasyLinks() {
  const urls = [];
  selectedEasyJobIds.forEach((id) => {
    const p = easyApplyPosts.find((post) => post.id === id);
    if (p && p.post_url) urls.push(`${p.author_headline || 'Job'} @ ${p.author_name || 'Company'}: ${p.post_url}`);
  });

  if (urls.length === 0) {
    showToast('No URLs selected', 'warn');
    return;
  }

  navigator.clipboard.writeText(urls.join('\n')).then(() => {
    showToast(`✓ Copied ${urls.length} job links to clipboard for screening!`, 'success');
  });
}

async function batchDismissEasyJobs() {
  const size = selectedEasyJobIds.size;
  if (size === 0) return;

  const confirmed = await showConfirm('Dismiss Selected', `Dismiss ${size} selected jobs from queue?`);
  if (!confirmed) return;

  for (const id of selectedEasyJobIds) {
    try {
      await fetch(`/api/posts/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Dismissed by user' }),
      });
    } catch (_) {}
  }

  selectedEasyJobIds.clear();
  showToast(`✓ Dismissed ${size} jobs`, 'success');
  fetchEasyApplyPosts();
}

async function batchApplySelectedEasyJobs() {
  const ids = Array.from(selectedEasyJobIds);
  if (ids.length === 0) return;

  const confirmed = await showConfirm(
    'Batch Easy Apply',
    `Queue automated Easy Apply for ${ids.length} selected jobs sequentially?`,
    { confirmText: 'Queue Applications' }
  );
  if (!confirmed) return;

  for (const id of ids) {
    try {
      await fetch(`/api/easy-apply/${id}`, { method: 'POST' });
    } catch (_) {}
  }

  selectedEasyJobIds.clear();
  showToast(`Queued ${ids.length} Easy Apply tasks!`, 'info');
  if (typeof startTaskPolling === 'function') startTaskPolling();
  fetchEasyApplyPosts();
}

// Status Transitions & Interactivity — Fixed-Position Smart Dropdown
function toggleEasyStatusMenu(postId, event) {
  if (event) event.stopPropagation();
  const wrap = document.getElementById(`status-wrap-${postId}`);
  const menu = document.getElementById(`status-menu-${postId}`);
  if (!wrap || !menu) return;

  const isVisible = menu.classList.contains('menu-visible');

  // Close all other open menus
  closeAllEasyStatusMenus();

  if (isVisible) return; // was open, now closed

  // Position menu using fixed coordinates relative to viewport
  const btn = wrap.querySelector('.tag-easy-status-btn');
  if (!btn) return;
  const rect = btn.getBoundingClientRect();
  const menuHeight = 170; // approx height of 4 menu items
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;

  menu.style.left = `${rect.left}px`;

  if (spaceBelow < menuHeight && spaceAbove > menuHeight) {
    // Open upward
    menu.style.top = `${rect.top - menuHeight - 4}px`;
  } else {
    // Open downward
    menu.style.top = `${rect.bottom + 4}px`;
  }

  menu.classList.add('menu-visible');
  wrap.classList.add('open');
}

function closeAllEasyStatusMenus() {
  document.querySelectorAll('.easy-status-menu.menu-visible').forEach((el) => {
    el.classList.remove('menu-visible');
  });
  document.querySelectorAll('.easy-status-wrap.open').forEach((el) => {
    el.classList.remove('open');
  });
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.easy-status-wrap')) {
    closeAllEasyStatusMenus();
  }
});

// Close menus on scroll/resize to prevent orphaned floating menus
window.addEventListener('scroll', closeAllEasyStatusMenus, true);
window.addEventListener('resize', closeAllEasyStatusMenus);

async function setEasyPostStatus(postId, newStatus, event) {
  if (event) event.stopPropagation();
  const wrap = document.getElementById(`status-wrap-${postId}`);
  if (wrap) wrap.classList.remove('open');

  try {
    const res = await fetch(`/api/posts/${postId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });

    if (res.ok) {
      const data = await res.json();
      const post = easyApplyPosts.find((p) => p.id === postId);
      if (post) {
        post.status = newStatus;
      }
      if (activeEasyModalPost && activeEasyModalPost.id === postId) {
        activeEasyModalPost.status = newStatus;
        updateModalStatusChips(newStatus);
      }
      updateEasyKPIs();
      renderEasyApplyTable();
      showToast(`✓ Status updated to ${newStatus}`, 'success');
    } else {
      const err = await res.json();
      showAlert('Failed to Update Status', err.detail || 'Could not update status');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function batchSetEasyStatus(newStatus) {
  const ids = Array.from(selectedEasyJobIds);
  if (ids.length === 0) return;

  try {
    const res = await fetch('/api/posts/status-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids, status: newStatus }),
    });

    if (res.ok) {
      ids.forEach((id) => {
        const post = easyApplyPosts.find((p) => p.id === id);
        if (post) post.status = newStatus;
      });
      selectedEasyJobIds.clear();
      updateEasyKPIs();
      renderEasyApplyTable();
      showToast(`✓ Updated ${ids.length} jobs to ${newStatus}`, 'success');
    } else {
      const err = await res.json();
      showAlert('Batch Update Failed', err.detail || 'Could not update jobs');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function setModalPostStatus(newStatus) {
  if (!activeEasyModalPost) return;
  await setEasyPostStatus(activeEasyModalPost.id, newStatus);
}

function updateModalStatusChips(status) {
  const statusEl = document.getElementById('easyModalStatus');
  if (statusEl) {
    const labels = {
      DISCOVERED: '⚡ Ready',
      REQUIRES_QUESTIONNAIRE: '📋 Screening',
      APPLIED: '✓ Applied',
      NOT_FOUND: '🚫 Not Found',
      REJECTED: '✕ Dismissed',
    };
    statusEl.textContent = labels[status] || status;
  }

  // Highlight matching modal chip via inline onclick attribute value matching
  document.querySelectorAll('.modal-status-segmented .btn-modal-status-chip, .modal-status-toggle-wrap .btn-modal-status-chip').forEach((chip) => {
    const onclick = chip.getAttribute('onclick') || '';
    const isActive = onclick.includes(`'${status}'`);
    chip.classList.toggle('active', isActive);
  });
}

// =============================================
// SCREENING QUESTIONNAIRE MODAL
// =============================================

let activeScreeningPost = null;

/**
 * Parse screening questions from rejection_reason.
 * Supports both legacy format ("Questions: Q1; Q2; Q3") and
 * future JSON format ({"questions": [{"label": "...", "type": "...", "step": N}]})
 */
function parseScreeningQuestions(rejectionReason) {
  if (!rejectionReason) return [];

  const genericPlaceholders = [
    'requires screening questions',
    'multi-step questionnaire (saved for screening)',
    'multi-step form required manual input',
    'exceeded step limit, saved for screening',
  ];

  // Try JSON format first
  try {
    const parsed = JSON.parse(rejectionReason);
    if (parsed && Array.isArray(parsed.questions)) {
      return parsed.questions
        .map((q) => ({
          label: (q.label || q || '').trim(),
          type: q.type || null,
          step: q.step || null,
        }))
        .filter((q) => q.label && !genericPlaceholders.includes(q.label.toLowerCase()));
    }
  } catch (_) {}

  // Legacy string format: "Questions: Q1; Q2; Q3" or semicolon-separated
  let raw = rejectionReason.trim();
  if (raw.toLowerCase().startsWith('questions:')) {
    raw = raw.replace(/^questions:\s*/i, '').trim();
  }

  return raw
    .split(';')
    .map((q) => q.replace(/^\s*\*\s*|\s*\*\s*$/g, '').trim())
    .filter((q) => q && !genericPlaceholders.includes(q.toLowerCase()))
    .map((q) => ({ label: q, type: null, step: null }));
}

function findQuestionBankAnswer(label) {
  if (!label || !questionBankAnswers) return '';
  const normKey = label.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (questionBankAnswers[normKey]) return questionBankAnswers[normKey];

  // Smart aliases to standard answers
  if (/(?:middle name|middle_name)/i.test(label)) {
    if (questionBankAnswers['std_middle_name']) return questionBankAnswers['std_middle_name'];
    if (questionBankAnswers['middlename']) return questionBankAnswers['middlename'];
    return '__EMPTY__';
  }
  if (/(?:phone|mobile|contact number)/i.test(label)) {
    if (questionBankAnswers['std_phone']) return questionBankAnswers['std_phone'];
    if (questionBankAnswers['phonemobilenumber']) return questionBankAnswers['phonemobilenumber'];
  }
  if (/(?:email)/i.test(label)) {
    if (questionBankAnswers['std_email']) return questionBankAnswers['std_email'];
    if (questionBankAnswers['emailaddress']) return questionBankAnswers['emailaddress'];
  }
  if (/(?:city|current location|current city|present location)/i.test(label) && !/relocat/i.test(label)) {
    if (questionBankAnswers['std_location']) return questionBankAnswers['std_location'];
    if (questionBankAnswers['currentcitylocation']) return questionBankAnswers['currentcitylocation'];
  }
  if (/(?:current ctc|current salary|fix ctc|fixed ctc|in-hand salary)/i.test(label)) {
    if (questionBankAnswers['std_current_ctc']) return questionBankAnswers['std_current_ctc'];
    if (questionBankAnswers['currentctcsalaryinlpaorinr']) return questionBankAnswers['currentctcsalaryinlpaorinr'];
  }
  if (/(?:expected ctc|expected salary|desired compensation|expectation fix ctc|ectc)/i.test(label)) {
    if (questionBankAnswers['std_expected_ctc']) return questionBankAnswers['std_expected_ctc'];
    if (questionBankAnswers['expectedctcsalaryinlpaorinr']) return questionBankAnswers['expectedctcsalaryinlpaorinr'];
  }
  if (/(?:notice period|notice days|days left in your notice|how many days is your notice)/i.test(label)) {
    if (questionBankAnswers['std_notice_period']) return questionBankAnswers['std_notice_period'];
    if (questionBankAnswers['noticeperiodindays']) return questionBankAnswers['noticeperiodindays'];
  }
  if (/(?:total years|total experience|professional software engineering experience)/i.test(label)) {
    if (questionBankAnswers['std_experience_total']) return questionBankAnswers['std_experience_total'];
    if (questionBankAnswers['totalyearsofprofessionalsoftwareengineeringexperience']) return questionBankAnswers['totalyearsofprofessionalsoftwareengineeringexperience'];
  }
  if (/(?:english)/i.test(label)) {
    if (questionBankAnswers['std_english']) return questionBankAnswers['std_english'];
  }
  return '';
}

function setScreeningInpValue(normKey, val) {
  const inp = document.getElementById(`screeningAnsInp_${normKey}`);
  if (inp) {
    inp.value = val;
    inp.focus();
  }
}

function openScreeningModal(postId) {
  const post = easyApplyPosts.find((p) => p.id === postId);
  if (!post) return;
  activeScreeningPost = post;

  const modal = document.getElementById('modalScreeningQuestions');
  if (!modal) return;

  // Populate job info
  document.getElementById('screeningJobTitle').textContent = post.author_headline || 'Job Details';
  document.getElementById('screeningJobCompany').textContent = `🏢 ${post.author_name || 'Company'}`;
  document.getElementById('screeningJobLocation').textContent = `📍 ${post.location || 'India'}`;

  const dateText = typeof formatPostDateTimeWithRelative === 'function'
    ? formatPostDateTimeWithRelative(post)
    : (typeof formatDateTime === 'function' ? formatDateTime(post.created_at) : (post.created_at || '—'));
  document.getElementById('screeningJobDate').textContent = `📅 ${dateText}`;

  const linkEl = document.getElementById('screeningOpenLink');
  if (linkEl) linkEl.href = post.post_url || '#';

  // Parse and render questions
  const questions = parseScreeningQuestions(post.rejection_reason);
  const listEl = document.getElementById('screeningQuestionsList');
  const emptyEl = document.getElementById('screeningEmptyState');
  const applyNowBtn = document.getElementById('btnScreeningApplyNow');

  if (questions.length > 0) {
    listEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');

    let allQuestionsAnswered = true;

    listEl.innerHTML = questions.map((q, i) => {
      const normKey = q.label.toLowerCase().replace(/[^a-z0-9]/g, '');
      const typeTag = q.type
        ? `<div class="screening-q-type">${escapeHtml(q.type)}${q.step ? ` · Step ${q.step}` : ''}</div>`
        : (q.step ? `<div class="screening-q-type">Step ${q.step}</div>` : '');

      const savedAnswer = findQuestionBankAnswer(q.label);
      if (!savedAnswer) {
        allQuestionsAnswered = false;
      }

      let answerRow = '';
      if (savedAnswer === '__EMPTY__') {
        answerRow = `<div class="screening-saved-ans-pill" style="margin-top: 0.45rem; font-size: 0.74rem; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; padding: 0.2rem 0.55rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.35rem;">
                       <span>✓ Configured Blank:</span> <strong>(Will leave blank on apply)</strong>
                     </div>`;
      } else if (savedAnswer) {
        answerRow = `<div class="screening-saved-ans-pill" style="margin-top: 0.45rem; font-size: 0.74rem; background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.3); color: #4ade80; padding: 0.2rem 0.55rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.35rem;">
                       <span>✓ Saved in Question Bank:</span> <strong>${escapeHtml(savedAnswer)}</strong>
                     </div>`;
      } else {
        answerRow = `
          <div class="screening-inline-ans-box" id="screeningAnsBox_${normKey}">
            <div style="display: flex; gap: 0.35rem; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap;">
              <button type="button" class="btn btn-outline btn-xs" style="font-size: 0.7rem; padding: 0.12rem 0.45rem;" onclick="setScreeningInpValue('${normKey}', 'Yes')">Yes</button>
              <button type="button" class="btn btn-outline btn-xs" style="font-size: 0.7rem; padding: 0.12rem 0.45rem;" onclick="setScreeningInpValue('${normKey}', 'No')">No</button>
              <button type="button" class="btn btn-outline btn-xs" style="font-size: 0.7rem; padding: 0.12rem 0.45rem; border-color: rgba(239, 68, 68, 0.4); color: #f87171;" onclick="setScreeningInpValue('${normKey}', '__EMPTY__')">🚫 Leave Blank</button>
            </div>
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              <input type="text" class="screening-inline-input" id="screeningAnsInp_${normKey}" placeholder="Type answer for Question Bank (e.g. 3, Immediate, Yes)..." onkeydown="if(event.key==='Enter') saveSingleInlineAnswer('${normKey}', '${escapeHtml(q.label)}', this.nextElementSibling)" />
              <button type="button" class="btn btn-warning btn-xs screening-inline-save-btn" onclick="saveSingleInlineAnswer('${normKey}', '${escapeHtml(q.label)}', this)">Save Answer</button>
            </div>
          </div>
        `;
      }

      return `
        <div class="screening-question-card">
          <span class="screening-q-num">${i + 1}</span>
          <div style="flex: 1;">
            <div class="screening-q-text">${escapeHtml(q.label)}</div>
            ${typeTag}
            <div id="screeningAnsSlot_${normKey}">
              ${answerRow}
            </div>
          </div>
        </div>
      `;
    }).join('');

    if (applyNowBtn) {
      if (allQuestionsAnswered) {
        applyNowBtn.classList.remove('hidden');
      } else {
        applyNowBtn.classList.add('hidden');
      }
    }
  } else {
    listEl.classList.add('hidden');
    listEl.innerHTML = '';
    emptyEl.classList.remove('hidden');
    if (applyNowBtn) applyNowBtn.classList.add('hidden');
  }

  modal.classList.remove('hidden');
}

function closeScreeningModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('close-x') && !e.target.classList.contains('modal-close-btn') && !e.target.classList.contains('close-dialog-btn')) {
    return;
  }
  const modal = document.getElementById('modalScreeningQuestions');
  if (modal) modal.classList.add('hidden');
  activeScreeningPost = null;
}

async function saveSingleInlineAnswer(normKey, label, btn) {
  const input = document.getElementById(`screeningAnsInp_${normKey}`);
  if (!input) return;
  const val = input.value.trim();
  if (!val) {
    showAlert('Empty Answer', 'Please enter an answer or select Leave Blank.');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Saving...';
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: { [normKey]: val, [label]: val } }),
    });

    if (res.ok) {
      showToast(val === '__EMPTY__' ? '✓ Configured to submit blank!' : '✓ Answer saved to Question Bank!', 'success');
      // Update local dictionary immediately
      if (questionBankAnswers) {
        questionBankAnswers[normKey] = val;
      }
      // Replace inline box with saved pill
      const slot = document.getElementById(`screeningAnsSlot_${normKey}`);
      if (slot) {
        if (val === '__EMPTY__') {
          slot.innerHTML = `
            <div class="screening-saved-ans-pill" style="margin-top: 0.45rem; font-size: 0.74rem; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; padding: 0.2rem 0.55rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.35rem;">
              <span>✓ Configured Blank:</span> <strong>(Will leave blank on apply)</strong>
            </div>
          `;
        } else {
          slot.innerHTML = `
            <div class="screening-saved-ans-pill" style="margin-top: 0.45rem; font-size: 0.74rem; background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.3); color: #4ade80; padding: 0.2rem 0.55rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.35rem;">
              <span>✓ Saved in Question Bank:</span> <strong>${escapeHtml(val)}</strong>
            </div>
          `;
        }
      }
      // Refresh Question Bank in background
      fetchQuestionBank(false);

      // Check if all questions are now answered
      if (activeScreeningPost) {
        const questions = parseScreeningQuestions(activeScreeningPost.rejection_reason);
        const allAnswered = questions.every((q) => Boolean(findQuestionBankAnswer(q.label)));
        const applyNowBtn = document.getElementById('btnScreeningApplyNow');
        if (applyNowBtn && allAnswered) {
          applyNowBtn.classList.remove('hidden');
        }
      }
    } else {
      const err = await res.json();
      showAlert('Save Error', err.detail || 'Could not save answer.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Save Answer';
    }
  }
}

async function applyToCurrentScreeningPost() {
  if (!activeScreeningPost) return;
  const postId = activeScreeningPost.id;
  closeScreeningModal();
  await applyToSingleEasyPost(postId);
}

function openScreeningFromDetails() {
  if (!activeEasyModalPost) return;
  const postId = activeEasyModalPost.id;
  closeEasyDetailsModal();
  openScreeningModal(postId);
}

function copyScreeningLink() {
  if (activeScreeningPost && activeScreeningPost.post_url) {
    navigator.clipboard.writeText(activeScreeningPost.post_url).then(() => {
      showToast('✓ Job link copied for manual screening!', 'success');
    }).catch(() => {
      showToast('Failed to copy to clipboard', 'error');
    });
  }
}

async function markScreeningAsReady() {
  if (!activeScreeningPost) return;
  await setEasyPostStatus(activeScreeningPost.id, 'DISCOVERED');
  closeScreeningModal();
  showToast('✓ Marked as Ready — you can now apply manually', 'success');
}

async function triggerScreeningRescan() {
  if (!activeScreeningPost) return;
  const postId = activeScreeningPost.id;
  const title = activeScreeningPost.author_headline || 'this job';

  const confirmed = await showConfirm(
    'Re-Scan Screening Questions',
    `Re-crawl all Easy Apply form pages for "${title}" to collect every question?\n\nThis will navigate through all steps with dummy data but will NOT submit the application.`,
    { confirmText: 'Re-Scan Now' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/easy-apply/${postId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_only: true }),
    });
    if (res.ok) {
      showToast('⚡ Re-scan queued — questions will be updated when complete', 'info');
      closeScreeningModal();
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Re-Scan Failed', err.detail || 'Could not start re-scan.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// =============================================
// BULK SEARCH & CSV KEYWORD IMPORT
// =============================================

let bulkParsedKeywords = [];

function openBulkSearchModal() {
  const modal = document.getElementById('modalBulkEasySearch');
  if (!modal) return;

  // Pre-fill location & time filter from active crawler form if set
  const currentLoc = document.getElementById('easySearchLocation')?.value || 'India';
  const currentTime = document.getElementById('easyTimeFilter')?.value || '24h';
  const locInput = document.getElementById('bulkSearchLocation');
  const timeSelect = document.getElementById('bulkTimeFilter');
  if (locInput) locInput.value = currentLoc;
  if (timeSelect) timeSelect.value = currentTime;

  // Pre-fill keywords from active search query if textarea is currently empty
  const activeQuery = (document.getElementById('easySearchQuery')?.value || '').trim();
  const kwTextarea = document.getElementById('bulkKeywordsInput');
  if (kwTextarea && !kwTextarea.value.trim() && activeQuery) {
    kwTextarea.value = activeQuery;
    handleBulkKeywordsInput(activeQuery);
  } else if (kwTextarea && kwTextarea.value.trim()) {
    handleBulkKeywordsInput(kwTextarea.value);
  }

  modal.classList.remove('hidden');
}

function closeBulkSearchModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('close-x')) {
    return;
  }
  const modal = document.getElementById('modalBulkEasySearch');
  if (modal) modal.classList.add('hidden');
}

function parseKeywordsString(text) {
  if (!text) return [];
  const ignoredHeaders = ['role', 'roles', 'keyword', 'keywords', 'title', 'titles', 'job title', 'job_title', 'search'];
  const rawList = text.split(/[\r\n,;|\t]+/);
  const seen = new Set();
  const result = [];

  for (let item of rawList) {
    let clean = item.trim().replace(/^["']|["']$/g, '');
    if (!clean || clean.length < 2) continue;
    if (ignoredHeaders.includes(clean.toLowerCase())) continue;
    const lower = clean.toLowerCase();
    if (!seen.has(lower)) {
      seen.add(lower);
      result.push(clean);
    }
  }
  return result;
}

function renderBulkKeywordsChips() {
  const container = document.getElementById('bulkKeywordsPreview');
  const countBadge = document.getElementById('bulkKeywordsCount');
  const submitBtn = document.getElementById('btnLaunchBulkCrawl');
  const submitText = document.getElementById('btnLaunchBulkCrawlText');

  if (!container || !countBadge) return;

  const count = bulkParsedKeywords.length;
  countBadge.textContent = `${count} keyword${count === 1 ? '' : 's'}`;

  if (count > 0) {
    container.classList.remove('hidden');
    container.innerHTML = bulkParsedKeywords.map((kw, i) => `
      <span class="bulk-keyword-chip">
        <span>${escapeHtml(kw)}</span>
        <span class="chip-del" onclick="removeBulkKeyword(${i})" title="Remove keyword">&times;</span>
      </span>
    `).join('');

    if (submitBtn) submitBtn.style.opacity = '1';
    if (submitText) submitText.textContent = `Queue ${count} Search${count === 1 ? '' : 'es'}`;
  } else {
    container.classList.add('hidden');
    container.innerHTML = '';
    if (submitBtn) submitBtn.style.opacity = '0.85';
    if (submitText) submitText.textContent = 'Queue Searches';
  }
}

function handleBulkKeywordsInput(text) {
  bulkParsedKeywords = parseKeywordsString(text);
  renderBulkKeywordsChips();
}

function handleBulkCsvUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function(e) {
    const content = e.target.result || '';
    const keywords = parseKeywordsString(content);
    if (keywords.length === 0) {
      showAlert('No Keywords Found', 'Could not detect any role names in the uploaded file. Please ensure it contains comma-separated or line-separated text.');
      return;
    }
    bulkParsedKeywords = keywords;
    const textarea = document.getElementById('bulkKeywordsInput');
    if (textarea) textarea.value = bulkParsedKeywords.join(', ');
    renderBulkKeywordsChips();
    showToast(`✓ Imported ${keywords.length} keywords from ${file.name}`, 'success');
  };
  reader.onerror = function() {
    showAlert('Upload Error', 'Failed to read the selected file.');
  };
  reader.readAsText(file);
  event.target.value = '';
}

function removeBulkKeyword(index) {
  if (index >= 0 && index < bulkParsedKeywords.length) {
    bulkParsedKeywords.splice(index, 1);
    const textarea = document.getElementById('bulkKeywordsInput');
    if (textarea) textarea.value = bulkParsedKeywords.join(', ');
    renderBulkKeywordsChips();
  }
}

function clearBulkKeywords() {
  bulkParsedKeywords = [];
  const textarea = document.getElementById('bulkKeywordsInput');
  if (textarea) textarea.value = '';
  renderBulkKeywordsChips();
}

async function submitBulkEasySearch() {
  const kwTextarea = document.getElementById('bulkKeywordsInput');
  const rawInput = (kwTextarea?.value || '').trim();
  if ((!bulkParsedKeywords || bulkParsedKeywords.length === 0) && rawInput) {
    bulkParsedKeywords = parseKeywordsString(rawInput);
    renderBulkKeywordsChips();
  }

  if (!bulkParsedKeywords || bulkParsedKeywords.length === 0) {
    if (kwTextarea) {
      kwTextarea.focus();
      kwTextarea.style.borderColor = '#f43f5e';
      setTimeout(() => { kwTextarea.style.borderColor = ''; }, 2000);
    }
    showAlert('No Keywords Provided', 'Please enter, paste, or upload at least one role keyword (e.g. "Full Stack Developer, Python Developer") to queue searches.', { centerPopup: true });
    return;
  }

  const location = (document.getElementById('bulkSearchLocation')?.value || 'India').trim();
  const timeFilter = document.getElementById('bulkTimeFilter')?.value || '24h';
  const count = bulkParsedKeywords.length;

  const confirmed = await showConfirm(
    'Launch Bulk LinkedIn Search',
    `Enqueue ${count} searches sequentially in background for "${location}"?\n\nEach search will run one after another in persistent Firefox.`,
    { confirmText: `Queue ${count} Searches` }
  );
  if (!confirmed) return;

  const submitBtn = document.getElementById('btnLaunchBulkCrawl');
  if (submitBtn) submitBtn.disabled = true;

  const cycles = parseInt(document.getElementById('easyCrawlerCycles')?.value || '8', 10);
  const pacing = document.getElementById('selectEasyPacing')?.value || 'safe';

  try {
    const res = await fetch('/api/scrape/easy-apply/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        keywords: bulkParsedKeywords,
        location: location,
        time_filter: timeFilter,
        cycles: isNaN(cycles) ? 8 : cycles,
        pacing: pacing,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      showToast(`🚀 Enqueued ${data.count || count} bulk search tasks!`, 'success');
      closeBulkSearchModal();
      clearBulkKeywords();
      if (typeof startTaskPolling === 'function') startTaskPolling();
      if (typeof toggleTaskDrawer === 'function') {
        toggleTaskDrawer(true);
      } else if (typeof toggleTaskLogs === 'function') {
        toggleTaskLogs(true);
      }
    } else {
      const err = await res.json();
      showAlert('Bulk Search Error', err.detail || 'Could not enqueue bulk search tasks.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

// --- Centralized Question & Answer Bank Controller ---
let questionBankData = null;
let questionBankAnswers = {};
let activeQBankCategory = 'all';
let qbankSearchFilter = '';
let rateLimitTimerInterval = null;

async function fetchQuestionBank(renderAfter = true) {
  try {
    const res = await fetch('/api/easy-apply/questions');
    if (!res.ok) return;
    const data = await res.json();
    questionBankData = data;

    // Cache answers in map for instant lookup
    questionBankAnswers = {};
    if (data.questions && Array.isArray(data.questions)) {
      data.questions.forEach((q) => {
        if (q.answer) {
          questionBankAnswers[q.key] = q.answer;
          if (q.id) questionBankAnswers[q.id] = q.answer;
        }
      });
    }

    // Update Question Bank button counter
    const countEl = document.getElementById('totalQuestionsCount');
    if (countEl) countEl.textContent = data.total_count || 0;

    const allPillCount = document.getElementById('qbankCountAll');
    if (allPillCount) allPillCount.textContent = data.total_count || 0;

    const unansweredPillCount = document.getElementById('qbankCountUnanswered');
    if (unansweredPillCount) unansweredPillCount.textContent = data.pending_count || 0;

    // Update pending alert banner and button badge
    const pendingCount = data.pending_count || 0;
    const alertBanner = document.getElementById('qbankPendingAlertBanner');
    const bannerCountEl = document.getElementById('qbankPendingCountBanner');
    const btnBadge = document.getElementById('qbankPendingBtnBadge');

    if (pendingCount > 0) {
      if (alertBanner) alertBanner.classList.remove('hidden');
      if (bannerCountEl) bannerCountEl.textContent = pendingCount;
      if (btnBadge) {
        btnBadge.classList.remove('hidden');
        btnBadge.textContent = `${pendingCount} pending`;
      }
    } else {
      if (alertBanner) alertBanner.classList.add('hidden');
      if (btnBadge) btnBadge.classList.add('hidden');
    }

    if (renderAfter) {
      renderQuestionBankList();
    }
  } catch (err) {
    console.error('Error fetching question bank:', err);
  }
}

function openQuestionBankModal(cat) {
  const modal = document.getElementById('modalQuestionBank');
  if (!modal) return;
  modal.classList.remove('hidden');

  if (cat) {
    activeQBankCategory = cat;
    document.querySelectorAll('.qbank-cat-pill').forEach((p) => {
      if (p.getAttribute('data-cat') === cat) {
        p.classList.add('active');
      } else {
        p.classList.remove('active');
      }
    });
  }

  fetchQuestionBank(true);
}

function closeQuestionBankModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('close-x') && !e.target.classList.contains('modal-close-btn') && !e.target.classList.contains('close-dialog-btn') && !e.target.closest('.close-dialog-btn')) {
    return;
  }
  const modal = document.getElementById('modalQuestionBank');
  if (modal) modal.classList.add('hidden');
}

function setQuestionBankCategory(cat, btn) {
  activeQBankCategory = cat;
  document.querySelectorAll('.qbank-cat-pill').forEach((p) => p.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderQuestionBankList();
}

function filterQuestionBankList() {
  const input = document.getElementById('qbankSearchInput');
  qbankSearchFilter = (input ? input.value : '').toLowerCase().trim();
  renderQuestionBankList();
}

function renderQuestionBankList() {
  const listEl = document.getElementById('qbankQuestionsList');
  if (!listEl) return;

  if (!questionBankData || !questionBankData.questions) {
    listEl.innerHTML = '<div class="qbank-loading"><span class="spinner-sm"></span> Loading questions...</div>';
    return;
  }

  let questions = questionBankData.questions;

  // Filter by category
  if (activeQBankCategory === 'unanswered') {
    questions = questions.filter((q) => !q.answer || !q.answer.trim());
  } else if (activeQBankCategory !== 'all') {
    questions = questions.filter((q) => q.category === activeQBankCategory);
  }

  // Filter by search keyword
  if (qbankSearchFilter) {
    questions = questions.filter((q) =>
      q.question.toLowerCase().includes(qbankSearchFilter) ||
      (q.answer && q.answer.toLowerCase().includes(qbankSearchFilter))
    );
  }

  // Update footer statistics
  const progressEl = document.getElementById('qbankAnsweredProgress');
  if (progressEl && questionBankData) {
    progressEl.innerHTML = `<strong>${questionBankData.answered_count}</strong> of <strong>${questionBankData.total_count}</strong> questions answered`;
  }

  if (questions.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
        <span style="font-size: 1.8rem; display: block; margin-bottom: 0.5rem;">🔍</span>
        <strong style="color: #cbd5e1;">No questions match your filter</strong>
        <p style="font-size: 0.76rem; margin-top: 0.25rem;">Try selecting a different category or clearing the search keyword.</p>
      </div>
    `;
    return;
  }

  listEl.innerHTML = questions.map((q) => {
    const isAnswered = Boolean(q.answer && q.answer.trim());
    const occTag = q.occurrences > 1
      ? `<span class="qbank-badge qbank-badge-occ" title="Captured across ${q.occurrences} different jobs">From ${q.occurrences} jobs</span>`
      : '';
    const stdTag = q.is_standard
      ? `<span class="qbank-badge qbank-badge-standard" title="Standard Candidate Profile Question">Standard</span>`
      : '';
    const catTag = `<span class="qbank-badge qbank-badge-cat">${escapeHtml(q.category || 'general')}</span>`;
    const ansBadge = isAnswered
      ? `<span class="qbank-badge qbank-badge-answered">✓ Answered</span>`
      : `<span class="qbank-badge qbank-badge-pending">⚠️ Pending Answer</span>`;

    const sampleJobInfo = !q.is_standard && q.sample_jobs && q.sample_jobs.length > 0
      ? `<div class="qbank-sample-jobs" title="${escapeHtml(q.sample_jobs.join(' • '))}">
           <span>💼</span> <span>${escapeHtml(q.sample_jobs.slice(0, 2).join(' • '))}</span>
         </div>`
      : '';

    const inputVal = q.answer || '';
    const placeholder = q.default_placeholder || 'Enter your default answer...';

    return `
      <div class="qbank-card" data-key="${escapeHtml(q.key)}">
        <div class="qbank-card-header">
          <div class="qbank-question-label">${escapeHtml(q.question)}</div>
          <div class="qbank-badges">
            ${stdTag}
            ${catTag}
            ${occTag}
            ${ansBadge}
          </div>
        </div>
        <input
          type="text"
          class="qbank-answer-input"
          data-key="${escapeHtml(q.key)}"
          placeholder="${escapeHtml(placeholder)}"
          value="${escapeHtml(inputVal)}"
        />
        ${sampleJobInfo}
      </div>
    `;
  }).join('');
}

async function saveQuestionBankAnswers() {
  const btn = document.getElementById('btnSaveQuestionBank');
  const inputs = document.querySelectorAll('.qbank-answer-input');
  const answers = {};

  inputs.forEach((inp) => {
    const key = inp.getAttribute('data-key');
    const val = inp.value.trim();
    if (key) {
      answers[key] = val;
    }
  });

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-sm"></span> <span>Saving...</span>`;
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    });

    if (res.ok) {
      showToast('✓ Answers saved to Question Bank!', 'success');
      await fetchQuestionBank(true);
    } else {
      const err = await res.json();
      showAlert('Save Error', err.detail || 'Could not save answers.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>Save Answers</span>`;
    }
  }
}

// --- Safeguard Rate Limit Watchdog & Banner ---
async function checkRateLimitSafeguard() {
  const banner = document.getElementById('easyRateLimitBanner');
  const msgEl = document.getElementById('easyRateLimitMsg');
  const timerEl = document.getElementById('easyRateLimitTimer');
  if (!banner) return;

  try {
    const res = await fetch('/api/easy-apply/rate-limit-status');
    if (!res.ok) return;
    const data = await res.json();

    if (data.is_paused && data.seconds_remaining > 0) {
      banner.classList.remove('hidden');
      if (msgEl) msgEl.textContent = data.safeguard_reason || 'LinkedIn temporarily paused Easy Apply ("applying at a fast pace"). Automation is paused to protect your account.';

      if (rateLimitTimerInterval) clearInterval(rateLimitTimerInterval);

      let remaining = data.seconds_remaining;
      const updateTimer = () => {
        if (remaining <= 0) {
          banner.classList.add('hidden');
          if (rateLimitTimerInterval) clearInterval(rateLimitTimerInterval);
          return;
        }
        const m = Math.floor(remaining / 60);
        const s = remaining % 60;
        if (timerEl) timerEl.textContent = `(${m}m ${s < 10 ? '0' : ''}${s}s)`;
        remaining--;
      };
      updateTimer();
      rateLimitTimerInterval = setInterval(updateTimer, 1000);
    } else {
      banner.classList.add('hidden');
      if (rateLimitTimerInterval) clearInterval(rateLimitTimerInterval);
    }
  } catch (err) {
    console.warn('Error checking rate limit status:', err);
  }
}

async function resumeEasyApplySafeguard() {
  const confirmed = await showConfirm(
    'Resume Easy Apply Now?',
    'Are you sure you want to clear the safeguard pause? If LinkedIn recently displayed an automated activity warning, resuming too quickly may risk restrictions. Ensure you use Safe or Extra Slow pacing.',
    { confirmText: 'Resume Easy Apply' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/easy-apply/rate-limit-resume', { method: 'POST' });
    if (res.ok) {
      const banner = document.getElementById('easyRateLimitBanner');
      if (banner) banner.classList.add('hidden');
      if (rateLimitTimerInterval) clearInterval(rateLimitTimerInterval);
      showToast('✓ Safeguard pause cleared. Easy Apply resumed.', 'success');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// Auto-fetch question bank count on script execution
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => fetchQuestionBank(false));
  } else {
    fetchQuestionBank(false);
  }
}

window.fetchEasyApplyPosts = fetchEasyApplyPosts;
window.filterEasyApplyStatus = filterEasyApplyStatus;
window.handleEasyTableSearch = handleEasyTableSearch;
window.triggerEasyApplyCrawl = triggerEasyApplyCrawl;
window.triggerSingleEasyApply = triggerSingleEasyApply;
window.copyEasyJobLink = copyEasyJobLink;
window.openEasyDetailsModal = openEasyDetailsModal;
window.closeEasyDetailsModal = closeEasyDetailsModal;
window.copyEasyModalLink = copyEasyModalLink;
window.triggerEasyModalApply = triggerEasyModalApply;
window.toggleSelectEasyJob = toggleSelectEasyJob;
window.toggleSelectAllEasyJobs = toggleSelectAllEasyJobs;
window.batchCopyEasyLinks = batchCopyEasyLinks;
window.batchDismissEasyJobs = batchDismissEasyJobs;
window.batchApplySelectedEasyJobs = batchApplySelectedEasyJobs;
window.toggleEasyStatusMenu = toggleEasyStatusMenu;
window.closeAllEasyStatusMenus = closeAllEasyStatusMenus;
window.setEasyPostStatus = setEasyPostStatus;
window.batchSetEasyStatus = batchSetEasyStatus;
window.setModalPostStatus = setModalPostStatus;
window.clearEasySelection = clearEasySelection;
window.openScreeningModal = openScreeningModal;
window.closeScreeningModal = closeScreeningModal;
window.openScreeningFromDetails = openScreeningFromDetails;
window.copyScreeningLink = copyScreeningLink;
window.markScreeningAsReady = markScreeningAsReady;
window.triggerScreeningRescan = triggerScreeningRescan;
window.openBulkSearchModal = openBulkSearchModal;
window.closeBulkSearchModal = closeBulkSearchModal;
window.handleBulkCsvUpload = handleBulkCsvUpload;
window.handleBulkKeywordsInput = handleBulkKeywordsInput;
window.removeBulkKeyword = removeBulkKeyword;
window.clearBulkKeywords = clearBulkKeywords;
window.submitBulkEasySearch = submitBulkEasySearch;
window.applyEasyDateFilter = applyEasyDateFilter;
window.openQuestionBankModal = openQuestionBankModal;
window.closeQuestionBankModal = closeQuestionBankModal;
window.setQuestionBankCategory = setQuestionBankCategory;
window.filterQuestionBankList = filterQuestionBankList;
window.saveQuestionBankAnswers = saveQuestionBankAnswers;
window.saveSingleInlineAnswer = saveSingleInlineAnswer;
window.applyToCurrentScreeningPost = applyToCurrentScreeningPost;
window.resumeEasyApplySafeguard = resumeEasyApplySafeguard;
window.checkRateLimitSafeguard = checkRateLimitSafeguard;

