/**
 * Reach — Dismissed Roles Registry Workspace
 * (src/static/js/dismissed_roles.js)
 * 
 * Manages viewing, searching, adding, restoring, and auto-dismissing
 * job roles across LinkedIn, Indeed, Easy Apply, and Infopark.
 */

const dismissedRolesState = {
  page: 1,
  limit: 50,
  total: 0,
  search: '',
  source: 'ALL',
  order_by: 'name_asc',
  selectedIds: new Set(),
  roles: [],
  searchDebounce: null,
};

async function loadDismissedRolesPage() {
  await Promise.all([
    fetchDismissedRolesStats(),
    fetchDismissedRolesList(),
  ]);
}

async function fetchDismissedRolesStats() {
  try {
    const res = await fetch('/api/dismissed-roles/stats');
    if (!res.ok) return;
    const data = await res.json();

    const total = data.total || 0;
    const srcMap = data.sources || {};

    const elAll = document.getElementById('countDismissedAll');
    const elLinkedIn = document.getElementById('countDismissedLinkedIn');
    const elEasyApply = document.getElementById('countDismissedEasyApply');
    const elIndeed = document.getElementById('countDismissedIndeed');
    const elInfopark = document.getElementById('countDismissedInfopark');
    const elManual = document.getElementById('countDismissedManual');
    const sidebarBadge = document.getElementById('countSidebarDismissedRoles');

    if (elAll) elAll.textContent = Number(total).toLocaleString();
    if (sidebarBadge) sidebarBadge.textContent = Number(total).toLocaleString();
    if (elLinkedIn) elLinkedIn.textContent = Number(srcMap['LinkedIn Posts'] || 0).toLocaleString();
    if (elEasyApply) elEasyApply.textContent = Number(srcMap['LinkedIn Easy Apply'] || 0).toLocaleString();
    if (elIndeed) elIndeed.textContent = Number(srcMap['Indeed Apply'] || 0).toLocaleString();
    if (elInfopark) elInfopark.textContent = Number(srcMap['Infopark'] || 0).toLocaleString();
    if (elManual) elManual.textContent = Number(srcMap['Manual'] || 0).toLocaleString();
  } catch (err) {
    console.warn('Failed to fetch dismissed roles stats:', err);
  }
}

