/**
 * Reach — Discovered Posts Table, Filtering, Pagination & Selection
 * (src/static/js/discovered.js)
 */

async function fetchDiscoveredPosts() {
  if (!state.posts || state.posts.length === 0) {
    renderSkeletonRows();
  }

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

    if (state.sortBy && state.sortBy !== 'default') {
      params.append('order_by', state.sortBy);
    }

    if (state.dateFilter && state.dateFilter !== 'ALL') {
      params.append('date_filter', state.dateFilter);
    }

    if (state.fromDiscoveredDate) {
      params.append('from_date', state.fromDiscoveredDate);
    }

    if (state.toDiscoveredDate) {
      params.append('to_date', state.toDiscoveredDate);
    }

    if (state.locationFilter && state.locationFilter !== 'ALL') {
      params.append('location', state.locationFilter);
    }

    if (state.discoveredReason && state.discoveredReason !== 'ALL') {
      params.append('reason', state.discoveredReason);
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

    const discBadge = document.getElementById('discoveredResultsBadge');
    const isFiltered = state.expFilter !== 'ALL' || (state.searchQuery && state.searchQuery.trim() !== '') || state.sourceFilter !== 'ALL' || (state.genStatusFilter && state.genStatusFilter !== 'ALL') || state.categoryFilter !== 'ALL' || (state.dateFilter && state.dateFilter !== 'ALL') || (state.sortBy && state.sortBy !== 'default') || (state.locationFilter && state.locationFilter !== 'ALL') || (state.discoveredReason && state.discoveredReason !== 'ALL') || Boolean(state.fromDiscoveredDate) || Boolean(state.toDiscoveredDate);
    if (discBadge) {
      if (isFiltered) {
        discBadge.textContent = `${state.total} result${state.total === 1 ? '' : 's'}`;
        discBadge.classList.remove('hidden');
      } else {
        discBadge.classList.add('hidden');
      }
    }

    const clearDiscBtn = document.getElementById('btnClearDiscoveredFilters');
    if (clearDiscBtn) {
      clearDiscBtn.classList.toggle('hidden', !isFiltered);
    }

    renderPostsTable();
    renderPagination();
    updateActiveFilterChips();
  } catch (err) {
    const tbody = document.getElementById('postsTableBody');
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem;">Error loading posts: ${escapeHtml(err.message)}</td></tr>`;
    }
  }
}

