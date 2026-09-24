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

function updateEasyKPIs(posts) {
  const total = posts.length;
  const applied = posts.filter((p) => p.status === 'APPLIED').length;
  const questionnaire = posts.filter((p) => p.status === 'REQUIRES_QUESTIONNAIRE').length;
  const ready = posts.filter((p) => p.status === 'DISCOVERED').length;

  const totalEl = document.getElementById('easyKpiTotal');
  if (totalEl) totalEl.textContent = total;

  const appliedEl = document.getElementById('easyKpiApplied');
  if (appliedEl) appliedEl.textContent = applied;

  const qEl = document.getElementById('easyKpiQuestionnaire');
  if (qEl) qEl.textContent = questionnaire;

  const readyEl = document.getElementById('easyKpiReady');
  if (readyEl) readyEl.textContent = ready;

  // Filter Pill Counter Badges
  const countAll = document.getElementById('countPillAll');
  if (countAll) countAll.textContent = total;

  const countReady = document.getElementById('countPillReady');
  if (countReady) countReady.textContent = ready;

  const countScreening = document.getElementById('countPillScreening');
  if (countScreening) countScreening.textContent = questionnaire;

  const countApplied = document.getElementById('countPillApplied');
  if (countApplied) countApplied.textContent = applied;

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

    // Status Badge
    let statusBadge = '<span class="tag-easy-status discovered">⚡ Ready</span>';
    if (post.status === 'APPLIED') {
      statusBadge = '<span class="tag-easy-status applied">✓ Applied</span>';
    } else if (post.status === 'REQUIRES_QUESTIONNAIRE') {
      statusBadge = '<span class="tag-easy-status questionnaire" title="Requires questionnaire screening">📋 Screening</span>';
    } else if (post.status === 'REJECTED') {
      statusBadge = '<span class="tag-easy-status rejected">✕ Dismissed</span>';
    }

    const expText = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
    const dateText = typeof formatPostDateTimeWithRelative === 'function'
      ? formatPostDateTimeWithRelative(post)
      : (typeof formatDateTime === 'function' ? formatDateTime(post.created_at) : (post.created_at || '—'));

    let actionBtn = `<button class="btn btn-primary btn-xs" onclick="triggerSingleEasyApply('${post.id}')" title="Run Easy Apply submission"><span>⚡ Apply</span></button>`;
    if (post.status === 'APPLIED') {
      actionBtn = `<span class="tag-easy-status applied" style="opacity: 0.9; font-size: 0.68rem; cursor: default;">✓ Submitted</span>`;
    } else if (post.status === 'REQUIRES_QUESTIONNAIRE') {
      actionBtn = `<button class="btn btn-outline btn-xs" onclick="openEasyDetailsModal('${post.id}')" title="Screen questionnaire requirements" style="color: #fbbf24; border-color: rgba(245, 158, 11, 0.4);"><span>📋 Screen</span></button>`;
    }

    tr.innerHTML = `
      <td width="38">
        <input type="checkbox" class="easy-checkbox" value="${post.id}" ${isSelected ? 'checked' : ''} onchange="toggleSelectEasyJob('${post.id}', this.checked)" />
      </td>
      <td>
        <div class="easy-role-cell">
          <a href="javascript:void(0)" onclick="openEasyDetailsModal('${post.id}')" class="easy-job-title-link" title="Click to view full job details">
            ${escapeHtml(post.author_headline || 'Software Role')}
          </a>
          <span class="easy-company-name">
            <span style="opacity: 0.7;">🏢</span>
            <span>${escapeHtml(post.author_name || 'Company')}</span>
          </span>
        </div>
      </td>
      <td width="190">
        <span class="easy-location-text" title="${escapeHtml(post.location || 'India')}">
          <span style="opacity: 0.7;">📍</span>
          <span>${escapeHtml(post.location || 'India')}</span>
        </span>
      </td>
      <td width="105">
        <span class="pill-badge badge-exp" style="font-size: 0.7rem;">${escapeHtml(expText)}</span>
      </td>
      <td width="135">
        ${statusBadge}
      </td>
      <td width="165">
        <span class="easy-date-text" title="${escapeHtml(post.created_at || '')}">${escapeHtml(dateText)}</span>
      </td>
      <td width="145" style="text-align: right;">
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

  document.getElementById('easyModalJobTitle').textContent = post.author_headline || 'Job Details';
  document.getElementById('easyModalCompany').textContent = post.author_name || 'N/A';
  document.getElementById('easyModalLocation').textContent = post.location || 'India';
  const expText = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
  document.getElementById('easyModalExp').textContent = expText;
  document.getElementById('easyModalStatus').textContent = post.status;
  document.getElementById('easyModalFullText').textContent = post.full_text || 'No description extracted.';

  const linkEl = document.getElementById('easyModalLink');
  if (linkEl) {
    linkEl.href = post.post_url || '#';
  }

  // Questionnaire box
  const qBox = document.getElementById('easyModalQuestionnaireBox');
  const qNotes = document.getElementById('easyModalQuestionnaireNotes');
  if (post.status === 'REQUIRES_QUESTIONNAIRE' && post.rejection_reason) {
    if (qBox) qBox.classList.remove('hidden');
    if (qNotes) qNotes.textContent = post.rejection_reason;
  } else {
    if (qBox) qBox.classList.add('hidden');
  }

  modal.classList.remove('hidden');
}

function closeEasyDetailsModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('modal-close-btn')) {
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