async function fetchDismissedRolesList() {
  const tbody = document.getElementById('tbodyDismissedRoles');
  if (!tbody) return;

  const offset = (dismissedRolesState.page - 1) * dismissedRolesState.limit;
  const params = new URLSearchParams({
    limit: String(dismissedRolesState.limit),
    offset: String(offset),
    order_by: dismissedRolesState.order_by,
  });

  if (dismissedRolesState.search) {
    params.append('search', dismissedRolesState.search);
  }
  if (dismissedRolesState.source && dismissedRolesState.source !== 'ALL') {
    params.append('source', dismissedRolesState.source);
  }

  try {
    const res = await fetch(`/api/dismissed-roles?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    dismissedRolesState.roles = data.roles || [];
    dismissedRolesState.total = typeof data.total === 'number' ? data.total : dismissedRolesState.roles.length;

    renderDismissedRolesTable();
    renderDismissedPagination();

    // Toggle Clear Filters button
    const hasFilter = Boolean(dismissedRolesState.search) || dismissedRolesState.source !== 'ALL' || dismissedRolesState.order_by !== 'name_asc';
    const clearBtn = document.getElementById('btnClearDismissedFilters');
    if (clearBtn) clearBtn.classList.toggle('hidden', !hasFilter);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #f43f5e;">Failed to load dismissed roles: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderDismissedRolesTable() {
  const tbody = document.getElementById('tbodyDismissedRoles');
  if (!tbody) return;

  const roles = dismissedRolesState.roles;
  const badgeEl = document.getElementById('badgeDismissedRolesResults');
  if (badgeEl) {
    badgeEl.textContent = `${Number(dismissedRolesState.total).toLocaleString()} role${dismissedRolesState.total === 1 ? '' : 's'}`;
  }

  if (!roles.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; padding: 3.5rem; color: var(--text-dim);">
          <div style="font-size: 1rem; font-weight: 600; margin-bottom: 0.35rem; color: var(--text-main);">No dismissed roles found</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">No entries match your search or filter criteria.</div>
        </td>
      </tr>
    `;
    updateBatchDeleteButton();
    return;
  }

  const selectAllCb = document.getElementById('selectAllDismissedRoles');
  if (selectAllCb) {
    const allSelected = roles.length > 0 && roles.every(r => dismissedRolesState.selectedIds.has(r.id));
    selectAllCb.checked = allSelected;
  }

  let html = '';
  for (const r of roles) {
    const isChecked = dismissedRolesState.selectedIds.has(r.id);
    const sourceClass = getSourceBadgeClass(r.source);
    const formattedDate = formatRoleDate(r.updated_at || r.created_at);

    html += `
      <tr class="${isChecked ? 'selected' : ''}">
        <td style="text-align: center;">
          <input type="checkbox" class="table-cb dismissed-cb" value="${r.id}" ${isChecked ? 'checked' : ''} onchange="toggleSelectDismissedRole('${r.id}', this.checked)" />
        </td>
        <td>
          <div class="role-title-cell" title="${escapeHtml(r.role_title)}">
            ${escapeHtml(r.role_title)}
          </div>
        </td>
        <td>
          <span class="badge-source-tag ${sourceClass}">
            ${escapeHtml(r.source || 'LinkedIn Posts')}
          </span>
        </td>
        <td>
          <div class="role-reason-cell" title="${escapeHtml(r.reason || 'No specific reason recorded')}">
            ${escapeHtml(r.reason || 'Previously dismissed role')}
          </div>
        </td>
        <td style="text-align: center;">
          <span class="badge-occurrences" title="${r.occurrences || 1} occurrences encountered across crawlers">
            ${r.occurrences || 1}x
          </span>
        </td>
        <td>
          <div class="role-date-cell" title="${escapeHtml(r.updated_at || '')}">
            ${formattedDate}
          </div>
        </td>
        <td style="text-align: right;">
          <button type="button" class="btn btn-outline btn-xs btn-remove-role" onclick="deleteSingleDismissedRole('${r.id}', '${escapeJs(r.role_title)}')" title="Restore this role so it will no longer be auto-dismissed">
            Restore
          </button>
        </td>
      </tr>
    `;
  }

  tbody.innerHTML = html;
  updateBatchDeleteButton();
}

function renderDismissedPagination() {
  const totalPages = Math.ceil(dismissedRolesState.total / dismissedRolesState.limit) || 1;
  const startRow = dismissedRolesState.total === 0 ? 0 : (dismissedRolesState.page - 1) * dismissedRolesState.limit + 1;
  const endRow = Math.min(dismissedRolesState.page * dismissedRolesState.limit, dismissedRolesState.total);
  const textInfo = `Showing ${startRow}–${endRow} of ${Number(dismissedRolesState.total).toLocaleString()} roles`;

  const info = document.getElementById('dismissedRolesPageInfo');
  if (info) info.textContent = textInfo;
  const infoTop = document.getElementById('dismissedRolesPageInfoTop');
  if (infoTop) infoTop.textContent = textInfo;

  // Sync rows-per-page selects
  const selLimitBottom = document.getElementById('selectDismissedLimit');
  if (selLimitBottom) selLimitBottom.value = String(dismissedRolesState.limit);
  const selLimitTop = document.getElementById('selectDismissedLimitTop');
  if (selLimitTop) selLimitTop.value = String(dismissedRolesState.limit);

  const containers = [
    document.getElementById('dismissedPageButtons'),
    document.getElementById('dismissedPageButtonsTop')
  ].filter(Boolean);

  containers.forEach(container => {
    container.innerHTML = '';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.textContent = '‹';
    prevBtn.disabled = dismissedRolesState.page <= 1;
    prevBtn.onclick = () => goToDismissedPage(dismissedRolesState.page - 1);
    container.appendChild(prevBtn);

    const startPage = Math.max(1, dismissedRolesState.page - 2);
    const endPage = Math.min(totalPages, dismissedRolesState.page + 2);

    for (let p = startPage; p <= endPage; p++) {
      const pBtn = document.createElement('button');
      pBtn.className = `page-btn ${p === dismissedRolesState.page ? 'active' : ''}`;
      pBtn.textContent = String(p);
      pBtn.onclick = () => goToDismissedPage(p);
      container.appendChild(pBtn);
    }

    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.textContent = '›';
    nextBtn.disabled = dismissedRolesState.page >= totalPages;
    nextBtn.onclick = () => goToDismissedPage(dismissedRolesState.page + 1);
    container.appendChild(nextBtn);
  });
}

function goToDismissedPage(p) {
  dismissedRolesState.page = p;
  fetchDismissedRolesList();
}

function changeDismissedRowsPerPage(val) {
  dismissedRolesState.limit = parseInt(val, 10) || 50;
  dismissedRolesState.page = 1;
  const selBottom = document.getElementById('selectDismissedLimit');
  if (selBottom) selBottom.value = String(dismissedRolesState.limit);
  const selTop = document.getElementById('selectDismissedLimitTop');
  if (selTop) selTop.value = String(dismissedRolesState.limit);
  fetchDismissedRolesList();
}

function getSourceBadgeClass(source) {
  const s = (source || '').toLowerCase();
  if (s.includes('easy')) return 'easy-apply';
  if (s.includes('indeed')) return 'indeed';
  if (s.includes('infopark')) return 'infopark';
  if (s.includes('manual')) return 'manual';
  return 'linkedin';
}

function formatRoleDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const diffMs = now - d;
    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHrs / 24);

    const dateFormatted = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    if (diffDays === 0) {
      if (diffHrs === 0) return 'Just now';
      return `${diffHrs}h ago`;
    } else if (diffDays < 7) {
      return `${diffDays}d ago (${dateFormatted})`;
    }
    return dateFormatted;
  } catch (_) {
    return dateStr;
  }
}