function renderSkeletonRows() {
  const tbody = document.getElementById('postsTableBody');
  if (!tbody) return;
  let rowsHtml = '';
  for (let i = 0; i < 6; i++) {
    rowsHtml += `
      <tr class="skeleton-row">
        <td><div class="skeleton-bar" style="width: 18px;"></div></td>
        <td><div class="skeleton-bar" style="width: 140px;"></div></td>
        <td><div class="skeleton-bar" style="width: 75px;"></div></td>
        <td><div class="skeleton-bar" style="width: 65px;"></div></td>
        <td><div class="skeleton-bar" style="width: 110px;"></div></td>
        <td><div class="skeleton-bar" style="width: 100px;"></div></td>
        <td style="text-align: right;"><div class="skeleton-bar" style="width: 70px; margin-left: auto;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = rowsHtml;
}

function getSourceBadgeHtml(postOrUrl, isPotentialSpam = false, potentialSpamReason = '', rejectionReason = '', status = '') {
  let url = '';
  let potentialSpam = isPotentialSpam;
  let potentialReason = potentialSpamReason;
  let rejReason = rejectionReason;
  let postStatus = status;

  if (typeof postOrUrl === 'object' && postOrUrl !== null) {
    url = postOrUrl.post_url || '';
    potentialSpam = !!postOrUrl.is_potential_spam;
    potentialReason = postOrUrl.potential_spam_reason || '';
    rejReason = postOrUrl.rejection_reason || '';
    postStatus = postOrUrl.status || '';
  } else {
    url = postOrUrl || '';
  }

  let badge = '';
  if (url.startsWith('direct://') || url.includes('direct')) {
    badge = `<span class="source-pill source-direct" title="Source: Direct Opportunity Outreach">Direct Outreach</span>`;
  } else if (url.includes('infopark.in')) {
    badge = `<span class="source-pill source-infopark" title="Source: Infopark Kochi Portal">Infopark Kochi</span>`;
  } else if (url.startsWith('manual://') || url.includes('manual')) {
    badge = `<span class="source-pill source-manual" title="Source: Manually Added">Manual</span>`;
  } else {
    badge = `<span class="source-pill source-linkedin" title="Source: LinkedIn Job Post">LinkedIn</span>`;
  }

  const isScam = rejReason && (rejReason.toLowerCase().includes('scam') || rejReason.toLowerCase().includes('spam'));
  const isPotential = potentialSpam || (rejReason && rejReason.toLowerCase().includes('potential'));
  const isDismissed = (typeof postOrUrl === 'object' && postOrUrl && (postOrUrl.is_dismissed || (rejReason && rejReason.toLowerCase().includes('dismissed'))));
  const isAlreadyApplied = (typeof postOrUrl === 'object' && postOrUrl && rejReason && rejReason.toLowerCase().includes('already applied'));

  if (isScam) {
    const why = rejReason || 'Flagged as scam recruiter';
    badge += `<span class="badge-scam-alert" title="Scam: ${escapeHtml(why)}">Scam</span>`;
  } else if (isPotential) {
    const why = potentialReason || rejReason || 'Suspicious contact domain or flagged recruiter activity';
    badge += `<span class="badge-spam-warning" title="Potential Scam: ${escapeHtml(why)}">Potential Scam</span>`;
  } else if (isDismissed) {
    const why = rejReason || 'Auto-dismissed: Matches previously dismissed role';
    badge += `<span class="badge-dismissed" title="${escapeHtml(why)}">🚫 Dismissed</span>`;
  } else if (isAlreadyApplied) {
    badge += `<span class="badge-already-applied" title="Already applied">✓ Already Applied</span>`;
  }

  return badge;
}

function renderPostsTable() {
  const tbody = document.getElementById('postsTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (state.posts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #64748b;">No matching jobs found. Try adjusting filters or scrape today's Infopark jobs.</td></tr>`;
    return;
  }

  state.posts.forEach((post) => {
    const tr = document.createElement('tr');
    tr.id = `row-${post.id}`;
    if (state.selectedIds.has(post.id)) tr.classList.add('selected');
    if (state.activeDiscoveredPostId === post.id) tr.classList.add('active-row');
    tr.setAttribute('onclick', `handleDiscoveredRowClick('${post.id}', event)`);

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

    const dateStr = formatPostDateTimeWithRelative(post);
    const dateHtml = `<span class="table-date-badge" title="${escapeHtml(post.posted_date_raw || post.created_at || '')}">${escapeHtml(dateStr || '—')}</span>`;

    const primaryEmail = (post.contact_emails && post.contact_emails[0]) || '';
    const emailHtml = primaryEmail
      ? `<span class="email-copy-pill" onclick="copyEmailToClipboard('${escapeHtml(primaryEmail)}')" title="Click to copy email">
           <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 3px;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>${escapeHtml(primaryEmail)}
         </span>`
      : `<span style="color: #64748b; font-size: 0.72rem;">—</span>`;

    const primaryPhone = (post.contact_phones && post.contact_phones[0]) || '';
    const phoneHtml = primaryPhone
      ? `<span class="phone-copy-pill" onclick="copyPhoneToClipboard('${escapeHtml(primaryPhone)}')" title="Click to copy contact number">
           <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 3px;"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>${escapeHtml(primaryPhone)}
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
            <span class="recruiter-name" title="${escapeHtml(post.author_name)}">${escapeHtml(post.author_name)}</span>
            ${getSourceBadgeHtml(post)}
            ${post.location ? `<span class="pill-badge badge-location" title="Location: ${escapeHtml(post.location)}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>${escapeHtml(post.location)}</span>` : `<span class="pill-badge badge-location" style="opacity: 0.55;" title="Location not specified in post"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>Not Specified</span>`}
          </div>
          <span class="recruiter-headline">${escapeHtml(post.author_headline || '')}</span>
        </div>
      </td>
      <td>
        <span class="pill-badge ${expClass}">${escapeHtml(expText)}</span>
      </td>
      <td>
        ${dateHtml}
      </td>
      <td>
        ${emailHtml}
      </td>
      <td>
        ${phoneHtml}
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
              ? `<span class="pill-badge" style="background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.25); font-size: 0.72rem; padding: 0.2rem 0.5rem; display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>Sent</span>
                 <button class="btn btn-icon-only" onclick="switchTab('tabSent')" title="View in Sent History">
                   <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                 </button>`
              : post.status === 'REJECTED'
                ? `<span class="badge-status-rejected" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Cancelled</span>
                   <button class="btn btn-icon-only btn-restore" onclick="revertPostToDraft('${post.id}')" title="Restore Post">
                     <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v6h6"></path><path d="M21 12A9 9 0 0 0 6 5.3L3 8"></path></svg>
                   </button>`
                : isGenerated
                  ? `<button class="btn btn-outline btn-sm" onclick="openPostInReview('${post.id}')" title="Review Generated Draft">
                       <span>Review Draft</span>
                     </button>
                     <button class="btn btn-icon-only btn-spam-icon" onclick="markPostAsSpam('${post.id}')" title="Mark as Spam / Scam">
                       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
                     </button>
                     <button class="btn btn-icon-only btn-cancel-icon" onclick="cancelDiscoveredPost('${post.id}')" title="Cancel opening with reason">
                       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                     </button>`
                  : `
                     ${primaryEmail ? `<button class="btn btn-primary btn-sm" onclick="generateSingleChatGPT('${post.id}')" title="Generate with ChatGPT"><span>Generate</span></button>` : ''}
                     <button class="btn btn-outline btn-sm" onclick="movePostToReview('${post.id}')" title="Move directly to Review & Drafts">
                       <span>Review</span>
                     </button>
                     <button class="btn btn-icon-only btn-spam-icon" onclick="markPostAsSpam('${post.id}')" title="Mark as Spam / Scam">
                       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
                     </button>
                     <button class="btn btn-icon-only btn-cancel-icon" onclick="cancelDiscoveredPost('${post.id}')" title="Cancel opening with reason">
                       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
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

function renderPagination() {
  const totalPages = Math.ceil(state.total / state.limit) || 1;
  const startRow = state.total === 0 ? 0 : (state.page - 1) * state.limit + 1;
  const endRow = Math.min(state.page * state.limit, state.total);
  const textInfo = `Showing ${startRow}–${endRow} of ${state.total} posts`;

  const pagInfoEl = document.getElementById('paginationInfo');
  if (pagInfoEl) pagInfoEl.textContent = textInfo;
  const pagInfoTopEl = document.getElementById('paginationInfoTop');
  if (pagInfoTopEl) pagInfoTopEl.textContent = textInfo;

  // Sync rows per page selects
  const selLimit = document.getElementById('selectLimit');
  if (selLimit) selLimit.value = String(state.limit);
  const selLimitTop = document.getElementById('selectLimitTop');
  if (selLimitTop) selLimitTop.value = String(state.limit);

  const containers = [
    document.getElementById('pageButtons'),
    document.getElementById('pageButtonsTop')
  ].filter(Boolean);

  containers.forEach(container => {
    container.innerHTML = '';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.textContent = '‹';
    prevBtn.disabled = state.page <= 1;
    prevBtn.onclick = () => goToPage(state.page - 1);
    container.appendChild(prevBtn);

    const startPage = Math.max(1, state.page - 2);
    const endPage = Math.min(totalPages, state.page + 2);

    for (let p = startPage; p <= endPage; p++) {
      const pBtn = document.createElement('button');
      pBtn.className = `page-btn ${p === state.page ? 'active' : ''}`;
      pBtn.textContent = String(p);
      pBtn.onclick = () => goToPage(p);
      container.appendChild(pBtn);
    }

    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.textContent = '›';
    nextBtn.disabled = state.page >= totalPages;
    nextBtn.onclick = () => goToPage(state.page + 1);
    container.appendChild(nextBtn);
  });
}

function goToPage(p) {
  state.page = p;
  fetchDiscoveredPosts();
}

function changeRowsPerPage(val) {
  state.limit = parseInt(val, 10) || 25;
  state.page = 1;
  const selLimit = document.getElementById('selectLimit');
  if (selLimit) selLimit.value = String(state.limit);
  const selLimitTop = document.getElementById('selectLimitTop');
  if (selLimitTop) selLimitTop.value = String(state.limit);
  fetchDiscoveredPosts();
}

function setExpFilter(tier) {
  state.expFilter = tier;
  state.page = 1;
  document.querySelectorAll('#expPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.exp === tier);
  });
  fetchDiscoveredPosts();
}

function applyFilters() {
  const catSel = document.getElementById('selectCategory');
  if (catSel) state.categoryFilter = catSel.value;

  const genSelect = document.getElementById('selectGenStatus');
  if (genSelect) state.genStatusFilter = genSelect.value;

  const srcSelect = document.getElementById('selectSource');
  if (srcSelect) state.sourceFilter = srcSelect.value;

  const dateSelect = document.getElementById('selectDateFilter');
  if (dateSelect) {
    if (dateSelect.value === 'CUSTOM') {
      const customValInput = document.getElementById('customDateFilterValue');
      const customUnitSelect = document.getElementById('customDateFilterUnit');
      const val = parseInt(customValInput?.value || '12', 10);
      const unit = customUnitSelect?.value || 'hours';
      state.dateFilter = `${unit === 'hours' ? 'CUSTOM_HOURS' : 'CUSTOM_DAYS'}:${val}`;
    } else {
      state.dateFilter = dateSelect.value;
    }
  }

  const locSelect = document.getElementById('selectLocationFilter');
  if (locSelect) state.locationFilter = locSelect.value;

  const discReasonSelect = document.getElementById('selectReasonFilterDiscovered');
  if (discReasonSelect) {
    state.discoveredReason = discReasonSelect.value;
    discReasonSelect.title = discReasonSelect.value !== 'ALL' ? discReasonSelect.value : 'Filter by cancellation / rejection reason';
  }

  const sortSelect = document.getElementById('selectSortBy');
  if (sortSelect) {
    state.sortBy = sortSelect.value;
    updateSortIndicators();
  }

  const searchInput = document.getElementById('inputSearch');
  if (searchInput) state.searchQuery = searchInput.value.trim();

  state.page = 1;
  fetchDiscoveredPosts();
}

function handleSortSelectChange(val) {
  state.sortBy = val;
  updateSortIndicators();
  state.page = 1;
  fetchDiscoveredPosts();
}

function handleDateFilterSelectChange() {
  const dateSelect = document.getElementById('selectDateFilter');
  const customGroup = document.getElementById('customDateFilterGroup');
  if (dateSelect && customGroup) {
    const isCustom = dateSelect.value === 'CUSTOM';
    customGroup.classList.toggle('hidden', !isCustom);
  }
  applyFilters();
}

function toggleSort(col) {
  if (col === 'exp') {
    state.sortBy = state.sortBy === 'exp_asc' ? 'exp_desc' : 'exp_asc';
  } else if (col === 'date') {
    state.sortBy = state.sortBy === 'date_desc' ? 'date_asc' : 'date_desc';
  } else if (col === 'author') {
    state.sortBy = state.sortBy === 'author_asc' ? 'author_desc' : 'author_asc';
  }
  const sortSel = document.getElementById('selectSortBy');
  if (sortSel) sortSel.value = state.sortBy;
  updateSortIndicators();
  state.page = 1;
  fetchDiscoveredPosts();
}

function updateSortIndicators() {
  const expInd = document.getElementById('sortExpIndicator');
  const dateInd = document.getElementById('sortDateIndicator');
  const authorInd = document.getElementById('sortAuthorIndicator');

  if (expInd) {
    const isAsc = state.sortBy === 'exp_asc';
    const isDesc = state.sortBy === 'exp_desc';
    expInd.textContent = isAsc ? '▲' : isDesc ? '▼' : '↕';
    expInd.className = 'sort-indicator' + (isAsc || isDesc ? ' active' : '');
  }
  if (dateInd) {
    const isAsc = state.sortBy === 'date_asc';
    const isDesc = state.sortBy === 'date_desc';
    dateInd.textContent = isAsc ? '▲' : isDesc ? '▼' : '↕';
    dateInd.className = 'sort-indicator' + (isAsc || isDesc ? ' active' : '');
  }
  if (authorInd) {
    const isAsc = state.sortBy === 'author_asc';
    const isDesc = state.sortBy === 'author_desc';
    authorInd.textContent = isAsc ? '▲' : isDesc ? '▼' : '↕';
    authorInd.className = 'sort-indicator' + (isAsc || isDesc ? ' active' : '');
  }
}

function handleSearchKeyUp(e) {
  if (e.key === 'Enter') {
    applyFilters();
  }
}

function applyDiscoveredDateFilter() {
  const fromEl = document.getElementById('discoveredDateFrom');
  const toEl = document.getElementById('discoveredDateTo');
  state.fromDiscoveredDate = fromEl ? fromEl.value.trim() : '';
  state.toDiscoveredDate = toEl ? toEl.value.trim() : '';
  state.page = 1;
  fetchDiscoveredPosts();
}

function clearDiscoveredFilters() {
  state.expFilter = 'ALL';
  document.querySelectorAll('#expPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.exp === 'ALL');
  });

  state.categoryFilter = 'ALL';
  const catSel = document.getElementById('selectCategory');
  if (catSel) catSel.value = 'ALL';

  state.genStatusFilter = 'ALL';
  const genSel = document.getElementById('selectGenStatus');
  if (genSel) genSel.value = 'ALL';

  state.sourceFilter = 'ALL';
  const srcSel = document.getElementById('selectSource');
  if (srcSel) srcSel.value = 'ALL';

  state.dateFilter = 'ALL';
  const dateSel = document.getElementById('selectDateFilter');
  if (dateSel) dateSel.value = 'ALL';
  const customGroup = document.getElementById('customDateFilterGroup');
  if (customGroup) customGroup.classList.add('hidden');

  state.fromDiscoveredDate = '';
  state.toDiscoveredDate = '';
  const fromEl = document.getElementById('discoveredDateFrom');
  if (fromEl) fromEl.value = '';
  const toEl = document.getElementById('discoveredDateTo');
  if (toEl) toEl.value = '';

  state.locationFilter = 'ALL';
  const locSel = document.getElementById('selectLocationFilter');
  if (locSel) locSel.value = 'ALL';

  state.discoveredReason = 'ALL';
  const discReasonSel = document.getElementById('selectReasonFilterDiscovered');
  if (discReasonSel) {
    discReasonSel.value = 'ALL';
    discReasonSel.title = 'Filter by cancellation / rejection reason';
  }

  state.sortBy = 'default';
  const sortSel = document.getElementById('selectSortBy');
  if (sortSel) sortSel.value = 'default';
  updateSortIndicators();

  state.searchQuery = '';
  const searchInput = document.getElementById('inputSearch');
  if (searchInput) searchInput.value = '';

  updateActiveFilterChips();
  state.page = 1;
  fetchDiscoveredPosts();
}

/**
 * Dynamically updates the active filter chips bar at the bottom of the Discovered toolbar.
 * Shows selected filter details with a clean (x) close button.
 */
function updateActiveFilterChips() {
  const bar = document.getElementById('discoveredActiveFiltersBar');
  const list = document.getElementById('discoveredActiveFiltersList');
  if (!bar || !list) return;

  const chips = [];

  // Reason Filter Chip
  if (state.discoveredReason && state.discoveredReason !== 'ALL') {
    chips.push(`
      <span class="filter-chip" title="Cancellation / Rejection Reason: ${escapeHtml(state.discoveredReason)}">
        <span class="chip-label">Reason:</span>
        <span class="chip-val">${escapeHtml(state.discoveredReason)}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('reason')" title="Remove Reason filter">✕</button>
      </span>
    `);
  }

  // Location Filter Chip
  if (state.locationFilter && state.locationFilter !== 'ALL') {
    chips.push(`
      <span class="filter-chip" title="Location: ${escapeHtml(state.locationFilter)}">
        <span class="chip-label">Location:</span>
        <span class="chip-val">${escapeHtml(state.locationFilter)}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('location')" title="Remove Location filter">✕</button>
      </span>
    `);
  }

  // Experience Filter Chip
  if (state.expFilter && state.expFilter !== 'ALL') {
    const expLabel = state.expFilter === 'FRESHER' ? 'Fresher (0-1 yr)' : state.expFilter === 'MID' ? '1 - 3 yrs' : '3 - 5+ yrs';
    chips.push(`
      <span class="filter-chip" title="Experience Level: ${expLabel}">
        <span class="chip-label">Exp:</span>
        <span class="chip-val">${expLabel}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('exp')" title="Remove Experience filter">✕</button>
      </span>
    `);
  }

  // Source Filter Chip
  if (state.sourceFilter && state.sourceFilter !== 'ALL') {
    chips.push(`
      <span class="filter-chip" title="Job Source: ${escapeHtml(state.sourceFilter)}">
        <span class="chip-label">Source:</span>
        <span class="chip-val">${escapeHtml(state.sourceFilter)}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('source')" title="Remove Source filter">✕</button>
      </span>
    `);
  }

  // Status Filter Chip (if non-default)
  if (state.genStatusFilter && state.genStatusFilter !== 'PENDING' && state.genStatusFilter !== 'ALL') {
    const statusMap = { GENERATED: 'Already Generated', SENT: 'Sent Applications', REJECTED: 'Cancelled / Screened' };
    chips.push(`
      <span class="filter-chip" title="Status: ${statusMap[state.genStatusFilter] || state.genStatusFilter}">
        <span class="chip-label">Status:</span>
        <span class="chip-val">${statusMap[state.genStatusFilter] || escapeHtml(state.genStatusFilter)}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('genStatus')" title="Reset Status to default">✕</button>
      </span>
    `);
  }

  // Date Filter Chip
  if (state.dateFilter && state.dateFilter !== 'ALL') {
    let dateTxt = state.dateFilter;
    if (dateTxt === '24H') dateTxt = 'Last 24 Hours';
    else if (dateTxt === 'TODAY') dateTxt = 'Today';
    else if (dateTxt === 'YESTERDAY') dateTxt = 'Yesterday';
    else if (dateTxt === '2D') dateTxt = 'Last 2 Days';
    else if (dateTxt === '3D') dateTxt = 'Last 3 Days';
    else if (dateTxt === 'WEEK') dateTxt = 'Past 7 Days';
    else if (dateTxt.startsWith('CUSTOM')) dateTxt = dateTxt.replace('CUSTOM_HOURS:', '').replace('CUSTOM_DAYS:', '') + (dateTxt.includes('HOURS') ? ' hrs' : ' days');
    chips.push(`
      <span class="filter-chip" title="Date: ${escapeHtml(dateTxt)}">
        <span class="chip-label">Date:</span>
        <span class="chip-val">${escapeHtml(dateTxt)}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('date')" title="Remove Date filter">✕</button>
      </span>
    `);
  }

  // From-To Date Range
  if (state.fromDiscoveredDate || state.toDiscoveredDate) {
    const rangeTxt = `${state.fromDiscoveredDate || '...'} → ${state.toDiscoveredDate || '...'}`;
    chips.push(`
      <span class="filter-chip" title="Date Range: ${rangeTxt}">
        <span class="chip-label">Range:</span>
        <span class="chip-val">${rangeTxt}</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('dateRange')" title="Remove Date Range">✕</button>
      </span>
    `);
  }

  // Search Query
  if (state.searchQuery && state.searchQuery.trim()) {
    chips.push(`
      <span class="filter-chip" title="Search query: ${escapeHtml(state.searchQuery)}">
        <span class="chip-label">Search:</span>
        <span class="chip-val">"${escapeHtml(state.searchQuery)}"</span>
        <button type="button" class="btn-chip-remove" onclick="removeDiscoveredFilter('search')" title="Clear Search">✕</button>
      </span>
    `);
  }

  if (chips.length > 0) {
    list.innerHTML = chips.join('');
    bar.classList.remove('hidden');
  } else {
    list.innerHTML = '';
    bar.classList.add('hidden');
  }
}

/**
 * Removes an individual filter from the active filter chips bar and refreshes results.
 */
function removeDiscoveredFilter(filterType) {
  if (filterType === 'reason') {
    state.discoveredReason = 'ALL';
    const sel = document.getElementById('selectReasonFilterDiscovered');
    if (sel) {
      sel.value = 'ALL';
      sel.title = 'Filter by cancellation / rejection reason';
    }
  } else if (filterType === 'location') {
    state.locationFilter = 'ALL';
    const sel = document.getElementById('selectLocationFilter');
    if (sel) sel.value = 'ALL';
  } else if (filterType === 'exp') {
    setExpFilter('ALL');
    return;
  } else if (filterType === 'source') {
    state.sourceFilter = 'ALL';
    const sel = document.getElementById('selectSource');
    if (sel) sel.value = 'ALL';
  } else if (filterType === 'genStatus') {
    state.genStatusFilter = 'PENDING';
    const sel = document.getElementById('selectGenStatus');
    if (sel) sel.value = 'PENDING';
  } else if (filterType === 'date') {
    state.dateFilter = 'ALL';
    const sel = document.getElementById('selectDateFilter');
    if (sel) sel.value = 'ALL';
    const customGroup = document.getElementById('customDateFilterGroup');
    if (customGroup) customGroup.classList.add('hidden');
  } else if (filterType === 'dateRange') {
    state.fromDiscoveredDate = '';
    state.toDiscoveredDate = '';
    const fromEl = document.getElementById('discoveredDateFrom');
    if (fromEl) fromEl.value = '';
    const toEl = document.getElementById('discoveredDateTo');
    if (toEl) toEl.value = '';
  } else if (filterType === 'search') {
    state.searchQuery = '';
    const input = document.getElementById('inputSearch');
    if (input) input.value = '';
  }

  applyFilters();
}

function filterPendingGeneration() {
  switchTab('tabDiscovered');
  const catSel = document.getElementById('selectCategory');
  if (catSel) catSel.value = 'EMAIL_OUTREACH';
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
  const dismissBtn = document.getElementById('btnBatchDismiss');
  const dismissBadge = document.getElementById('batchDismissCountBadge');

  if (batchBtn && countBadge) {
    if (count > 0) {
      batchBtn.classList.remove('hidden');
      countBadge.textContent = String(count);
    } else {
      batchBtn.classList.add('hidden');
    }
  }

  if (dismissBtn && dismissBadge) {
    if (count > 0) {
      dismissBtn.classList.remove('hidden');
      dismissBadge.textContent = String(count);
    } else {
      dismissBtn.classList.add('hidden');
    }
  }

  const selectAllCb = document.getElementById('selectAllCheckbox');
  if (selectAllCb) {
    if (!state.posts || state.posts.length === 0) {
      selectAllCb.checked = false;
      selectAllCb.indeterminate = false;
    } else {
      const allSelected = state.posts.every((p) => state.selectedIds.has(p.id));
      const someSelected = !allSelected && state.posts.some((p) => state.selectedIds.has(p.id));
      selectAllCb.checked = allSelected;
      selectAllCb.indeterminate = someSelected;
    }
  }
}

function cancelBatchSelectedDiscovered() {
  const count = state.selectedIds ? state.selectedIds.size : 0;
  if (count === 0) return;

  state.pendingCancelPostIds = Array.from(state.selectedIds);
  state.pendingCancelPostId = null;
  state.pendingCancelSource = 'discovered';
  state.isSpamCancelMode = false;

  const titleEl = document.getElementById('cancelModalTitle');
  if (titleEl) {
    titleEl.textContent = `Dismiss ${count} Discovered Post${count === 1 ? '' : 's'}`;
  }

  const descEl = document.getElementById('cancelModalDesc');
  if (descEl) {
    descEl.innerHTML = `Select a suggestion below or type a custom reason. All <strong>${count} selected post${count === 1 ? '' : 's'}</strong> will be removed from Discovered and moved to your <strong>Others</strong> history.`;
  }

  const checkAddToDismissed = document.getElementById('checkAddToDismissedRoles');
  if (checkAddToDismissed) checkAddToDismissed.checked = false;

  const btnPostOnly = document.getElementById('btnDismissPostOnly');
  if (btnPostOnly) {
    btnPostOnly.textContent = `Dismiss ${count} Post${count === 1 ? '' : 's'} Only`;
  }
  const btnBlacklist = document.getElementById('btnDismissAndBlacklist');
  if (btnBlacklist) {
    btnBlacklist.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg><span>🚫 Dismiss & Add Roles (${count})</span>`;
  }

  const nameEl = document.getElementById('cancelModalCandidate');
  if (nameEl) nameEl.textContent = `for ${count} selected posts`;

  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = 'Irrelevant tech stack';
  }

  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((c) => {
    const chipVal = c.getAttribute('data-reason') || c.textContent.trim();
    c.classList.toggle('active', chipVal.toLowerCase() === 'irrelevant tech stack');
  });

  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
  }, 50);
}

