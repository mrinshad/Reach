/**
 * Reach — Review & Drafts Workspace, AI Editor, Gmail Dispatch & Candidate Queue
 * (src/static/js/review.js)
 */

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
  if (!container) return;
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

    const queueCountEl = document.getElementById('reviewQueueCount');
    if (queueCountEl) queueCountEl.textContent = String(state.reviewPosts.length);
    const countReviewEl = document.getElementById('countReview');
    if (countReviewEl) countReviewEl.textContent = String(state.reviewPosts.length);
    container.innerHTML = '';

    if (state.reviewPosts.length === 0) {
      state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      const emptyMsg = state.searchReview
        ? `No drafts matching "${escapeHtml(state.searchReview)}" found.`
        : 'No emails generated yet. Generate emails or click Move to Review on Discovered Posts!';
      container.innerHTML = `<div style="text-align: center; padding: 2rem; font-size: 0.78rem; color: #64748b;">${emptyMsg}</div>`;
      const emptyStateEl = document.getElementById('emptyReviewState');
      if (emptyStateEl) emptyStateEl.classList.remove('hidden');
      const wsPanel = document.getElementById('workspacePanel');
      if (wsPanel) wsPanel.classList.add('hidden');
      return;
    }

    state.reviewPosts.forEach((post) => {
      const item = document.createElement('div');
      item.className = 'queue-item' + (state.activeReviewPost && state.activeReviewPost.id === post.id ? ' active' : '');
      item.id = `queue-item-${post.id}`;
      item.onclick = (e) => {
        if (e.target.closest('.draft-checkbox')) return;
        selectReviewPost(post);
      };

      const email = (post.contact_emails && post.contact_emails[0]) || 'No email';
      const isChecked = state.selectedDraftIds.has(post.id);

      item.innerHTML = `
        <div class="queue-item-inner">
          <input type="checkbox" class="draft-checkbox" value="${post.id}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelectDraft('${post.id}')" title="Select for batch send" />
          <div class="queue-item-content">
            <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
              <span class="queue-author">${escapeHtml(post.author_name)}</span>
              ${getSourceBadgeHtml(post)}
              ${post.location ? `<span class="pill-badge badge-location" style="font-size: 0.66rem; padding: 0.1rem 0.35rem; display: inline-flex; align-items: center; gap: 0.2rem;" title="Location: ${escapeHtml(post.location)}"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>${escapeHtml(post.location)}</span>` : ''}
            </div>
            <span class="queue-email" style="display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>${escapeHtml(email)}</span>
          </div>
        </div>
      `;

      container.appendChild(item);
    });

    updateSelectedDraftsUI();

    if (!state.activeReviewPost && state.reviewPosts.length > 0) {
      selectReviewPost(state.reviewPosts[0]);
    } else if (state.activeReviewPost) {
      const exists = state.reviewPosts.find((p) => p.id === state.activeReviewPost.id);
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

  const emptyEl = document.getElementById('emptyReviewState');
  if (emptyEl) emptyEl.classList.add('hidden');
  const wsEl = document.getElementById('workspacePanel');
  if (wsEl) wsEl.classList.remove('hidden');

  const authorEl = document.getElementById('reviewAuthorName');
  if (authorEl) {
    authorEl.innerHTML = `${escapeHtml(post.author_name)} ${getSourceBadgeHtml(post)} ${post.location ? `<span class="pill-badge badge-location" title="Location: ${escapeHtml(post.location)}">📍 ${escapeHtml(post.location)}</span>` : ''}`;
  }
  const headEl = document.getElementById('reviewHeadline');
  if (headEl) headEl.textContent = post.author_headline || 'N/A';

  const emailEl = document.getElementById('reviewTargetEmail');
  if (emailEl) emailEl.textContent = (post.contact_emails || []).join(', ') || 'None';

  const expLabel = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
  const expEl = document.getElementById('reviewExpPill');
  if (expEl) expEl.textContent = expLabel;

  const fullTextEl = document.getElementById('reviewFullText');
  if (fullTextEl) fullTextEl.textContent = post.full_text;

  const postLink = document.getElementById('reviewPostLink');
  if (postLink) {
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
  }

  const subjEl = document.getElementById('draftSubject');
  if (subjEl) subjEl.value = post.generated_subject || '';

  const bodyEl = document.getElementById('draftBody');
  if (bodyEl) bodyEl.value = post.generated_body || '';

  const resume = state.config.resume_path || '';
  const resFilenameEl = document.getElementById('draftResumeFilename');
  if (resFilenameEl) resFilenameEl.textContent = resume.split('/').pop() || 'None';
}

