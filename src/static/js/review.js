/**
 * Reach — Review & Drafts Workspace, Full Outreach History Table, Docked Email Window & AI Editor
 * (src/static/js/review.js)
 */

let reviewSearchDebounce = null;
let reviewDateFrom = '';
let reviewDateTo = '';
let draftAutoSaveTimer = null;
let isDraftDirty = false;
const DRAFT_DEBOUNCE_MS = 1000;

function updateReviewClearFiltersButton() {
  const btn = document.getElementById('btnClearReviewFilters');
  if (!btn) return;
  const isFiltered = (state.reviewFilter && state.reviewFilter !== 'GENERATED') ||
                     (state.reviewSourceFilter && state.reviewSourceFilter !== 'ALL') ||
                     Boolean(state.searchReview) ||
                     Boolean(reviewDateFrom) ||
                     Boolean(reviewDateTo);
  btn.classList.toggle('hidden', !isFiltered);
}

function setReviewFilter(filter) {
  state.reviewFilter = filter || 'GENERATED';
  state.reviewPage = 1;

  document.querySelectorAll('#reviewStatusPills .pill').forEach((pill) => {
    const f = pill.getAttribute('data-review');
    pill.classList.toggle('active', f === state.reviewFilter);
  });

  updateReviewClearFiltersButton();
  fetchReviewPosts();
}

function applyReviewSourceFilter(source) {
  state.reviewSourceFilter = source || 'ALL';
  state.reviewPage = 1;
  updateReviewClearFiltersButton();
  fetchReviewPosts();
}

function applyReviewDateFilter() {
  const fromEl = document.getElementById('reviewDateFrom');
  const toEl = document.getElementById('reviewDateTo');
  reviewDateFrom = fromEl ? fromEl.value.trim() : '';
  reviewDateTo = toEl ? toEl.value.trim() : '';
  state.reviewPage = 1;
  updateReviewClearFiltersButton();
  fetchReviewPosts();
}

function clearReviewFilters() {
  state.reviewFilter = 'GENERATED';
  state.reviewSourceFilter = 'ALL';
  state.searchReview = '';
  reviewDateFrom = '';
  reviewDateTo = '';
  state.reviewPage = 1;

  const searchInput = document.getElementById('inputSearchReview');
  if (searchInput) searchInput.value = '';

  const sourceSelect = document.getElementById('selectReviewSource');
  if (sourceSelect) sourceSelect.value = 'ALL';

  const fromEl = document.getElementById('reviewDateFrom');
  if (fromEl) fromEl.value = '';
  const toEl = document.getElementById('reviewDateTo');
  if (toEl) toEl.value = '';

  document.querySelectorAll('#reviewStatusPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.getAttribute('data-review') === 'GENERATED');
  });

  updateReviewClearFiltersButton();
  fetchReviewPosts();
}

function handleSearchReview(val) {
  clearTimeout(reviewSearchDebounce);
  reviewSearchDebounce = setTimeout(() => {
    state.searchReview = (val || '').trim();
    state.reviewPage = 1;
    updateReviewClearFiltersButton();
    fetchReviewPosts();
  }, 250);
}