// ==========================================================================
// Discovered Jobs Side Detail Drawer Management
// ==========================================================================

function handleDiscoveredRowClick(postId, event) {
  if (event.target.closest('input[type="checkbox"], button, a, .phone-copy-pill, .email-copy-pill')) {
    return;
  }
  openDiscoveredDetailDrawer(postId);
}

function openDiscoveredDetailDrawer(postId) {
  state.activeDiscoveredPostId = postId;
  const post = state.posts && state.posts.find((p) => p.id === postId);
  if (!post) return;

  // Active row highlight
  document.querySelectorAll('#postsTableBody tr').forEach((r) => r.classList.remove('active-row'));
  const row = document.getElementById(`row-${postId}`);
  if (row) row.classList.add('active-row');

  // Title & Source Badge
  const authorEl = document.getElementById('discoveredDrawerAuthor');
  if (authorEl) authorEl.textContent = post.author_name || 'Recruiter';

  const badgeEl = document.getElementById('discoveredDrawerSourceBadge');
  if (badgeEl) badgeEl.innerHTML = getSourceBadgeHtml(post);

  // Email
  const primaryEmail = (post.contact_emails && post.contact_emails[0]) || '';
  const emailEl = document.getElementById('discoveredDrawerEmail');
  const copyEmailBtn = document.getElementById('btnCopyDiscoveredEmail');
  if (emailEl) emailEl.textContent = primaryEmail || '—';
  if (copyEmailBtn) {
    if (primaryEmail) copyEmailBtn.classList.remove('hidden');
    else copyEmailBtn.classList.add('hidden');
  }

  // Contact Phone
  const primaryPhone = (post.contact_phones && post.contact_phones[0]) || '';
  const phoneEl = document.getElementById('discoveredDrawerPhone');
  const copyPhoneBtn = document.getElementById('btnCopyDiscoveredPhone');
  if (phoneEl) phoneEl.textContent = primaryPhone || '—';
  if (copyPhoneBtn) {
    if (primaryPhone) copyPhoneBtn.classList.remove('hidden');
    else copyPhoneBtn.classList.add('hidden');
  }

  // Job Description
  const jdEl = document.getElementById('discoveredDrawerJd');
  if (jdEl) jdEl.textContent = post.full_text || 'No job description text available.';

  // Source Link
  const sourceLink = document.getElementById('discoveredDrawerSourceLink');
  if (sourceLink) {
    if (post.post_url && !post.post_url.startsWith('manual://')) {
      sourceLink.href = post.post_url;
      sourceLink.classList.remove('hidden');
    } else {
      sourceLink.classList.add('hidden');
    }
  }

  // Action Buttons
  const genBtn = document.getElementById('btnDrawerGenerateMail');
  const genText = document.getElementById('drawerGenBtnText');
  const reviewBtn = document.getElementById('btnDrawerReview');
  const reviewText = document.getElementById('drawerReviewBtnText');

  const isGenerated = post.status === 'EMAIL_GENERATED';
  if (genText) genText.textContent = isGenerated ? 'Re-generate' : 'Generate Mail';
  if (reviewText) reviewText.textContent = isGenerated ? 'Review Draft' : 'Review';

  // Open Drawer & Set Workspace Class
  const drawer = document.getElementById('discoveredDetailDrawer');
  const wrapper = document.getElementById('discoveredWorkspaceWrapper');
  if (drawer) drawer.classList.remove('hidden');
  if (wrapper) wrapper.classList.add('drawer-open');
}

