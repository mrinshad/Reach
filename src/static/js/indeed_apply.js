/**
 * Reach — Indeed Job Portal & Indeed Apply Workspace Controller
 * (src/static/js/indeed_apply.js)
 *
 * Manages autonomous Indeed job discovery, in-stream recruiter email harvesting from JDs,
 * Question Bank screening automation, and multi-step Indeed Apply submission wizard.
 */

const indeedState = {
  posts: [],
  filteredPosts: [],
  statusFilter: 'ALL',
  emailOnlyFilter: false,
  sortByEmail: false,
  searchKeyword: '',
  dateFrom: '',
  dateTo: '',
  selectedIds: new Set(),
  loading: false,
  page: 1,
  limit: 50,
};

async function fetchIndeedApplyPosts() {
  const tbody = document.getElementById('indeedApplyTableBody');
  if (!tbody) return;

  indeedState.loading = true;
  tbody.innerHTML = `
    <tr>
      <td colspan="7" style="text-align: center; padding: 3rem; color: #64748b;">
        <span class="inline-spinner" style="margin-right: 0.5rem;"></span> Loading Indeed Apply opportunities...
      </td>
    </tr>
  `;

  try {
    const params = new URLSearchParams({
      category: 'INDEED_APPLY',
      limit: '250',
    });

    params.append('status', indeedState.statusFilter || 'ALL');
    if (indeedState.emailOnlyFilter) {
      params.append('has_email', 'true');
    }
    if (indeedState.sortByEmail) {
      params.append('order_by', 'email_desc');
    }
    if (indeedState.searchKeyword) {
      params.append('search', indeedState.searchKeyword);
    }
    if (indeedState.dateFrom) {
      params.append('from_date', indeedState.dateFrom);
    }
    if (indeedState.dateTo) {
      params.append('to_date', indeedState.dateTo);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    indeedState.posts = (data && data.posts) || [];
    applyIndeedFilters();
    updateIndeedKpiRibbon();
  } catch (err) {
    console.error('Error fetching Indeed Apply posts:', err);
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 2.5rem; color: #f43f5e;">
          Failed to load Indeed opportunities. Please refresh or check connection.
        </td>
      </tr>
    `;
  } finally {
    indeedState.loading = false;
  }
}

async function updateIndeedKpiRibbon() {
  try {
    const res = await fetch('/api/stats');
    const stats = await res.json();

    const elTotal = document.getElementById('indeedKpiTotal');
    if (elTotal) elTotal.textContent = stats.indeed_total || 0;

    const elApplied = document.getElementById('indeedKpiApplied');
    if (elApplied) elApplied.textContent = stats.indeed_applied || 0;

    const elQuest = document.getElementById('indeedKpiQuestionnaire');
    if (elQuest) elQuest.textContent = stats.indeed_questionnaire || 0;

    const elReady = document.getElementById('indeedKpiReady');
    if (elReady) elReady.textContent = stats.indeed_pending || 0;

    const elNotFound = document.getElementById('indeedKpiNotFound');
    if (elNotFound) elNotFound.textContent = stats.indeed_not_found || 0;

    // Filter pills counters
    const countAll = document.getElementById('countIndeedPillAll');
    if (countAll) countAll.textContent = stats.indeed_total || 0;

    const countReady = document.getElementById('countIndeedPillReady');
    if (countReady) countReady.textContent = stats.indeed_pending || 0;

    const countScreening = document.getElementById('countIndeedPillScreening');
    if (countScreening) countScreening.textContent = stats.indeed_questionnaire || 0;

    const countApplied = document.getElementById('countIndeedPillApplied');
    if (countApplied) countApplied.textContent = stats.indeed_applied || 0;

    const countEmail = document.getElementById('countIndeedPillEmail');
    if (countEmail) countEmail.textContent = stats.indeed_emails_harvested || 0;

    const countNotFound = document.getElementById('countIndeedPillNotFound');
    if (countNotFound) countNotFound.textContent = stats.indeed_not_found || 0;

    const countRerunBtn = document.getElementById('countRerunScreenedIndeedBtn');
    if (countRerunBtn) countRerunBtn.textContent = stats.indeed_questionnaire || 0;

    const sidebarBadge = document.getElementById('countIndeedApply');
    if (sidebarBadge) {
      const pendingVal = stats.indeed_pending || 0;
      sidebarBadge.textContent = pendingVal;
      sidebarBadge.title = `${pendingVal} Indeed Apply jobs ready to apply`;
    }
  } catch (err) {
    console.warn('Could not update Indeed KPI stats:', err);
  }
}

function applyIndeedFilters() {
  let list = [...indeedState.posts];

  // In-memory email filter if active
  if (indeedState.emailOnlyFilter) {
    list = list.filter((p) => Array.isArray(p.contact_emails) && p.contact_emails.length > 0);
  }

  // In-memory keyword filter if present
  if (indeedState.searchKeyword) {
    const kw = indeedState.searchKeyword.toLowerCase().trim();
    list = list.filter((p) => {
      const title = (p.author_headline || '').toLowerCase();
      const comp = (p.author_name || '').toLowerCase();
      const loc = (p.location || '').toLowerCase();
      const emails = (p.contact_emails || []).join(' ').toLowerCase();
      return title.includes(kw) || comp.includes(kw) || loc.includes(kw) || emails.includes(kw);
    });
  }

  // Sort by email if active
  if (indeedState.sortByEmail) {
    list.sort((a, b) => {
      const aHas = a.contact_emails && a.contact_emails.length > 0 ? 1 : 0;
      const bHas = b.contact_emails && b.contact_emails.length > 0 ? 1 : 0;
      return bHas - aHas;
    });
  }

  indeedState.filteredPosts = list;
  indeedState.page = 1;
  renderIndeedPostsTable();
  updateIndeedBatchToolbar();
}

function renderIndeedPagination(total) {
  const isAll = indeedState.limit === -1;
  const totalPages = isAll ? 1 : (Math.ceil(total / indeedState.limit) || 1);
  const startRow = total === 0 ? 0 : (isAll ? 1 : (indeedState.page - 1) * indeedState.limit + 1);
  const endRow = isAll ? total : Math.min(indeedState.page * indeedState.limit, total);
  const textInfo = `Showing ${startRow}–${endRow} of ${total} jobs`;

  const infoEl = document.getElementById('indeedPaginationInfo');
  if (infoEl) infoEl.textContent = textInfo;
  const infoTopEl = document.getElementById('indeedPaginationInfoTop');
  if (infoTopEl) infoTopEl.textContent = textInfo;

  // Sync rows per page selects
  const selLimit = document.getElementById('selectIndeedLimit');
  if (selLimit) selLimit.value = String(indeedState.limit);
  const selLimitTop = document.getElementById('selectIndeedLimitTop');
  if (selLimitTop) selLimitTop.value = String(indeedState.limit);

  const containers = [
    document.getElementById('indeedPageButtons'),
    document.getElementById('indeedPageButtonsTop')
  ].filter(Boolean);

  containers.forEach(container => {
    container.innerHTML = '';
    if (isAll || totalPages <= 1) return;

    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.textContent = '‹';
    prevBtn.disabled = indeedState.page <= 1;
    prevBtn.onclick = () => goToIndeedPage(indeedState.page - 1);
    container.appendChild(prevBtn);

    const startPage = Math.max(1, indeedState.page - 2);
    const endPage = Math.min(totalPages, indeedState.page + 2);

    for (let p = startPage; p <= endPage; p++) {
      const pBtn = document.createElement('button');
      pBtn.className = `page-btn ${p === indeedState.page ? 'active' : ''}`;
      pBtn.textContent = String(p);
      pBtn.onclick = () => goToIndeedPage(p);
      container.appendChild(pBtn);
    }

    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.textContent = '›';
    nextBtn.disabled = indeedState.page >= totalPages;
    nextBtn.onclick = () => goToIndeedPage(indeedState.page + 1);
    container.appendChild(nextBtn);
  });
}

function goToIndeedPage(p) {
  indeedState.page = p;
  renderIndeedPostsTable();
}

function changeIndeedRowsPerPage(val) {
  indeedState.limit = parseInt(val, 10);
  indeedState.page = 1;
  const sel = document.getElementById('selectIndeedLimit');
  if (sel) sel.value = String(indeedState.limit);
  const selTop = document.getElementById('selectIndeedLimitTop');
  if (selTop) selTop.value = String(indeedState.limit);
  renderIndeedPostsTable();
}

function renderIndeedPostsTable() {
  const tbody = document.getElementById('indeedApplyTableBody');
  if (!tbody) return;

  const posts = indeedState.filteredPosts;
  renderIndeedPagination(posts ? posts.length : 0);

  if (!posts || posts.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 3.5rem 1rem; color: #64748b;">
          <div style="font-size: 1.8rem; margin-bottom: 0.5rem;">🎯</div>
          <strong style="color: #cbd5e1; font-size: 0.95rem;">No Indeed Apply jobs match your active filters</strong>
          <p style="font-size: 0.8rem; margin: 0.35rem 0 1rem 0; color: #94a3b8;">
            Launch an Indeed discovery crawl using the form above to find new Easy Apply opportunities.
          </p>
          <button class="btn btn-primary btn-sm btn-indeed-crawl" onclick="triggerIndeedApplyCrawl()">
            <span>Collect Indeed Jobs</span>
          </button>
        </td>
      </tr>
    `;
    return;
  }

  const isAll = indeedState.limit === -1;
  const pageItems = isAll ? posts : posts.slice((indeedState.page - 1) * indeedState.limit, indeedState.page * indeedState.limit);

  const rowsHtml = pageItems.map((post) => {
    const isSelected = indeedState.selectedIds.has(post.id);
    const title = post.author_headline || 'Software Engineer';
    const company = post.author_name || 'Company';
    const loc = post.location || 'India';
    const hasEmails = post.contact_emails && post.contact_emails.length > 0;
    const primaryEmail = hasEmails ? post.contact_emails[0] : '';
    const isRemote = (loc || '').toLowerCase().includes('remote');

    const dateText = typeof formatPostDateTimeWithRelative === 'function'
      ? formatPostDateTimeWithRelative(post)
      : (typeof formatDateTime === 'function' ? formatDateTime(post.created_at) : (post.created_at || '—'));

    // Status Badge & Dropdown logic
    let statusBadgeText = '⚡ Ready';
    let statusBadgeClass = 'discovered';
    const st = (post.status || 'DISCOVERED').toUpperCase();

    if (st === 'APPLIED') {
      statusBadgeText = '✓ Applied';
      statusBadgeClass = 'applied';
    } else if (st === 'REQUIRES_QUESTIONNAIRE') {
      statusBadgeText = '📋 Screening';
      statusBadgeClass = 'questionnaire';
    } else if (st === 'NOT_FOUND') {
      statusBadgeText = '🚫 Not Found';
      statusBadgeClass = 'not-found';
    } else if (st === 'REJECTED') {
      if (post.rejection_reason && post.rejection_reason.toLowerCase().includes('already applied')) {
        statusBadgeText = '✓ Already Applied';
        statusBadgeClass = 'rejected';
      } else {
        statusBadgeText = '✕ Dismissed';
        statusBadgeClass = 'rejected';
      }
    }

    const statusTitle = post.rejection_reason
      ? `${st}: ${post.rejection_reason} (Click to change)`
      : 'Click to change status';

    const statusDropdown = `
      <div class="easy-status-wrap" id="status-wrap-indeed-${post.id}">
        <span class="tag-easy-status ${statusBadgeClass} tag-easy-status-btn" onclick="toggleIndeedStatusMenu('${post.id}', event)" title="${escapeHtml(statusTitle)}">
          <span>${statusBadgeText}</span>
          <span class="status-caret">▾</span>
        </span>
        <div class="easy-status-menu" id="status-menu-indeed-${post.id}">
          <button class="status-menu-opt opt-ready" onclick="setIndeedPostStatus('${post.id}', 'DISCOVERED', event)">
            <span>⚡</span><span>Ready (Queue)</span>
          </button>
          <button class="status-menu-opt opt-screening" onclick="setIndeedPostStatus('${post.id}', 'REQUIRES_QUESTIONNAIRE', event)">
            <span>📋</span><span>Screening</span>
          </button>
          <button class="status-menu-opt opt-applied" onclick="setIndeedPostStatus('${post.id}', 'APPLIED', event)">
            <span>✓</span><span>Mark Applied</span>
          </button>
          <button class="status-menu-opt opt-not-found" onclick="setIndeedPostStatus('${post.id}', 'NOT_FOUND', event)">
            <span>🚫</span><span>Not Found / Closed</span>
          </button>
          <button class="status-menu-opt opt-rejected" onclick="setIndeedPostStatus('${post.id}', 'REJECTED', event, false)">
            <span>✕</span><span>Dismiss Job Only</span>
          </button>
          <button class="status-menu-opt opt-rejected" style="color: #f43f5e;" onclick="setIndeedPostStatus('${post.id}', 'REJECTED', event, true)">
            <span>🚫</span><span>Dismiss & Add Role</span>
          </button>
        </div>
      </div>
    `;

    // Experience Tag
    let expBadge = '<span class="pill-badge badge-exp" style="font-size: 0.7rem;">Not specified</span>';
    if (post.is_fresher) {
      expBadge = '<span class="pill-badge badge-exp" style="font-size: 0.7rem; color: #34d399; border-color: rgba(16, 185, 129, 0.35);">Fresher (0y)</span>';
    } else if (post.raw_experience) {
      expBadge = `<span class="pill-badge badge-exp" style="font-size: 0.7rem;">${escapeHtml(post.raw_experience)}</span>`;
    } else if (post.min_experience !== null && post.min_experience !== undefined) {
      const min = post.min_experience;
      const max = post.max_experience;
      const label = max ? `${min}–${max}y exp` : `${min}+ yrs exp`;
      expBadge = `<span class="pill-badge badge-exp" style="font-size: 0.7rem;">${escapeHtml(label)}</span>`;
    }

    // Recruiter email pill (in-stream harvested indicator)
    const emailPillHtml = hasEmails
      ? `
        <div class="recruiter-email-chip" onclick="jumpToReviewForEmail('${post.id}')" title="Recruiter email harvested from JD! Click to view in Review & Drafts">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
          <span>${escapeHtml(primaryEmail)}</span>
        </div>
      `
      : '';

    // Closed / Not Found / Questionnaire reason
    const reasonPillHtml = (st === 'NOT_FOUND' && post.rejection_reason)
      ? `<span class="col-closed-reason" style="color: #94a3b8; font-size: 0.68rem; background: rgba(148, 163, 184, 0.12); padding: 0.05rem 0.35rem; border-radius: 4px; border: 1px solid rgba(148, 163, 184, 0.22); line-height: 1.3;" title="${escapeHtml(post.rejection_reason)}">🚫 ${escapeHtml(post.rejection_reason)}</span>`
      : (st === 'REQUIRES_QUESTIONNAIRE' && post.rejection_reason
        ? `<span class="col-closed-reason" style="color: #fbbf24; font-size: 0.68rem; background: rgba(245, 158, 11, 0.12); padding: 0.05rem 0.35rem; border-radius: 4px; border: 1px solid rgba(245, 158, 11, 0.25); line-height: 1.3; cursor: pointer;" onclick="openScreeningModal('${post.id}')" title="${escapeHtml(post.rejection_reason)}">📋 Questions required</span>`
        : '');

    // Primary action button
    let primaryAction = `<button class="btn btn-primary btn-xs" onclick="applySingleIndeedJob('${post.id}')" title="Apply to this job now via Indeed"><span>⚡ Apply</span></button>`;
    if (st === 'APPLIED') {
      primaryAction = `<span class="tag-easy-status applied" style="opacity: 0.9; font-size: 0.68rem; cursor: default;">✓ Submitted</span>`;
    } else if (st === 'REQUIRES_QUESTIONNAIRE') {
      primaryAction = `
        <button class="btn btn-primary btn-xs" onclick="applySingleIndeedJob('${post.id}')" title="Rerun Indeed Apply with Question Bank answers"><span>⚡ Rerun</span></button>
        <button class="btn btn-outline btn-xs" onclick="openScreeningModal('${post.id}')" title="View & answer screening questions" style="color: #fbbf24; border-color: rgba(245, 158, 11, 0.4);"><span>📋 Screen</span></button>
      `;
    } else if (st === 'NOT_FOUND') {
      primaryAction = `<span class="tag-easy-status not-found" style="opacity: 0.8; font-size: 0.68rem; cursor: default;" title="${post.rejection_reason ? escapeHtml(post.rejection_reason) : 'Position closed or not found'}">🚫 Closed</span>`;
    }

    return `
      <tr class="${isSelected ? 'row-selected' : ''}" id="indeedRow_${post.id}">
        <td class="col-check">
          <input type="checkbox" class="easy-checkbox" ${isSelected ? 'checked' : ''} onchange="toggleSelectIndeedJob('${post.id}', this.checked)" />
        </td>
        <td class="col-role">
          <div class="easy-role-cell">
            <a href="javascript:void(0)" onclick="openEasyDetailsModal('${post.id}')" class="easy-job-title-link" title="Click to view full job description & details">
              ${escapeHtml(title)}
            </a>
            <div style="display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; margin-top: 0.1rem;">
              <span class="easy-company-name">
                <span style="opacity: 0.7;">🏢</span>
                <span>${escapeHtml(company)}</span>
              </span>
              <span class="easy-location-chip" title="Location: ${escapeHtml(loc)}">
                <span style="opacity: 0.85;">📍</span>
                <span>${escapeHtml(loc)}</span>
              </span>
              ${post.is_dismissed || (post.rejection_reason && post.rejection_reason.toLowerCase().includes('dismissed')) ? `<span class="badge-dismissed" title="${escapeHtml(post.rejection_reason || 'Previously dismissed role')}">🚫 Dismissed</span>` : ''}
              ${post.rejection_reason && post.rejection_reason.toLowerCase().includes('already applied') ? `<span class="badge-already-applied" title="Already applied">✓ Already Applied</span>` : ''}
              ${emailPillHtml}
              ${reasonPillHtml}
            </div>
          </div>
        </td>
        <td class="col-location">
          <span class="easy-location-badge ${isRemote ? 'is-remote' : ''}" title="${escapeHtml(loc)}">
            <span style="opacity: 0.85; flex-shrink: 0;">📍</span>
            <span class="loc-label">${escapeHtml(loc)}</span>
          </span>
        </td>
        <td class="col-exp">
          ${expBadge}
        </td>
        <td class="col-status">
          ${statusDropdown}
        </td>
        <td class="col-date">
          <span class="easy-date-text" title="${escapeHtml(post.created_at || '')}">${escapeHtml(dateText)}</span>
        </td>
        <td class="col-actions">
          <div class="easy-actions-cell">
            ${primaryAction}
            ${
              hasEmails
                ? `
              <button class="btn btn-outline btn-xs btn-indeed-draft-email" onclick="handleIndeedEmailAction('${post.id}')" title="Generate AI Cover Letter & Send Email (via Review & Drafts / Gmail)" style="color: #38bdf8; border-color: rgba(56, 189, 248, 0.4); font-size: 0.68rem; padding: 0.12rem 0.42rem; white-space: nowrap;">
                <span>✉️ Email</span>
              </button>
            `
                : ''
            }
            <button class="icon-btn sm" onclick="openEasyDetailsModal('${post.id}')" title="View Full Job Description & Details">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            </button>
            <button class="icon-btn sm" onclick="copyIndeedJobLink('${post.id}')" title="Copy Indeed Job URL">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <a href="${escapeHtml(post.post_url)}" target="_blank" rel="noopener noreferrer" class="icon-btn sm" title="Open Job Listing on Indeed">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
            ${
              st !== 'REJECTED'
                ? `
              <button class="icon-btn sm btn-danger-soft" onclick="dismissSingleIndeedJob('${post.id}')" title="Dismiss this job (auto-syncs to LinkedIn rejections)">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            `
                : `
              <button class="icon-btn sm" onclick="revertSingleIndeedJob('${post.id}')" title="Restore to Ready">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
              </button>
            `
            }
          </div>
        </td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rowsHtml;
}

function filterIndeedApplyStatus(status) {
  indeedState.statusFilter = status;
  indeedState.emailOnlyFilter = false;

  const pillEmail = document.getElementById('pillIndeedHasEmail');
  if (pillEmail) pillEmail.classList.remove('active');

  // Update status pills active states
  const pillIds = {
    ALL: 'pillIndeedAll',
    DISCOVERED: 'pillIndeedDiscovered',
    REQUIRES_QUESTIONNAIRE: 'pillIndeedQuestionnaire',
    APPLIED: 'pillIndeedApplied',
    NOT_FOUND: 'pillIndeedNotFound',
    REJECTED: 'pillIndeedDismissed',
  };

  Object.entries(pillIds).forEach(([stKey, elId]) => {
    const el = document.getElementById(elId);
    if (el) el.classList.toggle('active', stKey === status);
  });

  // Also toggle active KPI card
  const kpiIds = {
    ALL: 'kpiIndeedTotal',
    APPLIED: 'kpiIndeedApplied',
    REQUIRES_QUESTIONNAIRE: 'kpiIndeedQuestionnaire',
    DISCOVERED: 'kpiIndeedReady',
    NOT_FOUND: 'kpiIndeedNotFound',
  };
  Object.entries(kpiIds).forEach(([stKey, elId]) => {
    const el = document.getElementById(elId);
    if (el) el.classList.toggle('active', stKey === status);
  });

  fetchIndeedApplyPosts();
}

function filterIndeedApplyEmailOnly(toggle) {
  if (typeof toggle === 'boolean') {
    indeedState.emailOnlyFilter = toggle;
  } else {
    indeedState.emailOnlyFilter = !indeedState.emailOnlyFilter;
  }

  const pill = document.getElementById('pillIndeedHasEmail');
  if (pill) {
    pill.classList.toggle('active', indeedState.emailOnlyFilter);
  }

  if (indeedState.emailOnlyFilter) {
    indeedState.statusFilter = 'ALL';
    // Remove active state from other status pills
    const statusPillIds = [
      'pillIndeedAll',
      'pillIndeedDiscovered',
      'pillIndeedQuestionnaire',
      'pillIndeedApplied',
      'pillIndeedNotFound',
      'pillIndeedDismissed',
    ];
    statusPillIds.forEach((pid) => {
      const el = document.getElementById(pid);
      if (el) el.classList.remove('active');
    });
  }

  const clearBtn = document.getElementById('btnClearIndeedFilters');
  if (clearBtn && indeedState.emailOnlyFilter) {
    clearBtn.classList.remove('hidden');
  }

  fetchIndeedApplyPosts();
}

function toggleIndeedSortByEmail() {
  indeedState.sortByEmail = !indeedState.sortByEmail;
  const btn = document.getElementById('btnSortIndeedByEmail');
  const lbl = document.getElementById('lblSortIndeedEmail');
  if (btn) {
    if (indeedState.sortByEmail) {
      btn.style.background = 'rgba(56, 189, 248, 0.15)';
      btn.style.borderColor = '#38bdf8';
      btn.style.color = '#38bdf8';
      if (lbl) lbl.textContent = '✓ Sorted: Emails First';
    } else {
      btn.style.background = 'var(--bg-card)';
      btn.style.borderColor = 'var(--border-color)';
      btn.style.color = 'var(--text-secondary)';
      if (lbl) lbl.textContent = 'Sort: Emails First';
    }
  }

  const clearBtn = document.getElementById('btnClearIndeedFilters');
  if (clearBtn && indeedState.sortByEmail) {
    clearBtn.classList.remove('hidden');
  }

  applyIndeedFilters();
}

function handleIndeedTableSearch(query) {
  indeedState.searchKeyword = query || '';
  const clearBtn = document.getElementById('btnClearIndeedFilters');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', !indeedState.searchKeyword && !indeedState.dateFrom && !indeedState.dateTo);
  }
  applyIndeedFilters();
}

function applyIndeedDateFilter() {
  const fromEl = document.getElementById('indeedDateFrom');
  const toEl = document.getElementById('indeedDateTo');
  indeedState.dateFrom = fromEl ? fromEl.value : '';
  indeedState.dateTo = toEl ? toEl.value : '';

  const clearBtn = document.getElementById('btnClearIndeedFilters');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', !indeedState.searchKeyword && !indeedState.dateFrom && !indeedState.dateTo);
  }
  fetchIndeedApplyPosts();
}

function clearIndeedApplyFilters() {
  indeedState.searchKeyword = '';
  indeedState.dateFrom = '';
  indeedState.dateTo = '';
  indeedState.statusFilter = 'ALL';
  indeedState.emailOnlyFilter = false;
  indeedState.sortByEmail = false;

  const pillEmail = document.getElementById('pillIndeedHasEmail');
  if (pillEmail) pillEmail.classList.remove('active');

  const btnSort = document.getElementById('btnSortIndeedByEmail');
  if (btnSort) {
    btnSort.style.background = 'var(--bg-card)';
    btnSort.style.borderColor = 'var(--border-color)';
    btnSort.style.color = 'var(--text-secondary)';
  }
  const lblSort = document.getElementById('lblSortIndeedEmail');
  if (lblSort) lblSort.textContent = 'Sort: Emails First';

  const kwInput = document.getElementById('indeedFilterKeyword');
  if (kwInput) kwInput.value = '';
  const fromEl = document.getElementById('indeedDateFrom');
  if (fromEl) fromEl.value = '';
  const toEl = document.getElementById('indeedDateTo');
  if (toEl) toEl.value = '';
  const clearBtn = document.getElementById('btnClearIndeedFilters');
  if (clearBtn) clearBtn.classList.add('hidden');

  filterIndeedApplyStatus('ALL');
}

function toggleSelectAllIndeedJobs(checked) {
  if (checked) {
    indeedState.filteredPosts.forEach((p) => indeedState.selectedIds.add(p.id));
  } else {
    indeedState.selectedIds.clear();
  }
  renderIndeedPostsTable();
  updateIndeedBatchToolbar();
}

function toggleSelectIndeedJob(id, checked) {
  if (checked) {
    indeedState.selectedIds.add(id);
  } else {
    indeedState.selectedIds.delete(id);
  }

  // Update individual row selected class
  const row = document.getElementById(`indeedRow_${id}`);
  if (row) row.classList.toggle('row-selected', checked);

  // Update header checkbox
  const selectAll = document.getElementById('selectAllIndeedCheck');
  if (selectAll && indeedState.filteredPosts.length > 0) {
    selectAll.checked = indeedState.filteredPosts.every((p) => indeedState.selectedIds.has(p.id));
  }

  updateIndeedBatchToolbar();
}

function updateIndeedBatchToolbar() {
  const toolbar = document.getElementById('indeedBatchToolbar');
  const countEl = document.getElementById('indeedSelectedCount');
  if (!toolbar || !countEl) return;

  const count = indeedState.selectedIds.size;
  if (count > 0) {
    countEl.textContent = `${count} selected`;
    toolbar.classList.remove('hidden');
  } else {
    toolbar.classList.add('hidden');
  }
}

function clearIndeedSelection() {
  indeedState.selectedIds.clear();
  const selectAll = document.getElementById('selectAllIndeedCheck');
  if (selectAll) selectAll.checked = false;
  renderIndeedPostsTable();
  updateIndeedBatchToolbar();
}

// Smart Fixed-Position Status Dropdown
function toggleIndeedStatusMenu(postId, event) {
  if (event) event.stopPropagation();
  const wrap = document.getElementById(`status-wrap-indeed-${postId}`);
  const menu = document.getElementById(`status-menu-indeed-${postId}`);
  if (!wrap || !menu) return;

  const isVisible = menu.classList.contains('menu-visible');
  closeAllIndeedStatusMenus();
  if (isVisible) return;

  const btn = wrap.querySelector('.tag-easy-status-btn');
  if (!btn) return;
  const rect = btn.getBoundingClientRect();
  const menuHeight = 170;
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;

  menu.style.left = `${rect.left}px`;
  if (spaceBelow < menuHeight && spaceAbove > menuHeight) {
    menu.style.top = `${rect.top - menuHeight - 4}px`;
  } else {
    menu.style.top = `${rect.bottom + 4}px`;
  }

  menu.classList.add('menu-visible');
  wrap.classList.add('open');
}

function closeAllIndeedStatusMenus() {
  document.querySelectorAll('.easy-status-menu.menu-visible').forEach((el) => {
    el.classList.remove('menu-visible');
  });
  document.querySelectorAll('.easy-status-wrap.open').forEach((el) => {
    el.classList.remove('open');
  });
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.easy-status-wrap')) {
    closeAllIndeedStatusMenus();
  }
});
window.addEventListener('scroll', closeAllIndeedStatusMenus, true);
window.addEventListener('resize', closeAllIndeedStatusMenus);

async function setIndeedPostStatus(postId, newStatus, event, addToDismissed = false) {
  if (event) event.stopPropagation();
  closeAllIndeedStatusMenus();

  try {
    const res = await fetch(`/api/posts/${postId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, add_to_dismissed_roles: !!addToDismissed }),
    });

    if (res.ok) {
      const p = indeedState.posts.find((x) => x.id === postId);
      if (p) p.status = newStatus;
      const fp = indeedState.filteredPosts.find((x) => x.id === postId);
      if (fp) fp.status = newStatus;

      renderIndeedPostsTable();
      updateIndeedKpiRibbon();

      if (addToDismissed && typeof loadDismissedRolesPage === 'function' && state.activeTab === 'tabDismissedRoles') {
        loadDismissedRolesPage();
      }

      if (typeof showSnackbar === 'function') {
        const blacklistMsg = addToDismissed ? ' (Role added to Dismissed Roles)' : '';
        showSnackbar({
          title: 'Status Updated',
          message: `Job updated to ${newStatus}${blacklistMsg}.`,
          type: 'success',
        });
      }
    } else {
      const err = await res.json();
      alert(`Could not update status: ${err.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Failed to update Indeed post status:', err);
  }
}

function copyIndeedJobLink(postId) {
  const post = indeedState.posts.find((p) => p.id === postId) || indeedState.filteredPosts.find((p) => p.id === postId);
  if (!post || !post.post_url) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({ title: 'Copy Failed', message: 'No URL available for this post', type: 'error' });
    }
    return;
  }
  navigator.clipboard.writeText(post.post_url).then(() => {
    if (typeof showSnackbar === 'function') {
      showSnackbar({ title: 'Link Copied', message: 'Indeed job URL copied to clipboard', type: 'success' });
    }
  }).catch(() => {
    prompt('Copy link:', post.post_url);
  });
}

async function batchSetIndeedStatus(newStatus, addToDismissed = false) {
  const ids = Array.from(indeedState.selectedIds);
  if (!ids.length) return;

  if (newStatus === 'REJECTED' && !addToDismissed) {
    return batchDismissIndeedJobs();
  }

  try {
    const res = await fetch('/api/posts/status-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids, status: newStatus, add_to_dismissed_roles: !!addToDismissed }),
    });

    if (res.ok) {
      if (addToDismissed && typeof loadDismissedRolesPage === 'function' && state.activeTab === 'tabDismissedRoles') {
        loadDismissedRolesPage();
      }
      if (typeof showSnackbar === 'function') {
        const blacklistMsg = addToDismissed ? ' (Roles added to Dismissed Roles)' : '';
        showSnackbar({
          title: 'Status Updated',
          message: `Updated ${ids.length} jobs to ${newStatus}${blacklistMsg}.`,
          type: 'success',
        });
      }
      clearIndeedSelection();
      fetchIndeedApplyPosts();
    } else {
      const err = await res.json();
      alert(`Error updating status: ${err.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Batch status update failed:', err);
  }
}

async function batchApplySelectedIndeedJobs() {
  const ids = Array.from(indeedState.selectedIds);
  if (!ids.length) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'No Jobs Selected',
        message: 'Please select one or more jobs using the row checkboxes before clicking Apply Selected.',
        type: 'warning',
      });
    } else {
      alert('Please select one or more jobs using the row checkboxes before clicking Apply Selected.');
    }
    return;
  }

  const pacingEl = document.getElementById('selectIndeedPacing');
  const pacing = pacingEl ? pacingEl.value : 'safe';

  try {
    const res = await fetch('/api/indeed-apply/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        post_ids: ids,
        pacing: pacing,
      }),
    });

    const data = await res.json();
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Batch Indeed Apply Queued',
          message: data.message || `Queued ${ids.length} applications in FIFO queue.`,
          type: 'success',
        });
      }
      clearIndeedSelection();
      if (typeof toggleTaskDrawer === 'function') {
        toggleTaskDrawer(true);
      }
      fetchIndeedApplyPosts();
    } else {
      alert(`Error starting batch apply: ${data.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Error queuing batch Indeed apply:', err);
  }
}

function batchCopyIndeedLinks() {
  const ids = Array.from(indeedState.selectedIds);
  if (!ids.length) return;

  const links = indeedState.filteredPosts
    .filter((p) => indeedState.selectedIds.has(p.id))
    .map((p) => p.post_url)
    .filter(Boolean);

  if (links.length) {
    navigator.clipboard.writeText(links.join('\n'));
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Links Copied',
        message: `Copied ${links.length} Indeed job URLs to clipboard.`,
        type: 'success',
      });
    }
  }
}

function batchDismissIndeedJobs() {
  const ids = Array.from(indeedState.selectedIds);
  if (!ids.length) return;
  state.pendingCancelPostId = null;
  state.pendingCancelPostIds = ids;
  state.pendingCancelSource = 'indeed_apply';
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(null, `${ids.length} selected Indeed jobs`, 'Dismissed from Indeed', false, 'indeed_apply');
  }
}

async function applySingleIndeedJob(postId) {
  try {
    const res = await fetch(`/api/indeed-apply/${postId}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Indeed Apply Started',
          message: data.message || 'Application job queued in Firefox.',
          type: 'info',
        });
      }
      if (typeof toggleTaskDrawer === 'function') {
        toggleTaskDrawer(true);
      }
    } else {
      alert(`Cannot apply: ${data.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Error applying to single Indeed job:', err);
  }
}

function dismissSingleIndeedJob(postId) {
  const post = (indeedState.posts || []).find((x) => x.id === postId)
            || (indeedState.filteredPosts || []).find((x) => x.id === postId);
  const title = post ? (post.author_headline || post.author_name || 'Job') : 'Job';
  state.pendingCancelPostId = postId;
  state.pendingCancelPostIds = [];
  state.pendingCancelSource = 'indeed_apply';
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(postId, title, 'Dismissed from Indeed', false, 'indeed_apply');
  }
}

async function revertSingleIndeedJob(postId) {
  try {
    const res = await fetch(`/api/posts/${postId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'DISCOVERED' }),
    });
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Job Restored',
          message: 'Restored job to Ready in Queue.',
          type: 'success',
        });
      }
      fetchIndeedApplyPosts();
    }
  } catch (err) {
    console.error('Error reverting post:', err);
  }
}

