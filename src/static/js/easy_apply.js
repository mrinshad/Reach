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

    const res = await fetch(`/api/posts?${params.toString()}`);
    if (!res.ok) return;

    const data = await res.json();
    easyApplyPosts = data.posts || [];

    updateEasyKPIs(easyApplyPosts);
    renderEasyApplyTable();
  } catch (err) {
    console.error('Error fetching Easy Apply posts:', err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #ef4444;">Error loading jobs: ${escapeHtml(err.message)}</td></tr>`;
  }
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

  // Try JSON format first
  try {
    const parsed = JSON.parse(rejectionReason);
    if (parsed && Array.isArray(parsed.questions)) {
      return parsed.questions.map((q) => ({
        label: q.label || q,
        type: q.type || null,
        step: q.step || null,
      }));
    }
  } catch (_) {
    // Not JSON — use legacy string parsing
  }

  // Legacy format: "Questions: Q1; Q2; Q3"
  let raw = rejectionReason;
  if (raw.startsWith('Questions: ')) {
    raw = raw.substring('Questions: '.length);
  }
  return raw.split('; ').filter(Boolean).map((q) => ({ label: q.trim(), type: null, step: null }));
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

  if (questions.length > 0) {
    listEl.classList.remove('hidden');
    emptyEl.classList.add('hidden');

    listEl.innerHTML = questions.map((q, i) => {
      const typeTag = q.type
        ? `<div class="screening-q-type">${escapeHtml(q.type)}${q.step ? ` · Step ${q.step}` : ''}</div>`
        : (q.step ? `<div class="screening-q-type">Step ${q.step}</div>` : '');
      return `
        <div class="screening-question-card">
          <span class="screening-q-num">${i + 1}</span>
          <div>
            <div class="screening-q-text">${escapeHtml(q.label)}</div>
            ${typeTag}
          </div>
        </div>
      `;
    }).join('');
  } else {
    listEl.classList.add('hidden');
    listEl.innerHTML = '';
    emptyEl.classList.remove('hidden');
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

    if (submitBtn) submitBtn.disabled = false;
    if (submitText) submitText.textContent = `Queue ${count} Search${count === 1 ? '' : 'es'}`;
  } else {
    container.classList.add('hidden');
    container.innerHTML = '';
    if (submitBtn) submitBtn.disabled = true;
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
  if (!bulkParsedKeywords || bulkParsedKeywords.length === 0) {
    showAlert('No Keywords', 'Please enter or import at least one keyword to search.');
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

  try {
    const res = await fetch('/api/scrape/easy-apply/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        keywords: bulkParsedKeywords,
        location: location,
        time_filter: timeFilter,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      showToast(`🚀 Enqueued ${data.count || count} bulk search tasks!`, 'success');
      closeBulkSearchModal();
      clearBulkKeywords();
      if (typeof startTaskPolling === 'function') startTaskPolling();
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