function updateReviewPaginationUI() {
  const infoEl = document.getElementById('reviewPageInfo');
  const infoTopEl = document.getElementById('reviewPageInfoTop');
  const btnPrev = document.getElementById('btnReviewPrevPage');
  const btnPrevTop = document.getElementById('btnReviewPrevPageTop');
  const btnNext = document.getElementById('btnReviewNextPage');
  const btnNextTop = document.getElementById('btnReviewNextPageTop');

  const total = state.reviewTotal || 0;
  const limit = state.reviewLimit || 25;
  const page = state.reviewPage || 1;
  const maxPage = Math.max(1, Math.ceil(total / limit));

  let textInfo = 'Showing 0 of 0 posts';
  if (total > 0) {
    const start = (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    textInfo = `Showing ${start}–${end} of ${total} posts`;
  }

  if (infoEl) infoEl.textContent = textInfo;
  if (infoTopEl) infoTopEl.textContent = textInfo;

  const isPrevDisabled = page <= 1;
  const isNextDisabled = page >= maxPage || total === 0;

  if (btnPrev) btnPrev.disabled = isPrevDisabled;
  if (btnPrevTop) btnPrevTop.disabled = isPrevDisabled;
  if (btnNext) btnNext.disabled = isNextDisabled;
  if (btnNextTop) btnNextTop.disabled = isNextDisabled;

  // Sync rows per page selects
  const selLimit = document.getElementById('selectReviewLimit');
  if (selLimit) selLimit.value = String(limit);
  const selLimitTop = document.getElementById('selectReviewLimitTop');
  if (selLimitTop) selLimitTop.value = String(limit);
}

function changeReviewRowsPerPage(val) {
  state.reviewLimit = parseInt(val, 10) || 25;
  state.reviewPage = 1;
  const sel = document.getElementById('selectReviewLimit');
  if (sel) sel.value = String(state.reviewLimit);
  const selTop = document.getElementById('selectReviewLimitTop');
  if (selTop) selTop.value = String(state.reviewLimit);
  fetchReviewPosts();
}

async function changeReviewPage(delta) {
  const total = state.reviewTotal || 0;
  const limit = state.reviewLimit || 25;
  const maxPage = Math.max(1, Math.ceil(total / limit));
  const newPage = (state.reviewPage || 1) + delta;

  if (newPage < 1 || newPage > maxPage) return;

  state.reviewPage = newPage;
  state.selectedDraftIds.clear();
  updateSelectedDraftsUI();

  await fetchReviewPosts();

  const container = document.getElementById('reviewTableContainer');
  if (container) container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderReviewSkeletonRows() {
  const tbody = document.getElementById('reviewTableBody');
  if (!tbody) return;
  let rowsHtml = '';
  for (let i = 0; i < 6; i++) {
    rowsHtml += `
      <tr class="skeleton-row">
        <td><div class="skeleton-box" style="width: 14px; height: 14px;"></div></td>
        <td>
          <div class="skeleton-box" style="width: 130px; height: 15px; margin-bottom: 4px;"></div>
          <div class="skeleton-box" style="width: 180px; height: 12px;"></div>
        </td>
        <td><div class="skeleton-box" style="width: 90px; height: 18px; border-radius: 4px;"></div></td>
        <td><div class="skeleton-box" style="width: 140px; height: 13px;"></div></td>
        <td><div class="skeleton-box" style="width: 200px; height: 14px;"></div></td>
        <td><div class="skeleton-box" style="width: 70px; height: 18px; border-radius: 4px;"></div></td>
        <td><div class="skeleton-box" style="width: 65px; height: 12px;"></div></td>
        <td style="text-align: right;"><div class="skeleton-box" style="width: 75px; height: 26px; border-radius: 4px; margin-left: auto;"></div></td>
      </tr>
    `;
  }
  tbody.innerHTML = rowsHtml;
}

async function fetchReviewPosts(forceSelectFirst = false) {
  const tbody = document.getElementById('reviewTableBody');
  if (!tbody) return;

  if (!state.reviewPosts || state.reviewPosts.length === 0) {
    renderReviewSkeletonRows();
  }

  const page = Math.max(1, state.reviewPage || 1);
  const limit = Math.max(1, state.reviewLimit || 25);
  const offset = (page - 1) * limit;

  try {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });

    const filter = state.reviewFilter || 'GENERATED';
    if (filter === 'ALL') {
      params.append('status', 'REVIEW_ALL');
      params.append('category', 'EMAIL_OUTREACH');
      params.append('order_by', 'generated_first');
    } else if (filter === 'GENERATED') {
      params.append('status', 'EMAIL_GENERATED');
    } else if (filter === 'PENDING') {
      params.append('gen_status', 'PENDING');
      params.append('category', 'EMAIL_OUTREACH');
    } else if (filter === 'SENT') {
      params.append('status', 'SENT');
    }

    if (state.reviewSourceFilter && state.reviewSourceFilter !== 'ALL') {
      params.append('source', state.reviewSourceFilter);
    }
    if (state.searchReview) {
      params.append('search', state.searchReview);
    }
    if (reviewDateFrom) {
      params.append('from_date', reviewDateFrom);
    }
    if (reviewDateTo) {
      params.append('to_date', reviewDateTo);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    state.reviewPosts = data.posts || [];
    state.reviewTotal = typeof data.total === 'number' ? data.total : (state.reviewPosts.length || 0);

    const badgeEl = document.getElementById('reviewResultsBadge');
    const isFiltered = (filter !== 'GENERATED') ||
                       (state.reviewSourceFilter && state.reviewSourceFilter !== 'ALL') ||
                       Boolean(state.searchReview) ||
                       Boolean(reviewDateFrom) ||
                       Boolean(reviewDateTo);
    if (badgeEl) {
      if (isFiltered) {
        badgeEl.textContent = `${state.reviewTotal} result${state.reviewTotal === 1 ? '' : 's'}`;
        badgeEl.classList.remove('hidden');
      } else {
        badgeEl.classList.add('hidden');
      }
    }

    updateReviewClearFiltersButton();
    updateReviewPaginationUI();
    tbody.innerHTML = '';

    if (state.reviewPosts.length === 0) {
      state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      const emptyMsg = state.searchReview
        ? `No outreach posts matching "${escapeHtml(state.searchReview)}" found.`
        : 'No posts matching the selected filter found.';
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 3rem; color: #64748b; font-size: 0.85rem;">${emptyMsg}</td></tr>`;
      return;
    }

    state.reviewPosts.forEach((post) => {
      const tr = document.createElement('tr');
      tr.id = `review-row-${post.id}`;
      const isActive = state.activeReviewPost && state.activeReviewPost.id === post.id;
      if (isActive) tr.classList.add('active-row');
      if (state.selectedDraftIds.has(post.id)) tr.classList.add('selected');

      const isChecked = state.selectedDraftIds.has(post.id);
      const email = (post.contact_emails && post.contact_emails[0]) || 'No email';
      const hasGeneratedBody = Boolean(post.generated_body && post.generated_body.trim().length > 0);
      const isSent = post.status === 'SENT';
      const isRejected = post.status === 'REJECTED';
      const isGenerated = post.status === 'EMAIL_GENERATED' || (hasGeneratedBody && !isSent && !isRejected);

      let statusBadgeHtml = '';
      if (isGenerated) {
        statusBadgeHtml = '<span class="badge-status-pill badge-status-generated">✓ Generated</span>';
      } else if (isSent) {
        statusBadgeHtml = '<span class="badge-status-pill badge-status-sent">✉ Sent</span>';
      } else if (isRejected) {
        statusBadgeHtml = '<span class="badge-status-pill badge-status-rejected">🚫 Cancelled</span>';
      } else {
        statusBadgeHtml = '<span class="badge-status-pill badge-status-pending">⏳ Yet to Generate</span>';
      }

      const expLabel = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
      const dateDisplay = typeof formatDateTime === 'function' ? formatDateTime(post.created_at || post.post_date) : (post.post_date || '—');

      let actionButtonHtml = '';
      if (isGenerated) {
        actionButtonHtml = `<button type="button" class="btn btn-outline btn-xs" onclick="event.stopPropagation(); openReviewDraftDrawer('${post.id}')" title="Open generated email draft in side drawer">View Email ✉</button>`;
      } else if (isSent) {
        actionButtonHtml = `<button type="button" class="btn btn-outline btn-xs" onclick="event.stopPropagation(); openReviewDraftDrawer('${post.id}')" title="View sent email details">View Sent</button>`;
      } else {
        actionButtonHtml = `<button type="button" class="btn btn-primary btn-xs" onclick="event.stopPropagation(); triggerGenerateSingleReviewPost('${post.id}')" title="Generate cold outreach email via ChatGPT">✨ Generate</button>`;
      }

      const subjectOrPreview = post.generated_subject
        ? `<div style="font-size: 0.78rem; font-weight: 600; color: var(--text-main); max-width: 290px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(post.generated_subject)}">${escapeHtml(post.generated_subject)}</div>`
        : `<div style="font-size: 0.74rem; color: var(--text-dim); max-width: 290px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(post.full_text || '')}">${escapeHtml((post.full_text || '').replace(/\s+/g, ' ').substring(0, 65))}...</div>`;

      tr.innerHTML = `
        <td>
          <input type="checkbox" class="draft-checkbox" value="${post.id}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelectDraft('${post.id}')" title="Select for batch action" />
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
            <strong style="color: var(--text-main); font-size: 0.85rem;">${escapeHtml(post.author_name)}</strong>
            ${getSourceBadgeHtml(post)}
            ${post.location ? `<span class="pill-badge badge-location" style="font-size: 0.66rem; padding: 0.1rem 0.35rem;" title="Location: ${escapeHtml(post.location)}">📍 ${escapeHtml(post.location)}</span>` : ''}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${escapeHtml(post.author_headline || '')}
          </div>
        </td>
        <td>${statusBadgeHtml}</td>
        <td>
          <span class="queue-email" style="display: inline-flex; align-items: center; gap: 0.25rem;">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
            ${escapeHtml(email)}
          </span>
        </td>
        <td>${subjectOrPreview}</td>
        <td><span class="pill-badge" style="font-size: 0.7rem;">${escapeHtml(expLabel)}</span></td>
        <td><span style="font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono);">${escapeHtml(dateDisplay)}</span></td>
        <td style="text-align: right;">${actionButtonHtml}</td>
      `;

      tr.onclick = (e) => {
        if (e.target.closest('input, button, a')) return;
        openReviewDraftDrawer(post.id);
      };

      tbody.appendChild(tr);
    });

    updateSelectedDraftsUI();

    // Auto-select drawer post if drawer was already open
    if (state.activeReviewPost) {
      const match = state.reviewPosts.find((p) => p.id === state.activeReviewPost.id);
      if (match) {
        populateDrawerWithPost(match);
      }
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 2.5rem; color: #ef4444;">Error loading posts: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function populateDrawerWithPost(post) {
  if (!post) return;

  const isSamePost = state.activeReviewPost && state.activeReviewPost.id === post.id;
  const subjInput = document.getElementById('draftSubject');
  const bodyInput = document.getElementById('draftBody');
  const hasFocus = (subjInput && document.activeElement === subjInput) ||
                    (bodyInput && document.activeElement === bodyInput);

  state.activeReviewPost = post;
  state.activePostId = post.id;

  const statusPill = document.getElementById('drawerStatusPill');
  const hasBody = Boolean(post.generated_body && post.generated_body.trim().length > 0);
  const isSent = post.status === 'SENT';

  if (statusPill) {
    if (isSent) {
      statusPill.textContent = '✉ Sent';
      statusPill.className = 'drawer-status-pill badge-status-sent';
    } else if (hasBody) {
      statusPill.textContent = '✓ Generated';
      statusPill.className = 'drawer-status-pill badge-status-generated';
    } else {
      statusPill.textContent = '⏳ Not Generated';
      statusPill.className = 'drawer-status-pill badge-status-pending';
    }
  }

  // Unready Banner
  const unreadyBanner = document.getElementById('drawerUnreadyBanner');
  if (unreadyBanner) {
    unreadyBanner.classList.toggle('hidden', hasBody || isSent);
  }

  const btnGenLabel = document.getElementById('btnGenerateMailLabel');
  if (btnGenLabel) {
    btnGenLabel.textContent = hasBody ? 'Re-gen' : 'Generate';
  }

  // Recipient email
  const emailEl = document.getElementById('reviewTargetEmail');
  if (emailEl) {
    const email = (post.contact_emails && post.contact_emails[0]) || 'No email';
    emailEl.textContent = email;
    emailEl.title = email;
  }

  // Subject and Body fields
  if (!isSamePost || (!isDraftDirty && !hasFocus)) {
    if (subjInput) subjInput.value = post.generated_subject || '';
    if (bodyInput) {
      let b = post.generated_body || '';
      if (typeof cleanEmailBody === 'function') {
        b = cleanEmailBody(b);
      }
      bodyInput.value = b;
      bodyInput.scrollTop = 0;
    }
    isDraftDirty = false;
    updateDraftSaveStatus('saved');
  }

  setupDraftInputListeners();

  const resume = state.config.resume_path || '';
  const resFilenameEl = document.getElementById('draftResumeFilename');
  if (resFilenameEl) resFilenameEl.textContent = resume.split('/').pop() || 'rinshadp.pdf';
}

async function openReviewDraftDrawer(postId) {
  if (!postId) return;

  // Flush previous unsaved edits if switching posts
  if (isDraftDirty && state.activeReviewPost && state.activeReviewPost.id !== postId) {
    await saveActiveDraftEdits({ silent: true });
  }

  let post = (state.reviewPosts || []).find((p) => p.id === postId)
          || (state.posts || []).find((p) => p.id === postId);

  if (!post) {
    try {
      const res = await fetch(`/api/posts/${postId}`);
      if (res.ok) post = await res.json();
    } catch (_) {}
  }

  if (!post) return;

  populateDrawerWithPost(post);

  // Show Drawer and adjust workspace layout
  const drawer = document.getElementById('reviewEmailDrawer');
  const wrapper = document.getElementById('reviewWorkspaceWrapper');
  if (drawer) drawer.classList.remove('hidden');
  if (wrapper) wrapper.classList.add('drawer-open');

  // Highlight active row in table
  document.querySelectorAll('#reviewTableBody tr').forEach((r) => r.classList.remove('active-row'));
  const targetRow = document.getElementById(`review-row-${postId}`);
  if (targetRow) targetRow.classList.add('active-row');
}

function closeReviewEmailDrawer() {
  if (isDraftDirty && state.activeReviewPost) {
    saveActiveDraftEdits({ silent: true });
  }

  const drawer = document.getElementById('reviewEmailDrawer');
  const wrapper = document.getElementById('reviewWorkspaceWrapper');
  if (drawer) drawer.classList.add('hidden');
  if (wrapper) wrapper.classList.remove('drawer-open');

  document.querySelectorAll('#reviewTableBody tr').forEach((r) => r.classList.remove('active-row'));
  state.activeReviewPost = null;
  state.activePostId = null;
}

function selectReviewPost(post) {
  if (!post) return;
  openReviewDraftDrawer(post.id);
}

async function openPostInReview(postId) {
  if (typeof switchTab === 'function') switchTab('tabReview');
  await openReviewDraftDrawer(postId);
}

async function triggerGenerateSingleReviewPost(postId) {
  await openReviewDraftDrawer(postId);
  await generateEmailForActiveDraft();
}

function updateDraftSaveStatus(status) {
  const statusEl = document.getElementById('draftSaveStatus');
  const btnBody = document.getElementById('btnSaveDraftBody');

  if (statusEl) {
    statusEl.className = `draft-save-status status-${status}`;
    if (status === 'saved') {
      statusEl.textContent = '✓ Saved';
    } else if (status === 'dirty') {
      statusEl.textContent = '● Unsaved';
    } else if (status === 'saving') {
      statusEl.textContent = '⟳ Saving...';
    }
  }

  if (btnBody) {
    btnBody.classList.toggle('dirty', status === 'dirty');
  }
}

function onDraftInputChange() {
  if (!state.activeReviewPost) return;
  isDraftDirty = true;
  updateDraftSaveStatus('dirty');

  if (draftAutoSaveTimer) clearTimeout(draftAutoSaveTimer);
  draftAutoSaveTimer = setTimeout(() => {
    saveActiveDraftEdits({ silent: true });
  }, DRAFT_DEBOUNCE_MS);
}

function setupDraftInputListeners() {
  const subjInput = document.getElementById('draftSubject');
  const bodyInput = document.getElementById('draftBody');

  [subjInput, bodyInput].forEach((input) => {
    if (!input || input._hasDraftListener) return;
    input._hasDraftListener = true;

    input.addEventListener('input', onDraftInputChange);
    input.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveActiveDraftEdits({ silent: false });
      }
    });
  });

  // Smart paste listener on Email Body field
  if (bodyInput && !bodyInput._hasPasteListener) {
    bodyInput._hasPasteListener = true;
    bodyInput.addEventListener('paste', (e) => {
      const pasteText = (e.clipboardData || window.clipboardData)?.getData('text');
      if (!pasteText) return;

      const isLikelyEmailDraft =
        /^(?:\*\*)?Subject(?:\*\*)?:/im.test(pasteText) ||
        /^(?:Send(?:\s+email)?|Connect email|Recipients|Email(?:\s+Draft)?)/im.test(pasteText) ||
        /\b(?:Regards|Sincerely|Thanks & Regards|Best|Cheers)[,\s]+[A-Za-z]+/i.test(pasteText);

      if (isLikelyEmailDraft && typeof parseAndCleanEmailInput === 'function') {
        const { subject, body } = parseAndCleanEmailInput(pasteText);
        if (body) {
          e.preventDefault();
          if (subject && subjInput) {
            subjInput.value = subject;
          }
          if (bodyInput.selectionStart === 0 && bodyInput.selectionEnd === bodyInput.value.length) {
            bodyInput.value = body;
          } else if (!bodyInput.value.trim()) {
            bodyInput.value = body;
          } else {
            const start = bodyInput.selectionStart;
            const end = bodyInput.selectionEnd;
            const val = bodyInput.value;
            bodyInput.value = val.substring(0, start) + body + val.substring(end);
            bodyInput.selectionStart = bodyInput.selectionEnd = start + body.length;
          }
          onDraftInputChange();
          if (typeof showToast === 'function') {
            showToast('✓ Cleaned & formatted ChatGPT email draft', 'success');
          }
        }
      }
    });
  }

  // Smart paste listener on Subject field (handles pasting whole email into subject input)
  if (subjInput && !subjInput._hasPasteListener) {
    subjInput._hasPasteListener = true;
    subjInput.addEventListener('paste', (e) => {
      const pasteText = (e.clipboardData || window.clipboardData)?.getData('text');
      if (!pasteText) return;

      if (pasteText.includes('\n') && (
        /^(?:\*\*)?Subject(?:\*\*)?:/im.test(pasteText) ||
        /\b(?:Regards|Sincerely|Thanks & Regards|Best|Cheers)[,\s]+/i.test(pasteText) ||
        /^(?:Send|Hi|Dear|Hello)\b/im.test(pasteText)
      ) && typeof parseAndCleanEmailInput === 'function') {
        e.preventDefault();
        const { subject, body } = parseAndCleanEmailInput(pasteText);
        if (subject) {
          subjInput.value = subject;
        }
        if (body && bodyInput) {
          bodyInput.value = body;
        }
        onDraftInputChange();
        if (typeof showToast === 'function') {
          showToast('✓ Split and cleaned email into Subject and Body', 'success');
        }
      }
    });
  }
}

