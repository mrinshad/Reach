/**
 * Reach — Modal Dialogs (Post Details, Add Manual JD, Direct Outreach & Settings)
 * (src/static/js/modals.js)
 */

function openPostModal(postId) {
  state.currentModalPostId = postId;
  const post = (state.posts && state.posts.find((p) => p.id === postId)) ||
               (state.reviewPosts && state.reviewPosts.find((p) => p.id === postId)) ||
               (state.sentPosts && state.sentPosts.find((p) => p.id === postId));
  if (!post) return;

  const modalSpamBtn = document.getElementById('modalPostSpamBtn');
  if (modalSpamBtn) {
    if (post.status !== 'REJECTED' && post.status !== 'SENT') {
      modalSpamBtn.classList.remove('hidden');
    } else {
      modalSpamBtn.classList.add('hidden');
    }
  }

  const postUrl = post.post_url || '';
  let sourceBadge = 'LinkedIn';
  if (postUrl.includes('infopark.in')) sourceBadge = 'Infopark Kochi';
  else if (postUrl.startsWith('manual://') || postUrl.includes('manual')) sourceBadge = 'Manual JD';

  const authorBadgeHtml = typeof getSourceBadgeHtml === 'function' ? getSourceBadgeHtml(post) : '';
  const authorEl = document.getElementById('modalPostAuthor');
  if (authorEl) {
    authorEl.innerHTML = `${escapeHtml(post.author_name)} <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted);">— [${escapeHtml(sourceBadge)}]</span> ${authorBadgeHtml}`;
  }
  const metaEl = document.getElementById('modalPostMeta');
  if (metaEl) {
    const email = (post.contact_emails && post.contact_emails[0]) ? `Email: ${post.contact_emails[0]}` : 'No email detected';
    const exp = post.raw_experience ? ` • Exp: ${post.raw_experience}` : '';
    const loc = post.location ? ` • 📍 Location: ${post.location}` : '';
    metaEl.textContent = `${email}${exp}${loc}`;
  }

  // Status Banner
  const bannerEl = document.getElementById('modalPostStatusBanner');
  const restoreBtn = document.getElementById('modalPostRestoreBtn');
  if (bannerEl) {
    const isScam = (post.rejection_reason && (post.rejection_reason.toLowerCase().includes('scam') || post.rejection_reason.toLowerCase().includes('spam')));
    const isPotential = post.is_potential_spam || (post.rejection_reason && post.rejection_reason.toLowerCase().includes('potential'));

    if (isScam) {
      bannerEl.className = '';
      bannerEl.innerHTML = `
        <div class="modal-scam-box">
          <div class="modal-scam-box-title" style="display: flex; align-items: center; gap: 0.4rem;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>
            <span>Recruiter Flagged as Scam / Spam</span>
          </div>
          <div class="modal-scam-box-desc">
            <span style="font-weight: 700; color: #ffffff;">Why:</span> ${escapeHtml(post.rejection_reason || 'Marked as scam recruiter')}
          </div>
        </div>
      `;
    } else if (isPotential) {
      bannerEl.className = '';
      const whyText = post.potential_spam_reason || post.rejection_reason || 'Suspicious contact domain or flagged recruiter activity';
      bannerEl.innerHTML = `
        <div class="modal-potential-scam-box">
          <div class="modal-potential-scam-box-title" style="display: flex; align-items: center; gap: 0.4rem;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <span>Warning: Recruiter Flagged as Potential Scam</span>
          </div>
          <div class="modal-potential-scam-box-desc">
            <span style="font-weight: 700; color: #ffffff;">Why:</span> ${escapeHtml(whyText)}
          </div>
        </div>
      `;
    } else if (post.status === 'REJECTED') {
      bannerEl.className = '';
      bannerEl.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; padding: 0.65rem 0.85rem; color: #f87171; font-size: 0.82rem;">
          <strong style="display: flex; align-items: center; gap: 0.35rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Application Cancelled / Discarded</strong>
          ${post.rejection_reason ? `<div style="margin-top: 0.25rem; color: #fca5a5;"><span style="font-weight: 600; color: #fff;">Why:</span> <strong>${escapeHtml(post.rejection_reason)}</strong></div>` : ''}
        </div>
      `;
    } else if (post.status === 'SENT') {
      bannerEl.className = '';
      const sentTime = post.sent_at ? ` on ${new Date(post.sent_at).toLocaleString()}` : '';
      bannerEl.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 6px; padding: 0.65rem 0.85rem; color: #34d399; font-size: 0.82rem;">
          <strong style="display: flex; align-items: center; gap: 0.35rem;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>Outreach Email Sent${sentTime}</strong>
          ${post.generated_subject ? `<div style="margin-top: 0.25rem; color: #a7f3d0;">Subject: <em>${escapeHtml(post.generated_subject)}</em></div>` : ''}
        </div>
      `;
    } else {
      bannerEl.className = 'hidden';
      bannerEl.innerHTML = '';
    }
  }

  if (restoreBtn) {
    if (post.status === 'SENT' || post.status === 'REJECTED') {
      restoreBtn.classList.remove('hidden');
      restoreBtn.onclick = () => {
        closePostModal();
        if (typeof revertPostToDraft === 'function') revertPostToDraft(post.id);
      };
    } else {
      restoreBtn.classList.add('hidden');
    }
  }

  const linkEl = document.getElementById('modalPostLink');
  if (linkEl) {
    if (post.post_url && !post.post_url.startsWith('manual://') && !post.post_url.startsWith('direct://')) {
      linkEl.href = post.post_url;
      linkEl.style.display = 'inline-flex';
      linkEl.textContent = post.post_url.includes('infopark.in') ? 'View on Infopark ↗' : 'View on LinkedIn ↗';
    } else {
      linkEl.style.display = 'none';
    }
  }
  const contentEl = document.getElementById('modalPostContent');
  if (contentEl) contentEl.textContent = post.full_text;
  const modalEl = document.getElementById('postModal');
  if (modalEl) modalEl.classList.remove('hidden');
}