function escapeJs(str) {
  return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function handleSearchDismissedRoles(val) {
  clearTimeout(dismissedRolesState.searchDebounce);
  dismissedRolesState.searchDebounce = setTimeout(() => {
    dismissedRolesState.search = (val || '').trim();
    dismissedRolesState.page = 1;
    fetchDismissedRolesList();
  }, 250);
}

function setDismissedRoleSourceFilter(source) {
  dismissedRolesState.source = source || 'ALL';
  dismissedRolesState.page = 1;
  document.querySelectorAll('#dismissedSourcePills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.source === dismissedRolesState.source);
  });
  fetchDismissedRolesList();
}

function handleSortDismissedRoles(val) {
  dismissedRolesState.order_by = val || 'name_asc';
  dismissedRolesState.page = 1;
  fetchDismissedRolesList();
}

function clearDismissedFilters() {
  dismissedRolesState.search = '';
  dismissedRolesState.source = 'ALL';
  dismissedRolesState.order_by = 'name_asc';
  dismissedRolesState.page = 1;

  const inputSearch = document.getElementById('inputSearchDismissedRoles');
  if (inputSearch) inputSearch.value = '';

  const selectSort = document.getElementById('selectDismissedRoleSort');
  if (selectSort) selectSort.value = 'name_asc';

  document.querySelectorAll('#dismissedSourcePills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.source === 'ALL');
  });

  const clearBtn = document.getElementById('btnClearDismissedFilters');
  if (clearBtn) clearBtn.classList.add('hidden');

  fetchDismissedRolesList();
}

function toggleSelectDismissedRole(id, checked) {
  if (checked) {
    dismissedRolesState.selectedIds.add(id);
  } else {
    dismissedRolesState.selectedIds.delete(id);
  }
  renderDismissedRolesTable();
}

function toggleSelectAllDismissedRoles(checked) {
  const roles = dismissedRolesState.roles;
  for (const r of roles) {
    if (checked) {
      dismissedRolesState.selectedIds.add(r.id);
    } else {
      dismissedRolesState.selectedIds.delete(r.id);
    }
  }
  renderDismissedRolesTable();
}

function updateBatchDeleteButton() {
  const btn = document.getElementById('btnBatchDeleteDismissedRoles');
  const text = document.getElementById('btnBatchDeleteDismissedRolesText');
  const banner = document.getElementById('dismissedBatchBanner');
  const bannerSelectedCount = document.getElementById('dismissedSelectedCount');
  const bannerBatchCount = document.getElementById('dismissedBatchCount');

  const count = dismissedRolesState.selectedIds.size;
  if (btn) {
    btn.classList.toggle('hidden', count === 0);
  }
  if (text) {
    text.textContent = `Restore Selected (${count})`;
  }

  if (banner) {
    banner.classList.toggle('hidden', count === 0);
  }
  if (bannerSelectedCount) {
    bannerSelectedCount.textContent = `${count} role${count === 1 ? '' : 's'} selected`;
  }
  if (bannerBatchCount) {
    bannerBatchCount.textContent = count;
  }
}

function clearDismissedSelection() {
  dismissedRolesState.selectedIds.clear();
  renderDismissedRolesTable();
}