function cleanActiveDraftFields() {
  const subjInput = document.getElementById('draftSubject');
  const bodyInput = document.getElementById('draftBody');
  if (!bodyInput) return;

  const currentSubject = subjInput ? subjInput.value : '';
  const currentBody = bodyInput.value;

  if (typeof parseAndCleanEmailInput !== 'function') return;

  const { subject, body } = parseAndCleanEmailInput(currentBody);
  let changed = false;

  if (subject && subjInput && (!currentSubject || !currentSubject.trim())) {
    subjInput.value = subject;
    changed = true;
  }
  if (body && body !== currentBody) {
    bodyInput.value = body;
    changed = true;
  }

  if (changed) {
    onDraftInputChange();
    if (typeof showToast === 'function') {
      showToast('✓ Cleaned ChatGPT artifacts & trimmed signature extras', 'success');
    }
  } else {
    if (typeof showToast === 'function') {
      showToast('Draft is already clean', 'info');
    }
  }
}

// Global Esc key listener to dismiss side drawer
window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const drawer = document.getElementById('reviewEmailDrawer');
    if (drawer && !drawer.classList.contains('hidden')) {
      closeReviewEmailDrawer();
    }
  }
});

async function saveActiveDraftEdits(options = {}) {
  const silent = Boolean(options && options.silent);
  if (draftAutoSaveTimer) {
    clearTimeout(draftAutoSaveTimer);
    draftAutoSaveTimer = null;
  }

  const targetPost = state.activeReviewPost;
  if (!targetPost) return;

  const subject = (document.getElementById('draftSubject')?.value || '').trim();
  const body = (document.getElementById('draftBody')?.value || '').trim();

  updateDraftSaveStatus('saving');

  try {
    const res = await fetch(`/api/posts/${targetPost.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, body }),
    });

    if (res.ok) {
      isDraftDirty = false;
      targetPost.generated_subject = subject;
      targetPost.generated_body = body;

      const match = (state.reviewPosts || []).find((p) => p.id === targetPost.id);
      if (match) {
        match.generated_subject = subject;
        match.generated_body = body;
      }

      updateDraftSaveStatus('saved');
      if (!silent) {
        showToast('✓ Draft changes saved', 'success');
      }
    } else {
      updateDraftSaveStatus('dirty');
      if (!silent) {
        const err = await res.json();
        showAlert('Save Error', err.detail || 'Could not save draft.');
      }
    }
  } catch (err) {
    updateDraftSaveStatus('dirty');
    if (!silent) {
      showAlert('Save Error', err.message);
    }
  }
}

async function generateEmailForActiveDraft() {
  if (!state.activeReviewPost || !state.activePostId) {
    showToast('Please select a post first to generate outreach email.', 'warn');
    return;
  }
  const postId = state.activePostId;
  const author = state.activeReviewPost.author_name || 'the job poster';

  const confirmed = await showConfirm(
    'Generate Outreach Email from JD',
    `This will submit the full job description for "${author}" to ChatGPT and generate a tailored cold outreach email. Proceed?`,
    { confirmText: 'Generate Now' }
  );
  if (!confirmed) return;

  const btn = document.getElementById('btnGenerateMailFromJd');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `
      <svg class="spin-fast" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg>
      <span>Generating...</span>
    `;
  }

  try {
    const res = await fetch(`/api/generate-email/${postId}?force=true`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued email generation (Queue #${data.position})`, 'info');
      } else {
        showToast('ChatGPT email generation launched!', 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail || 'Failed to start email generator.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  } finally {
    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          <span id="btnGenerateMailLabel">Re-generate</span>
        `;
      }
    }, 2500);
  }
}

function toggleSelectDraft(postId) {
  if (state.selectedDraftIds.has(postId)) {
    state.selectedDraftIds.delete(postId);
  } else {
    state.selectedDraftIds.add(postId);
  }
  updateSelectedDraftsUI();
}

function toggleSelectAllDrafts(checked) {
  if (checked) {
    state.reviewPosts.forEach((p) => state.selectedDraftIds.add(p.id));
  } else {
    state.selectedDraftIds.clear();
  }
  updateSelectedDraftsUI();
}

function updateSelectedDraftsUI() {
  const count = state.selectedDraftIds.size;
  const countEl = document.getElementById('selectedDraftsCount');
  const countCancelEl = document.getElementById('selectedDraftsCancelCount');
  const countGenEl = document.getElementById('selectedDraftsGenCount');
  const btnBatch = document.getElementById('btnSendBatchDrafts');
  const btnCancelBatch = document.getElementById('btnCancelBatchDrafts');
  const btnGenBatch = document.getElementById('btnGenerateBatchDrafts');
  const checkAll = document.getElementById('selectAllDraftsCheckbox');

  if (countEl) countEl.textContent = String(count);
  if (countCancelEl) countCancelEl.textContent = String(count);
  if (countGenEl) countGenEl.textContent = String(count);
  if (btnBatch) btnBatch.classList.toggle('hidden', count === 0);
  if (btnCancelBatch) btnCancelBatch.classList.toggle('hidden', count === 0);
  if (btnGenBatch) btnGenBatch.classList.toggle('hidden', count === 0);

  if (checkAll) {
    checkAll.checked = state.reviewPosts.length > 0 && count === state.reviewPosts.length;
    checkAll.indeterminate = count > 0 && count < state.reviewPosts.length;
  }

  document.querySelectorAll('.draft-checkbox').forEach((cb) => {
    cb.checked = state.selectedDraftIds.has(cb.value);
    const row = cb.closest('tr');
    if (row) row.classList.toggle('selected', state.selectedDraftIds.has(cb.value));
  });
}

function formatCooldownWait(waitSeconds) {
  const total = Math.max(0, Math.floor(waitSeconds || 0));
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (d > 0) return `${d} day${d !== 1 ? 's' : ''} ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${Math.max(m, 1)} minute${m !== 1 ? 's' : ''}`;
}

async function preflightSendCooldown(postIds) {
  try {
    const res = await fetch('/api/send-preflight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: postIds }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

function showCooldownDialog(blocked, cooldownDays) {
  const lines = blocked.map(
    (b) => `• ${b.email} — already sent, wait ${formatCooldownWait(b.wait_seconds)} to send again`
  );
  showCenterAlert(
    'Already Sent Recently',
    `An application email was already sent to ${blocked.length === 1 ? 'this recipient' : 'these recipients'} within the last ${cooldownDays} days:\n\n${lines.join('\n')}\n\nPlease wait for the cooldown to finish before sending again.`,
    { danger: true, confirmText: 'Got it' }
  );
}

async function sendActiveDraftDirectly() {
  if (!state.activeReviewPost) return;

  const cooldown = await preflightSendCooldown([state.activeReviewPost.id]);
  if (cooldown && cooldown.blocked && cooldown.blocked.length > 0) {
    showCooldownDialog(cooldown.blocked, cooldown.cooldown_days || 3);
    return;
  }

  const recipient = (state.activeReviewPost.contact_emails && state.activeReviewPost.contact_emails[0]) || state.activeReviewPost.author_name;
  const confirmed = await showConfirm(
    'Direct Send Application',
    `Send application email directly to ${recipient} via Gmail without manual interaction? Your active resume will be attached and this post will be moved to Sent history.`,
    { confirmText: 'Send Directly' }
  );
  if (!confirmed) return;

  await saveActiveDraftEdits();

  try {
    const res = await fetch(`/api/send-direct/${state.activeReviewPost.id}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued direct send (Position #${data.position})`, 'info');
      } else {
        showToast('Sending email directly via Gmail...', 'info');
      }
      state.selectedDraftIds.delete(state.activeReviewPost.id);
      updateSelectedDraftsUI();
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      if (res.status === 409) {
        showCenterAlert('Already Sent Recently', err.detail || 'This recipient was emailed recently.', { danger: true, confirmText: 'Got it' });
      } else {
        showAlert('Send Direct Error', err.detail || 'Cannot send email directly.');
      }
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function sendBatchSelectedDrafts() {
  const ids = Array.from(state.selectedDraftIds);
  if (ids.length === 0) {
    showToast('Please select at least one draft to send.', 'warn');
    return;
  }

  let sendIds = ids;
  const cooldown = await preflightSendCooldown(ids);
  if (cooldown && cooldown.blocked && cooldown.blocked.length > 0) {
    const days = cooldown.cooldown_days || 3;
    if (!cooldown.allowed || cooldown.allowed.length === 0) {
      showCooldownDialog(cooldown.blocked, days);
      return;
    }
    const lines = cooldown.blocked.map(
      (b) => `• ${b.email} — wait ${formatCooldownWait(b.wait_seconds)}`
    );
    const proceed = await showConfirm(
      'Some Recipients Recently Emailed',
      `${cooldown.blocked.length} of ${ids.length} selected recipients were already emailed within the last ${days} days:\n\n${lines.join('\n')}\n\nSend to the remaining ${cooldown.allowed.length} recipient(s) only?`,
      { confirmText: `Send ${cooldown.allowed.length} Remaining` }
    );
    if (!proceed) return;
    sendIds = cooldown.allowed;
    cooldown.blocked.forEach((b) => state.selectedDraftIds.delete(b.post_id));
    updateSelectedDraftsUI();
  }

  const confirmed = await showConfirm(
    'Batch Direct Send',
    `Send ${sendIds.length} selected applications directly via Gmail in a single browser session? Each recipient will be emailed and attached your resume sequentially.`,
    { confirmText: `Send ${sendIds.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/send-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: sendIds }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued batch send for ${sendIds.length} emails (Position #${data.position})`, 'info');
      } else {
        showToast(`Dispatched batch send task for ${sendIds.length} emails. Monitor progress in live widget.`, 'info');
      }
      state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      if (res.status === 409) {
        showCenterAlert('Already Sent Recently', err.detail || 'Selected recipients were emailed recently.', { danger: true, confirmText: 'Got it' });
      } else {
        showAlert('Batch Send Error', err.detail || 'Cannot initiate batch send.');
      }
    }
  } catch (err) {
    showAlert('Error', err.message);
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
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued Gmail draft opening (Position #${data.position})`, 'info');
      } else {
        showToast('Launching Gmail compose in headed Firefox...', 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
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
        closeReviewEmailDrawer();
      }
      await fetchReviewPosts();
      if (typeof loadDashboardData === 'function') loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Failed to mark as sent.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function markActivePostSpam() {
  if (!state.activeReviewPost) return;
  openCancelReasonModal(state.activeReviewPost.id, state.activeReviewPost.author_name, 'Scam: Suspicious contact or recruitment fraud', true);
}

function cancelActiveApplication() {
  if (!state.activeReviewPost) return;
  openCancelReasonModal(state.activeReviewPost.id, state.activeReviewPost.author_name, '', false);
}

async function generateBatchSelectedDrafts() {
  const ids = Array.from(state.selectedDraftIds || []);
  if (ids.length === 0) {
    showToast('Please select at least one draft to generate.', 'warn');
    return;
  }

  const confirmed = await showConfirm(
    'Batch Generate Outreach Emails',
    `Generate or re-generate tailored outreach emails for ${ids.length} selected post${ids.length === 1 ? '' : 's'} using ChatGPT?`,
    { confirmText: `Generate ${ids.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/generate-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids, force: true }),
    });

    if (res.ok) {
      const data = await res.json();
      state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      if (data.queued) {
        showToast(`Enqueued batch generation for ${ids.length} posts (Position #${data.position})`, 'info');
      } else {
        showToast(`Batch generation started for ${ids.length} posts`, 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail || 'Failed to start batch generation.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function quickGenerateAllReviewDrafts() {
  let ids = Array.from(state.selectedDraftIds || []);
  if (ids.length === 0) {
    ids = (state.reviewPosts || []).map((p) => p.id);
  }
  if (ids.length === 0) {
    showToast('No drafts available in the queue to generate.', 'warn');
    return;
  }

  const label = state.selectedDraftIds && state.selectedDraftIds.size > 0
    ? `${ids.length} selected draft${ids.length === 1 ? '' : 's'}`
    : `all ${ids.length} ready draft${ids.length === 1 ? '' : 's'} in the review queue`;

  const confirmed = await showConfirm(
    'Bulk Email Generation',
    `Submit ${label} to ChatGPT for automated outreach email generation in headed Firefox?`,
    { confirmText: `Generate ${ids.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/generate-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids, force: true }),
    });

    if (res.ok) {
      const data = await res.json();
      if (state.selectedDraftIds) state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      if (data.queued) {
        showToast(`Enqueued batch generation for ${ids.length} posts (Position #${data.position})`, 'info');
      } else {
        showToast(`Batch generation started for ${ids.length} posts`, 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail || 'Failed to start batch generation.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function cancelBatchSelectedDrafts() {
  const count = state.selectedDraftIds ? state.selectedDraftIds.size : 0;
  if (count === 0) return;

  state.pendingCancelPostIds = Array.from(state.selectedDraftIds);
  state.pendingCancelPostId = null;
  state.pendingCancelSource = 'review';
  state.isSpamCancelMode = false;

  const titleEl = document.getElementById('cancelModalTitle');
  if (titleEl) {
    titleEl.textContent = `Cancel ${count} Applications`;
  }

  const descEl = document.getElementById('cancelModalDesc');
  if (descEl) {
    descEl.innerHTML = `Select a ready suggestion below or type a custom comment. All <strong>${count} selected applications</strong> will be moved to your <strong>Others</strong> history.`;
  }

  const checkAddToDismissed = document.getElementById('checkAddToDismissedRoles');
  if (checkAddToDismissed) checkAddToDismissed.checked = false;

  const btnPostOnly = document.getElementById('btnDismissPostOnly');
  if (btnPostOnly) {
    btnPostOnly.textContent = `Dismiss ${count} Application${count === 1 ? '' : 's'} Only`;
  }
  const btnBlacklist = document.getElementById('btnDismissAndBlacklist');
  if (btnBlacklist) {
    btnBlacklist.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg><span>🚫 Dismiss & Add Roles (${count})</span>`;
  }

  const nameEl = document.getElementById('cancelModalCandidate');
  if (nameEl) nameEl.textContent = `for ${count} selected drafts`;

  const input = document.getElementById('inputCancelReason');
  if (input) input.value = '';

  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((c) => {
    c.classList.remove('active');
  });

  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
  }, 50);
}

function openCancelReasonModal(postId, candidateName, defaultReason = '', isSpamMode = false, source = null) {
  state.pendingCancelPostId = postId;
  state.pendingCancelPostIds = [];
  if (source) {
    state.pendingCancelSource = source;
  } else if (!state.pendingCancelSource) {
    state.pendingCancelSource = state.activeTab === 'tabDiscovered' ? 'discovered'
                              : (state.activeTab === 'tabEasyApply' ? 'easy_apply'
                              : (state.activeTab === 'tabIndeedApply' ? 'indeed_apply' : 'review'));
  }
  state.isSpamCancelMode = !!isSpamMode;

  // Uncheck the "Also register role title in Dismissed Roles" checkbox on each open
  const checkAddToDismissed = document.getElementById('checkAddToDismissedRoles');
  if (checkAddToDismissed) checkAddToDismissed.checked = false;

  if (!candidateName && postId) {
    const p = (state.posts || []).find((item) => item.id === postId)
           || (state.reviewPosts || []).find((item) => item.id === postId)
           || (typeof easyApplyPosts !== 'undefined' && Array.isArray(easyApplyPosts) ? easyApplyPosts.find((item) => item.id === postId) : null)
           || (typeof indeedState !== 'undefined' && Array.isArray(indeedState.posts) ? indeedState.posts.find((item) => item.id === postId) : null);
    candidateName = p?.author_headline || p?.author_name || '';
  }

  const titleEl = document.getElementById('cancelModalTitle');
  if (titleEl) {
    titleEl.textContent = 'Dismiss Post';
  }

  const descEl = document.getElementById('cancelModalDesc');
  if (descEl) {
    descEl.innerHTML = 'Select a reason below or type a custom comment. This will be saved to your <strong>Others</strong> history.';
  }

  // Update button labels
  const btnPostOnly = document.getElementById('btnDismissPostOnly');
  if (btnPostOnly) {
    btnPostOnly.textContent = 'Dismiss Only';
  }
  const btnBlacklist = document.getElementById('btnDismissAndBlacklist');
  if (btnBlacklist) {
    btnBlacklist.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg><span>🚫 Dismiss & Add to Dismissed Roles</span>`;
  }

  const nameEl = document.getElementById('cancelModalCandidate');
  if (nameEl) nameEl.textContent = candidateName ? `for ${candidateName}` : '';

  // Default option: "Irrelevant tech stack" unless explicitly provided
  const initialReason = defaultReason || 'Irrelevant tech stack';
  const input = document.getElementById('inputCancelReason');
  if (input) input.value = initialReason;

  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((c) => {
    const chipVal = c.getAttribute('data-reason') || c.textContent.trim();
    c.classList.toggle('active', chipVal.toLowerCase() === initialReason.toLowerCase());
  });

  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
    if (initialReason) input?.select();
  }, 50);
}

function closeCancelReasonModal() {
  state.pendingCancelPostId = null;
  state.pendingCancelPostIds = [];
  state.pendingCancelSource = null;
  state.isSpamCancelMode = false;
  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.add('hidden');
}

function selectPreMadeReason(reason) {
  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = reason;
    input.focus();
  }
  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((chip) => {
    const chipVal = chip.getAttribute('data-reason') || chip.textContent.trim();
    chip.classList.toggle('active', chipVal.toLowerCase() === reason.toLowerCase());
  });
}

async function confirmCancelWithReason(explicitAddToDismissed = null) {
  const source = state.pendingCancelSource || (state.activeTab === 'tabDiscovered' ? 'discovered'
               : (state.activeTab === 'tabEasyApply' ? 'easy_apply'
               : (state.activeTab === 'tabIndeedApply' ? 'indeed_apply' : 'review')));
  const isDiscovered = source === 'discovered';
  const isEasyApply = source === 'easy_apply';
  const isIndeedApply = source === 'indeed_apply';

  // Determine whether to register headline in Dismissed Roles blacklist
  const checkboxVal = document.getElementById('checkAddToDismissedRoles')?.checked || false;
  const addToDismissed = explicitAddToDismissed !== null ? !!explicitAddToDismissed : checkboxVal;

  const input = document.getElementById('inputCancelReason');
  const defaultReason = isDiscovered ? 'Dismissed from Discovered'
                      : (isEasyApply ? 'Dismissed from Easy Apply'
                      : (isIndeedApply ? 'Dismissed from Indeed' : 'Unspecified'));
  const reason = (input?.value || '').trim() || defaultReason;

  // Multi-item bulk cancel handling
  if (state.pendingCancelPostIds && state.pendingCancelPostIds.length > 0) {
    const postIds = state.pendingCancelPostIds;
    try {
      const res = await fetch('/api/posts/reject-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_ids: postIds, reason, add_to_dismissed_roles: addToDismissed }),
      });
      if (res.ok) {
        const data = await res.json();
        const count = data.count || postIds.length;
        closeCancelReasonModal();

        if (isDiscovered) {
          state.selectedIds.clear();
          if (typeof updateSelectedCountUI === 'function') updateSelectedCountUI();
          if (typeof fetchDiscoveredPosts === 'function') await fetchDiscoveredPosts();
          if (state.activeDiscoveredPostId && postIds.includes(state.activeDiscoveredPostId)) {
            if (state.posts && state.posts.length > 0) {
              openDiscoveredDetailDrawer(state.posts[0].id);
            } else {
              closeDiscoveredDetailDrawer();
            }
          }
        } else if (isEasyApply) {
          if (typeof selectedEasyJobIds !== 'undefined') {
            selectedEasyJobIds.clear();
          }
          if (typeof updateEasyKPIs === 'function') updateEasyKPIs();
          if (typeof fetchEasyApplyPosts === 'function') await fetchEasyApplyPosts();
        } else if (isIndeedApply) {
          if (typeof clearIndeedSelection === 'function') {
            clearIndeedSelection();
          }
          if (typeof fetchIndeedApplyPosts === 'function') await fetchIndeedApplyPosts();
        } else {
          state.selectedDraftIds.clear();
          if (typeof updateSelectedDraftsUI === 'function') updateSelectedDraftsUI();
          await fetchReviewPosts();
        }

        if (typeof fetchSentPosts === 'function') await fetchSentPosts();
        if (typeof loadDashboardData === 'function') loadDashboardData();
        if (addToDismissed && typeof loadDismissedRolesPage === 'function' && state.activeTab === 'tabDismissedRoles') {
          loadDismissedRolesPage();
        }

        const undoAction = {
          label: 'Undo',
          payload: { post_ids: postIds, target_status: isDiscovered ? 'DISCOVERED' : 'EMAIL_GENERATED' },
          onClick: async () => {
            try {
              const revRes = await fetch('/api/posts/revert-batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ post_ids: postIds }),
              });
              if (revRes.ok) {
                showToast(`✓ Restored ${count} ${isDiscovered ? 'post(s)' : 'item(s)'}`, 'success');
                if (isDiscovered) {
                  if (typeof fetchDiscoveredPosts === 'function') await fetchDiscoveredPosts();
                } else if (isEasyApply) {
                  if (typeof fetchEasyApplyPosts === 'function') await fetchEasyApplyPosts();
                } else if (isIndeedApply) {
                  if (typeof fetchIndeedApplyPosts === 'function') await fetchIndeedApplyPosts();
                } else {
                  await fetchReviewPosts();
                }
                if (typeof fetchSentPosts === 'function') await fetchSentPosts();
                if (typeof loadDashboardData === 'function') loadDashboardData();
              }
            } catch (e) {
              showToast('Error restoring: ' + e.message, 'error');
            }
          },
        };

        const itemLabel = isDiscovered ? 'post' : (isEasyApply || isIndeedApply ? 'job' : 'application');
        const notifTitle = isDiscovered ? 'Posts Dismissed'
                         : (isEasyApply ? 'Easy Apply Jobs Dismissed'
                         : (isIndeedApply ? 'Indeed Jobs Dismissed' : 'Applications Cancelled'));
        const blacklistNotice = addToDismissed ? ' (Roles added to Dismissed Roles)' : '';
        const notifMsg = `Dismissed ${count} ${itemLabel}${count === 1 ? '' : 's'}: ${reason}${blacklistNotice}`;

        if (typeof sendAppNotification === 'function') {
          sendAppNotification({
            title: notifTitle,
            message: notifMsg,
            type: 'warn',
            action: undoAction,
          });
        }
        if (typeof showSnackbar === 'function') {
          showSnackbar({
            title: notifTitle,
            message: notifMsg,
            type: 'warn',
            duration: 14000,
            action: undoAction,
          });
        } else {
          showToast(`✕ ${notifMsg}`, 'info');
        }
      } else {
        const err = await res.json();
        showAlert('Error', err.detail || 'Could not cancel applications.');
      }
    } catch (err) {
      showAlert('Error', err.message);
    }
    return;
  }

  const postId = state.pendingCancelPostId;
  if (!postId) return;

  // IMPORTANT: Capture active state and position index BEFORE any network calls or re-fetching
  const prevDiscoveredIndex = isDiscovered && postId ? (state.posts || []).findIndex((p) => p.id === postId) : -1;
  const wasActiveInDrawer = isDiscovered && postId && state.activeDiscoveredPostId === postId;

  const prevReviewIndex = !isDiscovered && !isEasyApply && !isIndeedApply && postId
    ? (state.reviewPosts || []).findIndex((p) => p.id === postId) : -1;
  const wasActiveReview = !isDiscovered && !isEasyApply && !isIndeedApply && postId
    && state.activeReviewPost && state.activeReviewPost.id === postId;

  try {
    const endpoint = (reason.toLowerCase() === 'scam' || reason.toLowerCase().includes('spam'))
      ? `/api/posts/${postId}/spam`
      : `/api/posts/${postId}/reject`;

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason, add_to_dismissed_roles: addToDismissed }),
    });
    if (res.ok) {
      closeCancelReasonModal();
      await loadDashboardData();

      if (isDiscovered) {
        if (state.selectedIds && state.selectedIds.has(postId)) {
          state.selectedIds.delete(postId);
          if (typeof updateSelectedCountUI === 'function') updateSelectedCountUI();
        }

        // If the dismissed post was currently shown in the window, show the NEXT row
        if (wasActiveInDrawer) {
          if (state.posts && state.posts.length > 0) {
            const nextIdx = (prevDiscoveredIndex >= 0 && prevDiscoveredIndex < state.posts.length)
              ? prevDiscoveredIndex
              : state.posts.length - 1;
            const nextPost = state.posts[nextIdx];
            if (nextPost) {
              openDiscoveredDetailDrawer(nextPost.id);
            } else {
              closeDiscoveredDetailDrawer();
            }
          } else {
            closeDiscoveredDetailDrawer();
          }
        }
        if (typeof fetchDiscoveredPosts === 'function') await fetchDiscoveredPosts();
      } else if (isEasyApply) {
        if (typeof selectedEasyJobIds !== 'undefined') {
          selectedEasyJobIds.delete(postId);
        }
        if (typeof updateEasyKPIs === 'function') updateEasyKPIs();
        if (typeof fetchEasyApplyPosts === 'function') await fetchEasyApplyPosts();
      } else if (isIndeedApply) {
        if (typeof indeedState !== 'undefined' && indeedState.selectedIds) {
          indeedState.selectedIds.delete(postId);
        }
        if (typeof fetchIndeedApplyPosts === 'function') await fetchIndeedApplyPosts();
      } else {
        // Review drafts workspace
        if (wasActiveReview) {
          if (state.reviewPosts && state.reviewPosts.length > 0) {
            const nextIdx = (prevReviewIndex >= 0 && prevReviewIndex < state.reviewPosts.length)
              ? prevReviewIndex
              : state.reviewPosts.length - 1;
            const nextReviewPost = state.reviewPosts[nextIdx];
            if (nextReviewPost) {
              openReviewDraftDrawer(nextReviewPost.id);
            } else {
              closeReviewEmailDrawer();
            }
          } else {
            closeReviewEmailDrawer();
          }
        }
        await fetchReviewPosts();
      }

      if (typeof fetchSentPosts === 'function') await fetchSentPosts();
      if (addToDismissed && typeof loadDismissedRolesPage === 'function' && state.activeTab === 'tabDismissedRoles') {
        loadDismissedRolesPage();
      }

      const undoAction = {
        label: 'Undo',
        payload: { post_ids: [postId], target_status: isDiscovered ? 'DISCOVERED' : 'EMAIL_GENERATED' },
        onClick: async () => {
          try {
            const revRes = await fetch(`/api/posts/${postId}/revert`, { method: 'POST' });
            if (revRes.ok) {
              showToast(`✓ Restored ${isDiscovered ? 'post' : 'item'}`, 'success');
              if (isDiscovered) {
                if (typeof fetchDiscoveredPosts === 'function') await fetchDiscoveredPosts();
              } else if (isEasyApply) {
                if (typeof fetchEasyApplyPosts === 'function') await fetchEasyApplyPosts();
              } else if (isIndeedApply) {
                if (typeof fetchIndeedApplyPosts === 'function') await fetchIndeedApplyPosts();
              } else {
                await fetchReviewPosts();
                await openReviewDraftDrawer(postId);
              }
              if (typeof fetchSentPosts === 'function') await fetchSentPosts();
              if (typeof loadDashboardData === 'function') loadDashboardData();
            }
          } catch (e) {
            showToast('Error restoring: ' + e.message, 'error');
          }
        },
      };

      const itemLabel = isDiscovered ? 'post' : (isEasyApply || isIndeedApply ? 'job' : 'application');
      const notifTitle = isDiscovered ? 'Post Dismissed'
                       : (isEasyApply ? 'Easy Apply Job Dismissed'
                       : (isIndeedApply ? 'Indeed Job Dismissed' : 'Application Cancelled'));
      const blacklistNotice = addToDismissed ? ' (Role added to Dismissed Roles)' : '';
      const notifMsg = `Dismissed ${itemLabel}: ${reason}${blacklistNotice}`;

      if (typeof sendAppNotification === 'function') {
        sendAppNotification({
          title: notifTitle,
          message: notifMsg,
          type: 'warn',
          action: undoAction,
        });
      }
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: notifTitle,
          message: notifMsg,
          type: 'warn',
          duration: 12000,
          action: undoAction,
        });
      } else {
        showToast(`✕ ${notifMsg}`, 'info');
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

function copyDraftSubject() {
  const subj = document.getElementById('draftSubject')?.value || '';
  if (!subj) {
    showToast('Subject line is empty', 'warn');
    return;
  }
  navigator.clipboard.writeText(subj).then(() => {
    showToast('✓ Subject copied to clipboard', 'success');
  }).catch(() => {
    showToast('Could not copy to clipboard', 'error');
  });
}

function copyTargetEmail() {
  const email = document.getElementById('reviewTargetEmail')?.textContent || '';
  if (!email || email === 'No email detected') {
    showToast('No recipient email available', 'warn');
    return;
  }
  navigator.clipboard.writeText(email).then(() => {
    showToast(`✓ Copied email: ${email}`, 'success');
  }).catch(() => {
    showToast('Could not copy to clipboard', 'error');
  });
}

// Mail Return Prompt
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

async function selectReviewPostById(postId) {
  if (!postId) return;
  await openReviewDraftDrawer(postId);
}

// Global Bindings
window.handleSearchReview = handleSearchReview;
window.applyReviewDateFilter = applyReviewDateFilter;
window.applyReviewSourceFilter = applyReviewSourceFilter;
window.setReviewFilter = setReviewFilter;
window.clearReviewFilters = clearReviewFilters;
window.fetchReviewPosts = fetchReviewPosts;
window.selectReviewPost = selectReviewPost;
window.selectReviewPostById = selectReviewPostById;
window.openPostInReview = openPostInReview;
window.openReviewDraftDrawer = openReviewDraftDrawer;
window.closeReviewEmailDrawer = closeReviewEmailDrawer;
window.saveActiveDraftEdits = saveActiveDraftEdits;
window.generateEmailForActiveDraft = generateEmailForActiveDraft;
window.triggerGenerateSingleReviewPost = triggerGenerateSingleReviewPost;
window.toggleSelectDraft = toggleSelectDraft;
window.toggleSelectAllDrafts = toggleSelectAllDrafts;
window.updateSelectedDraftsUI = updateSelectedDraftsUI;
window.sendActiveDraftDirectly = sendActiveDraftDirectly;
window.sendBatchSelectedDrafts = sendBatchSelectedDrafts;
window.generateBatchSelectedDrafts = generateBatchSelectedDrafts;
window.quickGenerateAllReviewDrafts = quickGenerateAllReviewDrafts;
window.openActivePostInGmail = openActivePostInGmail;
window.markActivePostSent = markActivePostSent;
window.markActivePostSpam = markActivePostSpam;
window.markPostSentById = markPostSentById;
window.cancelActiveApplication = cancelActiveApplication;
window.cancelBatchSelectedDrafts = cancelBatchSelectedDrafts;
window.openCancelReasonModal = openCancelReasonModal;
window.closeCancelReasonModal = closeCancelReasonModal;
window.selectPreMadeReason = selectPreMadeReason;
window.confirmCancelWithReason = confirmCancelWithReason;
window.rejectActivePost = rejectActivePost;
window.changeReviewPage = changeReviewPage;
window.changeReviewRowsPerPage = changeReviewRowsPerPage;
window.updateReviewPaginationUI = updateReviewPaginationUI;
window.copyDraftSubject = copyDraftSubject;
window.copyTargetEmail = copyTargetEmail;
window.cleanActiveDraftFields = cleanActiveDraftFields;