function closePostModal() {
  const modalEl = document.getElementById('postModal');
  if (modalEl) modalEl.classList.add('hidden');
}

// --- Manual JD Entry Modal ---
function openAddJdModal() {
  const titleInput = document.getElementById('manualJdTitle');
  const compInput = document.getElementById('manualJdCompany');
  const locInput = document.getElementById('manualJdLocation');
  const contInput = document.getElementById('manualJdContent');

  if (titleInput) titleInput.value = '';
  if (compInput) compInput.value = '';
  if (locInput) locInput.value = '';
  if (contInput) contInput.value = '';

  const modalEl = document.getElementById('modalAddJd');
  if (modalEl) modalEl.classList.remove('hidden');
}

function closeAddJdModal() {
  const modalEl = document.getElementById('modalAddJd');
  if (modalEl) modalEl.classList.add('hidden');
}

async function submitManualJd() {
  const content = (document.getElementById('manualJdContent')?.value || '').trim();
  if (!content) {
    showAlert('Missing Content', 'Please paste the job description text.');
    return;
  }
  const title = (document.getElementById('manualJdTitle')?.value || '').trim();
  const company = (document.getElementById('manualJdCompany')?.value || '').trim();
  const location = (document.getElementById('manualJdLocation')?.value || '').trim();

  try {
    const res = await fetch('/api/posts/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title || 'Job Opening',
        company: company || 'Recruiter',
        content: content,
        location: location || null,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      closeAddJdModal();
      showToast(`✓ Added manual JD: ${data.post?.author_name || 'Job Opening'}`, 'success');
      if (typeof loadDashboardData === 'function') loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Could not save manual JD.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Direct Opportunity Outreach Modal ---
function openDirectOutreachModal() {
  const emailInput = document.getElementById('directOutreachEmail');
  const companyInput = document.getElementById('directOutreachCompany');
  const locInput = document.getElementById('directOutreachLocation');
  const subInput = document.getElementById('directOutreachSubject');
  const bodyInput = document.getElementById('directOutreachBody');

  if (emailInput) emailInput.value = '';
  if (companyInput) companyInput.value = '';
  if (locInput) locInput.value = '';
  if (subInput) subInput.value = DEFAULT_OPPORTUNITY_SUBJECT;
  if (bodyInput) bodyInput.value = DEFAULT_OPPORTUNITY_BODY;

  document.getElementById('modalDirectOutreach')?.classList.remove('hidden');
  if (emailInput) emailInput.focus();
}

function closeDirectOutreachModal() {
  document.getElementById('modalDirectOutreach')?.classList.add('hidden');
}

function resetDirectOutreachBody() {
  const subInput = document.getElementById('directOutreachSubject');
  const bodyInput = document.getElementById('directOutreachBody');
  if (subInput) subInput.value = DEFAULT_OPPORTUNITY_SUBJECT;
  if (bodyInput) bodyInput.value = DEFAULT_OPPORTUNITY_BODY;
}

async function submitDirectOutreach(mode = 'send') {
  const email = (document.getElementById('directOutreachEmail')?.value || '').trim();
  if (!email || !email.includes('@')) {
    showAlert('Invalid Recipient', 'Please enter a valid recipient email address.');
    return;
  }

  const company = (document.getElementById('directOutreachCompany')?.value || '').trim();
  const location = (document.getElementById('directOutreachLocation')?.value || '').trim();
  const subject = (document.getElementById('directOutreachSubject')?.value || '').trim() || DEFAULT_OPPORTUNITY_SUBJECT;
  const body = (document.getElementById('directOutreachBody')?.value || '').trim() || DEFAULT_OPPORTUNITY_BODY;

  try {
    const res = await fetch('/api/direct-outreach', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recipient_email: email,
        company_name: company || null,
        location: location || null,
        subject: subject,
        body: body,
        mode: mode,
      }),
    });

    if (res.ok) {
      const data = await res.json();
      closeDirectOutreachModal();
      showToast(data.message || `✓ Outreach dispatched to ${email}`, 'success');
      if (typeof startTaskPolling === 'function') startTaskPolling();
      if (typeof loadDashboardData === 'function') loadDashboardData();
    } else {
      const err = await res.json();
      showAlert('Direct Outreach Error', err.detail || 'Failed to dispatch direct outreach.');
    }
  } catch (err) {
    showAlert('Network Error', err.message);
  }
}