function closeDiscoveredDetailDrawer() {
  state.activeDiscoveredPostId = null;
  const drawer = document.getElementById('discoveredDetailDrawer');
  const wrapper = document.getElementById('discoveredWorkspaceWrapper');
  if (drawer) drawer.classList.add('hidden');
  if (wrapper) wrapper.classList.remove('drawer-open');
  document.querySelectorAll('#postsTableBody tr').forEach((r) => r.classList.remove('active-row'));
}

function drawerGenerateMailDiscovered() {
  if (!state.activeDiscoveredPostId) return;
  const post = state.posts && state.posts.find((p) => p.id === state.activeDiscoveredPostId);
  if (!post) return;
  generateSingleChatGPT(post.id);
}

function drawerMoveToReviewDiscovered() {
  if (!state.activeDiscoveredPostId) return;
  const post = state.posts && state.posts.find((p) => p.id === state.activeDiscoveredPostId);
  if (!post) return;
  if (post.status === 'EMAIL_GENERATED') {
    openPostInReview(post.id);
  } else {
    movePostToReview(post.id);
  }
}

function copyDiscoveredDrawerEmail() {
  if (!state.activeDiscoveredPostId) return;
  const post = state.posts && state.posts.find((p) => p.id === state.activeDiscoveredPostId);
  const email = (post && post.contact_emails && post.contact_emails[0]) || '';
  if (email && typeof copyEmailToClipboard === 'function') {
    copyEmailToClipboard(email);
  }
}