async function openPostInReview(postId) {
  switchTab('tabReview');
  let post = state.reviewPosts.find((p) => p.id === postId) || state.posts.find((p) => p.id === postId);
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

  const subject = (document.getElementById('draftSubject')?.value || '').trim();
  const body = (document.getElementById('draftBody')?.value || '').trim();

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

async function generateEmailForActiveDraft() {
  if (!state.activeReviewPost || !state.activePostId) {
    showToast('Please select a job post from the left queue to generate outreach email.', 'warn');
    return;
  }
  const postId = state.activePostId;
  const author = state.activeReviewPost.author_name || 'the job poster';

  const confirmed = await showConfirm(
    'Generate Outreach Email from JD',
    `This will submit the full job description for "${author}" to ChatGPT and generate a tailored cold outreach subject & body, replacing the current draft. Proceed?`,
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
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 0.25rem;"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          <span>Generate Mail from JD</span>
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
  if (btnBatch) {
    btnBatch.classList.toggle('hidden', count === 0);
  }
  if (btnCancelBatch) {
    btnCancelBatch.classList.toggle('hidden', count === 0);
  }
  if (btnGenBatch) {
    btnGenBatch.classList.toggle('hidden', count === 0);
  }
  if (checkAll) {
    checkAll.checked = state.reviewPosts.length > 0 && count === state.reviewPosts.length;
    checkAll.indeterminate = count > 0 && count < state.reviewPosts.length;
  }

  document.querySelectorAll('.draft-checkbox').forEach((cb) => {
    cb.checked = state.selectedDraftIds.has(cb.value);
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
  state.isSpamCancelMode = false;

  const titleEl = document.getElementById('cancelModalTitle');
  if (titleEl) {
    titleEl.textContent = `Cancel ${count} Applications`;
  }

  const descEl = document.getElementById('cancelModalDesc');
  if (descEl) {
    descEl.innerHTML = `Select a ready suggestion below or type a custom comment. All <strong>${count} selected applications</strong> will be moved to your <strong>Others</strong> history.`;
  }

  const btnConfirm = document.getElementById('btnConfirmCancelModal');
  if (btnConfirm) {
    btnConfirm.textContent = `✕ Cancel ${count} Applications`;
  }

  const nameEl = document.getElementById('cancelModalCandidate');
  if (nameEl) nameEl.textContent = `for ${count} selected drafts`;

  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = '';
  }

  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((c) => {
    c.classList.remove('active');
  });

  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
  }, 50);
}

function openCancelReasonModal(postId, candidateName, defaultReason = '', isSpamMode = false) {
  state.pendingCancelPostId = postId;
  state.pendingCancelPostIds = [];
  state.isSpamCancelMode = !!isSpamMode;

  if (!candidateName) {
    const p = (state.posts || []).find((item) => item.id === postId)
           || (state.reviewPosts || []).find((item) => item.id === postId);
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

  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach((c) => {
    const chipVal = c.getAttribute('data-reason') || c.textContent.trim();
    c.classList.toggle('active', !!(defaultReason && chipVal.toLowerCase() === defaultReason.toLowerCase()));
  });

  const modal = document.getElementById('cancelReasonModal');
  if (modal) modal.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
    if (defaultReason) input?.select();
  }, 50);
}

function closeCancelReasonModal() {
  state.pendingCancelPostId = null;
  state.pendingCancelPostIds = [];
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

async function confirmCancelWithReason() {
  const input = document.getElementById('inputCancelReason');
  const reason = (input?.value || '').trim() || (state.isSpamCancelMode ? 'Scam' : 'Unspecified');

  // Multi-item bulk cancel handling
  if (state.pendingCancelPostIds && state.pendingCancelPostIds.length > 0) {
    const postIds = state.pendingCancelPostIds;
    try {
      const res = await fetch('/api/posts/reject-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_ids: postIds, reason }),
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`✕ Cancelled ${data.count || postIds.length} applications: ${reason}`, 'info');
        closeCancelReasonModal();
        state.selectedDraftIds.clear();
        updateSelectedDraftsUI();
        await fetchReviewPosts();
        await fetchSentPosts();
        if (typeof loadDashboardData === 'function') loadDashboardData();
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

  try {
    const endpoint = (state.isSpamCancelMode || reason.toLowerCase() === 'scam' || reason.toLowerCase().includes('spam'))
      ? `/api/posts/${postId}/spam`
      : `/api/posts/${postId}/reject`;

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (res.ok) {
      showToast(`✕ Application cancelled: ${reason}`, 'info');
      closeCancelReasonModal();
      if (state.activeReviewPost && state.activeReviewPost.id === postId) {
        state.activeReviewPost = null;
      }
      await loadDashboardData();

      if (state.activeTab === 'tabReview' || (state.reviewPosts && state.reviewPosts.length > 0)) {
        const remaining = state.reviewPosts.filter((p) => p.id !== postId);
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

// Global Bindings
window.handleSearchReview = handleSearchReview;
window.fetchReviewPosts = fetchReviewPosts;
window.selectReviewPost = selectReviewPost;
window.openPostInReview = openPostInReview;
window.saveActiveDraftEdits = saveActiveDraftEdits;
window.generateEmailForActiveDraft = generateEmailForActiveDraft;
window.toggleSelectDraft = toggleSelectDraft;
window.toggleSelectAllDrafts = toggleSelectAllDrafts;
window.updateSelectedDraftsUI = updateSelectedDraftsUI;
window.sendActiveDraftDirectly = sendActiveDraftDirectly;
window.sendBatchSelectedDrafts = sendBatchSelectedDrafts;
window.generateBatchSelectedDrafts = generateBatchSelectedDrafts;
window.quickGenerateAllReviewDrafts = quickGenerateAllReviewDrafts;
window.openActivePostInGmail = openActivePostInGmail;
window.markActivePostSent = markActivePostSent;
window.markPostSentById = markPostSentById;
window.cancelActiveApplication = cancelActiveApplication;
window.cancelBatchSelectedDrafts = cancelBatchSelectedDrafts;
window.openCancelReasonModal = openCancelReasonModal;
window.closeCancelReasonModal = closeCancelReasonModal;
window.selectPreMadeReason = selectPreMadeReason;
window.confirmCancelWithReason = confirmCancelWithReason;
window.rejectActivePost = rejectActivePost;