// --- Settings Modal ---
function openSettingsModal() {
  const resPathInput = document.getElementById('settingResumePath');
  if (resPathInput) resPathInput.value = state.config.resume_path || '';

  const queryInput = document.getElementById('settingSearchQuery');
  if (queryInput) queryInput.value = state.config.search_query || '';

  const settingLoc = document.getElementById('settingSearchLocation');
  if (settingLoc) settingLoc.value = state.config.search_location || '';

  const gptUrlInput = document.getElementById('settingChatGptUrl');
  if (gptUrlInput) gptUrlInput.value = state.config.chatgpt_url || '';

  updateHeadlessUI(state.config ? state.config.headless_mode : false);
  document.getElementById('settingsModal')?.classList.remove('hidden');
}

function closeSettingsModal() {
  document.getElementById('settingsModal')?.classList.add('hidden');
}

function closeModal(modalId) {
  const el = typeof modalId === 'string' ? document.getElementById(modalId) : modalId;
  if (el) el.classList.add('hidden');
}

// --- Headless Mode Controls ---
function updateHeadlessUI(isHeadless) {
  const toggleInput = document.getElementById('settingHeadlessToggle');
  if (toggleInput) toggleInput.checked = !!isHeadless;

  const statusTitle = document.getElementById('headlessStatusTitle');
  if (statusTitle) {
    statusTitle.textContent = isHeadless ? 'Headless Mode (Silent Background)' : 'Headed Mode (Visible Window)';
  }

  const statusDesc = document.getElementById('headlessStatusDesc');
  if (statusDesc) {
    statusDesc.textContent = isHeadless
      ? 'Browser runs silently in background. Faster execution and zero window interruptions.'
      : 'Browser opens visibly on screen for monitoring and live inspection.';
  }

  const quickBtn = document.getElementById('btnQuickHeadlessToggle');
  if (quickBtn) {
    quickBtn.classList.toggle('headless-active', !!isHeadless);
    quickBtn.setAttribute('title', isHeadless
      ? 'Headless Active (Click to switch to visible window)'
      : 'Headed Active (Click to switch to silent headless background)');
  }

  const quickLabel = document.getElementById('quickHeadlessLabel');
  if (quickLabel) {
    quickLabel.textContent = isHeadless ? 'Headless' : 'Headed';
  }

  const iconDisplay = document.getElementById('headlessIconDisplay');
  if (iconDisplay) {
    iconDisplay.innerHTML = isHeadless
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  }

  const quickSvg = document.getElementById('quickHeadlessSvg');
  if (quickSvg) {
    quickSvg.innerHTML = isHeadless
      ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
      : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  }
}