function copyDiscoveredDrawerPhone() {
  if (!state.activeDiscoveredPostId) return;
  const post = state.posts && state.posts.find((p) => p.id === state.activeDiscoveredPostId);
  const phone = (post && post.contact_phones && post.contact_phones[0]) || '';
  if (phone && typeof copyPhoneToClipboard === 'function') {
    copyPhoneToClipboard(phone);
  }
}

function copyDiscoveredDrawerJd() {
  const jdEl = document.getElementById('discoveredDrawerJd');
  const text = jdEl ? jdEl.textContent : '';
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    if (typeof showToast === 'function') showToast('✓ Job description copied to clipboard', 'success');
  });
}

// Global Keyboard Listener for Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const drawer = document.getElementById('discoveredDetailDrawer');
    if (drawer && !drawer.classList.contains('hidden')) {
      closeDiscoveredDetailDrawer();
    }
  }
});

// Global Bindings
window.fetchDiscoveredPosts = fetchDiscoveredPosts;
window.loadDiscoveredPosts = fetchDiscoveredPosts;
window.renderSkeletonRows = renderSkeletonRows;
window.getSourceBadgeHtml = getSourceBadgeHtml;
window.renderPostsTable = renderPostsTable;
window.renderPagination = renderPagination;
window.goToPage = goToPage;
window.changeRowsPerPage = changeRowsPerPage;
window.setExpFilter = setExpFilter;
window.applyFilters = applyFilters;
window.handleSortSelectChange = handleSortSelectChange;
window.handleDateFilterSelectChange = handleDateFilterSelectChange;
window.toggleSort = toggleSort;
window.updateSortIndicators = updateSortIndicators;
window.handleSearchKeyUp = handleSearchKeyUp;
window.clearDiscoveredFilters = clearDiscoveredFilters;
window.applyDiscoveredDateFilter = applyDiscoveredDateFilter;
window.filterPendingGeneration = filterPendingGeneration;
window.movePostToReview = movePostToReview;
window.toggleSelectPost = toggleSelectPost;
window.toggleSelectAll = toggleSelectAll;
window.updateSelectedCountUI = updateSelectedCountUI;
window.cancelBatchSelectedDiscovered = cancelBatchSelectedDiscovered;
window.handleDiscoveredRowClick = handleDiscoveredRowClick;
window.openDiscoveredDetailDrawer = openDiscoveredDetailDrawer;
window.closeDiscoveredDetailDrawer = closeDiscoveredDetailDrawer;
window.drawerGenerateMailDiscovered = drawerGenerateMailDiscovered;
window.drawerMoveToReviewDiscovered = drawerMoveToReviewDiscovered;
window.drawerDismissDiscovered = drawerDismissDiscovered;
window.copyDiscoveredDrawerEmail = copyDiscoveredDrawerEmail;
window.copyDiscoveredDrawerPhone = copyDiscoveredDrawerPhone;
window.copyDiscoveredDrawerJd = copyDiscoveredDrawerJd;

function drawerDismissDiscovered() {
  if (!state.activeDiscoveredPostId) return;
  cancelDiscoveredPost(state.activeDiscoveredPostId);
}