async function triggerIndeedApplyCrawl() {
  const query = (document.getElementById('indeedSearchQuery')?.value || '').trim();
  const location = (document.getElementById('indeedSearchLocation')?.value || '').trim();
  const timeFilter = document.getElementById('indeedTimeFilter')?.value || '24h';
  const pacing = document.getElementById('selectIndeedPacing')?.value || 'safe';
  const cycles = parseInt(document.getElementById('indeedCrawlerCycles')?.value || '8', 10);
  const maxJobs = parseInt(document.getElementById('indeedMaxJobs')?.value || '50', 10);

  try {
    const res = await fetch('/api/scrape/indeed-apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        search_query: query,
        location: location,
        time_filter: timeFilter,
        pacing: pacing,
        cycles: cycles,
        max_jobs: maxJobs,
      }),
    });

    const data = await res.json();
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Indeed Collector Queued',
          message: data.message || 'Indeed job collector dispatched in visible Firefox.',
          type: 'success',
        });
      }
      if (typeof toggleTaskDrawer === 'function') {
        toggleTaskDrawer(true);
      }
    } else {
      alert(`Failed to launch Indeed crawler: ${data.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Error launching Indeed crawl:', err);
  }
}

async function triggerRerunScreenedIndeedApply() {
  try {
    const res = await fetch('/api/indeed-apply/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ all_screened: true }),
    });
    const data = await res.json();
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Rerun Queued',
          message: data.message || 'Re-running screened Indeed applications.',
          type: 'success',
        });
      }
      if (typeof toggleTaskDrawer === 'function') {
        toggleTaskDrawer(true);
      }
    } else {
      alert(`Cannot rerun screened applications: ${data.detail || 'None found'}`);
    }
  } catch (err) {
    console.error('Error rerunning screened applications:', err);
  }
}

function openIndeedBulkSearchModal() {
  if (typeof openBulkSearchModal === 'function') {
    openBulkSearchModal('indeed');
  } else {
    alert('Bulk Search modal available in Easy Apply.');
  }
}

async function handleIndeedEmailAction(postId) {
  const post = indeedState.posts.find((p) => p.id === postId) || (indeedState.filteredPosts && indeedState.filteredPosts.find((p) => p.id === postId));
  if (!post) return;

  const emails = post.contact_emails || [];
  if (emails.length === 0) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({ title: 'No Email Found', message: 'No recruiter email has been extracted for this position.', type: 'warning' });
    }
    return;
  }

  // If email already generated, jump directly to Review & Drafts
  if (post.status === 'EMAIL_GENERATED' || post.generated_body) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({ title: 'Opening Review Draft', message: `Opening draft for ${post.author_name || 'recruiter'}...`, type: 'info' });
    }
    switchTab('tabReview');
    if (typeof selectReviewPostById === 'function') {
      selectReviewPostById(postId);
    }
    return;
  }

  // Otherwise, enqueue ChatGPT generation
  if (typeof showSnackbar === 'function') {
    showSnackbar({ title: 'Generating Cover Letter', message: `Queueing AI draft for ${post.author_name || 'recruiter'}...`, type: 'info' });
  }

  try {
    const res = await fetch(`/api/generate-email/${postId}?force=true`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({ title: 'Draft Queued', message: data.message || 'Email generation queued! Opening Review workspace...', type: 'success' });
      }
      switchTab('tabReview');
      if (typeof selectReviewPostById === 'function') {
        selectReviewPostById(postId);
      }
    } else {
      alert(`Cannot generate email draft: ${data.detail || 'Request failed'}`);
    }
  } catch (err) {
    console.error('Error initiating email draft:', err);
    alert(`Error: ${err.message}`);
  }
}

function jumpToReviewForEmail(postId) {
  handleIndeedEmailAction(postId);
}

function initIndeedApplyWorkspace() {
  // Restore saved cycles/max-jobs preferences if present
  try {
    const savedCycles = localStorage.getItem('reach_indeed_cycles');
    if (savedCycles && document.getElementById('indeedCrawlerCycles')) {
      document.getElementById('indeedCrawlerCycles').value = savedCycles;
    }
    const savedMax = localStorage.getItem('reach_indeed_max_jobs');
    if (savedMax && document.getElementById('indeedMaxJobs')) {
      document.getElementById('indeedMaxJobs').value = savedMax;
    }

    // Auto-save on change
    const cyclesInput = document.getElementById('indeedCrawlerCycles');
    if (cyclesInput) {
      cyclesInput.addEventListener('change', () => {
        localStorage.setItem('reach_indeed_cycles', cyclesInput.value);
      });
    }
    const maxInput = document.getElementById('indeedMaxJobs');
    if (maxInput) {
      maxInput.addEventListener('change', () => {
        localStorage.setItem('reach_indeed_max_jobs', maxInput.value);
      });
    }
  } catch (_) {}
}

// Bind globally to window
window.fetchIndeedApplyPosts = fetchIndeedApplyPosts;
window.filterIndeedApplyStatus = filterIndeedApplyStatus;
window.filterIndeedApplyEmailOnly = filterIndeedApplyEmailOnly;
window.toggleIndeedSortByEmail = toggleIndeedSortByEmail;
window.handleIndeedEmailAction = handleIndeedEmailAction;
window.handleIndeedTableSearch = handleIndeedTableSearch;
window.applyIndeedDateFilter = applyIndeedDateFilter;
window.clearIndeedApplyFilters = clearIndeedApplyFilters;
window.toggleSelectAllIndeedJobs = toggleSelectAllIndeedJobs;
window.toggleSelectIndeedJob = toggleSelectIndeedJob;
window.clearIndeedSelection = clearIndeedSelection;
window.batchSetIndeedStatus = batchSetIndeedStatus;
window.batchApplySelectedIndeedJobs = batchApplySelectedIndeedJobs;
window.batchCopyIndeedLinks = batchCopyIndeedLinks;
window.batchDismissIndeedJobs = batchDismissIndeedJobs;
window.applySingleIndeedJob = applySingleIndeedJob;
window.dismissSingleIndeedJob = dismissSingleIndeedJob;
window.revertSingleIndeedJob = revertSingleIndeedJob;
window.triggerIndeedApplyCrawl = triggerIndeedApplyCrawl;
window.triggerRerunScreenedIndeedApply = triggerRerunScreenedIndeedApply;
window.openIndeedBulkSearchModal = openIndeedBulkSearchModal;
window.jumpToReviewForEmail = jumpToReviewForEmail;
window.toggleIndeedStatusMenu = toggleIndeedStatusMenu;
window.setIndeedPostStatus = setIndeedPostStatus;
window.copyIndeedJobLink = copyIndeedJobLink;
window.changeIndeedRowsPerPage = changeIndeedRowsPerPage;
window.goToIndeedPage = goToIndeedPage;
window.initIndeedApplyWorkspace = initIndeedApplyWorkspace;