async function handleHeadlessModalToggle(checked) {
  try {
    const res = await fetch('/api/settings/headless', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ headless: !!checked }),
    });
    const data = await res.json();
    if (res.ok) {
      if (state.config) state.config.headless_mode = data.headless;
      updateHeadlessUI(data.headless);
      showToast(data.headless ? '✓ Silent Headless mode enabled' : '✓ Visible Headed window mode enabled', 'info');
    } else {
      showToast(data.detail || 'Failed to update headless mode', 'error');
      updateHeadlessUI(state.config ? state.config.headless_mode : false);
    }
  } catch (err) {
    showToast('Network error toggling headless mode: ' + err.message, 'error');
    updateHeadlessUI(state.config ? state.config.headless_mode : false);
  }
}

async function toggleQuickHeadless() {
  const current = !!(state.config && state.config.headless_mode);
  const target = !current;
  await handleHeadlessModalToggle(target);
}

async function saveSettings() {
  const payload = {
    resume_path: (document.getElementById('settingResumePath')?.value || '').trim(),
    search_query: (document.getElementById('settingSearchQuery')?.value || '').trim(),
    search_location: (document.getElementById('settingSearchLocation')?.value || '').trim(),
    chatgpt_url: (document.getElementById('settingChatGptUrl')?.value || '').trim(),
    headless_mode: !!(document.getElementById('settingHeadlessToggle') && document.getElementById('settingHeadlessToggle').checked),
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeSettingsModal();
      if (typeof fetchSettings === 'function') await fetchSettings();
      showToast('✓ Settings updated successfully', 'success');
    } else {
      showAlert('Save Error', 'Could not save settings.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// Global Bindings
window.openPostModal = openPostModal;
window.closePostModal = closePostModal;
window.openAddJdModal = openAddJdModal;
window.closeAddJdModal = closeAddJdModal;
window.submitManualJd = submitManualJd;
window.openDirectOutreachModal = openDirectOutreachModal;
window.closeDirectOutreachModal = closeDirectOutreachModal;
window.resetDirectOutreachBody = resetDirectOutreachBody;
window.submitDirectOutreach = submitDirectOutreach;
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.closeModal = closeModal;
window.updateHeadlessUI = updateHeadlessUI;
window.handleHeadlessModalToggle = handleHeadlessModalToggle;
window.toggleQuickHeadless = toggleQuickHeadless;
window.saveSettings = saveSettings;