async function deleteSingleDismissedRole(roleId, title) {
  const confirmed = await showConfirm(
    'Restore Dismissed Role',
    `Are you sure you want to restore "${title}"? Future scrapers will no longer auto-dismiss this role.`
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/dismissed-roles/${roleId}`, { method: 'DELETE' });
    if (res.ok) {
      dismissedRolesState.selectedIds.delete(roleId);
      showToast(`✓ Restored "${title}"`, 'success');
      await Promise.all([
        fetchDismissedRolesStats(),
        fetchDismissedRolesList(),
      ]);
    } else {
      const err = await res.json();
      showAlert('Restore Failed', err.detail || 'Could not restore role.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function deleteBatchDismissedRoles() {
  const ids = Array.from(dismissedRolesState.selectedIds);
  if (!ids.length) return;

  const confirmed = await showConfirm(
    'Restore Selected Roles',
    `Are you sure you want to restore ${ids.length} selected role(s)? These will no longer be auto-dismissed during scraping.`
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/dismissed-roles/delete-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });

    if (res.ok) {
      const data = await res.json();
      dismissedRolesState.selectedIds.clear();
      showToast(`✓ ${data.message || 'Restored selected roles'}`, 'success');
      await Promise.all([
        fetchDismissedRolesStats(),
        fetchDismissedRolesList(),
      ]);
    } else {
      const err = await res.json();
      showAlert('Batch Restore Failed', err.detail || 'Could not restore selected roles.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function syncDismissedRolesFromHistory() {
  const btn = document.getElementById('btnSyncDismissedFromHistory');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite;"></span> <span>Syncing...</span>`;
  }

  try {
    const res = await fetch('/api/dismissed-roles/sync', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      showToast(`✓ ${data.message || 'Synced roles from history'}`, 'success');
      await Promise.all([
        fetchDismissedRolesStats(),
        fetchDismissedRolesList(),
      ]);
    } else {
      const err = await res.json();
      showAlert('Sync Failed', err.detail || 'Could not sync dismissed roles.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
        </svg>
        <span>Sync History</span>
      `;
    }
  }
}

function openAddDismissedRoleModal() {
  const modal = document.getElementById('modalAddDismissedRole');
  if (modal) {
    const inputTitle = document.getElementById('inputAddDismissedTitle');
    const inputReason = document.getElementById('inputAddDismissedReason');
    if (inputTitle) inputTitle.value = '';
    if (inputReason) inputReason.value = '';
    modal.classList.remove('hidden');
    if (inputTitle) inputTitle.focus();
  }
}

function closeAddDismissedRoleModal() {
  const modal = document.getElementById('modalAddDismissedRole');
  if (modal) modal.classList.add('hidden');
}

async function submitAddDismissedRole() {
  const inputTitle = document.getElementById('inputAddDismissedTitle');
  const selectSource = document.getElementById('selectAddDismissedSource');
  const inputReason = document.getElementById('inputAddDismissedReason');

  const roleTitle = (inputTitle?.value || '').trim();
  const source = selectSource?.value || 'Manual';
  const reason = (inputReason?.value || '').trim();

  if (!roleTitle) {
    showAlert('Role Title Required', 'Please enter a job role title to dismiss.');
    return;
  }

  try {
    const res = await fetch('/api/dismissed-roles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        role_title: roleTitle,
        source: source,
        reason: reason || 'Manually added to exclusion list',
      }),
    });

    if (res.ok) {
      closeAddDismissedRoleModal();
      showToast(`✓ Added "${roleTitle}" to dismissed roles`, 'success');
      await Promise.all([
        fetchDismissedRolesStats(),
        fetchDismissedRolesList(),
      ]);
    } else {
      const err = await res.json();
      showAlert('Failed to Add Role', err.detail || 'Could not add role.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// Global Exports
window.loadDismissedRolesPage = loadDismissedRolesPage;
window.handleSearchDismissedRoles = handleSearchDismissedRoles;
window.setDismissedRoleSourceFilter = setDismissedRoleSourceFilter;
window.handleSortDismissedRoles = handleSortDismissedRoles;
window.clearDismissedFilters = clearDismissedFilters;
window.toggleSelectDismissedRole = toggleSelectDismissedRole;
window.toggleSelectAllDismissedRoles = toggleSelectAllDismissedRoles;
window.goToDismissedPage = goToDismissedPage;
window.changeDismissedRowsPerPage = changeDismissedRowsPerPage;
window.deleteSingleDismissedRole = deleteSingleDismissedRole;
window.deleteBatchDismissedRoles = deleteBatchDismissedRoles;
window.clearDismissedSelection = clearDismissedSelection;
window.syncDismissedRolesFromHistory = syncDismissedRolesFromHistory;
window.openAddDismissedRoleModal = openAddDismissedRoleModal;
window.closeAddDismissedRoleModal = closeAddDismissedRoleModal;
window.submitAddDismissedRole = submitAddDismissedRole;
