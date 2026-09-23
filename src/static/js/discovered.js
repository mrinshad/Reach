/**
 * Reach — Discovered Posts Table, Filtering, Pagination & Selection
 * (src/static/js/discovered.js)
 */

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

    if (state.sortBy && state.sortBy !== 'default') {
      params.append('order_by', state.sortBy);
    }

    if (state.dateFilter && state.dateFilter !== 'ALL') {
      params.append('date_filter', state.dateFilter);
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
    const isFiltered = state.expFilter !== 'ALL' || (state.searchQuery && state.searchQuery.trim() !== '') || state.sourceFilter !== 'ALL' || (state.genStatusFilter && state.genStatusFilter !== 'ALL') || state.categoryFilter !== 'ALL' || (state.dateFilter && state.dateFilter !== 'ALL') || (state.sortBy && state.sortBy !== 'default') || (state.locationFilter && state.locationFilter !== 'ALL') || (state.discoveredReason && state.discoveredReason !== 'ALL');
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
        <td><div class="skeleton-bar" style="width: 200px;"></div></td>
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

  if (isScam) {
    const why = rejReason || 'Flagged as scam recruiter';
    badge += `<span class="badge-scam-alert" title="Scam: ${escapeHtml(why)}">Scam</span>`;
  } else if (isPotential) {
    const why = potentialReason || rejReason || 'Suspicious contact domain or flagged recruiter activity';
    badge += `<span class="badge-spam-warning" title="Potential Scam: ${escapeHtml(why)}">Potential Scam</span>`;
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

    const isGenerated = post.status === 'EMAIL_GENERATED';

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="table-cb" data-id="${post.id}" ${state.selectedIds.has(post.id) ? 'checked' : ''} onchange="toggleSelectPost('${post.id}', this.checked)" />
      </td>
      <td>
        <div class="recruiter-cell">
          <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
            <span class="recruiter-name">${escapeHtml(post.author_name)}</span>
            ${getSourceBadgeHtml(post)}
            ${post.location ? `<span class="pill-badge badge-location" title="Location: ${escapeHtml(post.location)}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 2px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>${escapeHtml(post.location)}</span>` : ''}
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

  const pagInfoEl = document.getElementById('paginationInfo');
  if (pagInfoEl) pagInfoEl.textContent = `Showing ${startRow}–${endRow} of ${state.total} posts`;

  const container = document.getElementById('pageButtons');
  if (!container) return;
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
  if (discReasonSelect) state.discoveredReason = discReasonSelect.value;

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

  state.locationFilter = 'ALL';
  const locSel = document.getElementById('selectLocationFilter');
  if (locSel) locSel.value = 'ALL';

  state.discoveredReason = 'ALL';
  const discReasonSel = document.getElementById('selectReasonFilterDiscovered');
  if (discReasonSel) discReasonSel.value = 'ALL';

  state.sortBy = 'default';
  const sortSel = document.getElementById('selectSortBy');
  if (sortSel) sortSel.value = 'default';
  updateSortIndicators();

  state.searchQuery = '';
  const searchInput = document.getElementById('inputSearch');
  if (searchInput) searchInput.value = '';

  state.page = 1;
  fetchDiscoveredPosts();
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

  if (batchBtn && countBadge) {
    if (count > 0) {
      batchBtn.classList.remove('hidden');
      countBadge.textContent = String(count);
    } else {
      batchBtn.classList.add('hidden');
    }
  }
}

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
window.filterPendingGeneration = filterPendingGeneration;
window.movePostToReview = movePostToReview;
window.toggleSelectPost = toggleSelectPost;
window.toggleSelectAll = toggleSelectAll;
window.updateSelectedCountUI = updateSelectedCountUI;
