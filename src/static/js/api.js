/**
 * Reach — API Client, Health Diagnostics & Settings Synchronizer
 * (src/static/js/api.js)
 */

async function fetchHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    state.health = await res.json();

    updateHealthPill('healthInfopark', state.health.infopark || { connected: true, label: 'Online' });
    updateHealthPill('healthLinkedin', state.health.linkedin);
    updateHealthPill('healthChatgpt', state.health.chatgpt);
    updateHealthPill('healthGmail', state.health.gmail);
    updateHealthPill('healthDatabase', state.health.database);

    const banner = document.getElementById('systemAlertBanner');
    const msgEl = document.getElementById('systemAlertMessage');
    const actionsEl = document.getElementById('systemAlertActions');

    if (state.health.has_issues && state.health.issues.length > 0) {
      if (msgEl) msgEl.textContent = state.health.issues.join(' | ');
      if (actionsEl) {
        actionsEl.innerHTML = '';
        if (state.health.linkedin && !state.health.linkedin.connected) {
          const btn = document.createElement('button');
          btn.className = 'alert-action-btn';
          btn.textContent = 'Log into LinkedIn';
          btn.onclick = () => launchServiceLogin('linkedin');
          actionsEl.appendChild(btn);
        }
        if (state.health.chatgpt && !state.health.chatgpt.connected) {
          const btn = document.createElement('button');
          btn.className = 'alert-action-btn';
          btn.textContent = 'Log into ChatGPT';
          btn.onclick = () => launchServiceLogin('chatgpt');
          actionsEl.appendChild(btn);
        }
        if (state.health.gmail && !state.health.gmail.connected) {
          const btn = document.createElement('button');
          btn.className = 'alert-action-btn';
          btn.textContent = 'Log into Gmail';
          btn.onclick = () => launchServiceLogin('gmail');
          actionsEl.appendChild(btn);
        }
      }
      if (banner) banner.classList.remove('hidden');
    } else {
      if (actionsEl) actionsEl.innerHTML = '';
      if (banner) banner.classList.add('hidden');
    }
  } catch (err) {
    console.warn('Health check error:', err);
  }
}

function updateHealthPill(elementId, serviceData) {
  const el = document.getElementById(elementId);
  if (!el || !serviceData) return;

  el.classList.remove('ok', 'warn', 'error');
  if (serviceData.connected) {
    el.classList.add('ok');
    el.title = `${serviceData.label || 'Connected'}`;
  } else {
    el.classList.add('warn');
    el.title = `${serviceData.label || 'Not Logged In'}`;
  }

  const suffix = elementId.replace('health', '');
  const labelEl = document.getElementById(`healthLabel${suffix}`);
  if (labelEl) {
    labelEl.textContent = serviceData.label || (serviceData.connected ? 'Online' : 'Not Connected');
    labelEl.style.color = serviceData.connected ? '#a7f3d0' : '#fde68a';
  }

  const btnEl = document.getElementById(`healthBtn${suffix}`);
  const btnLabelEl = document.getElementById(`healthBtnLabel${suffix}`);
  if (btnEl) {
    if (serviceData.connected) {
      btnEl.className = 'health-action-btn btn-subtle';
      btnEl.title = `Launch ${suffix} in Firefox to verify or switch accounts`;
      if (btnLabelEl) btnLabelEl.textContent = 'Open / Re-login';
    } else {
      btnEl.className = 'health-action-btn btn-warn';
      btnEl.title = `Click to log into ${suffix} in Firefox`;
      if (btnLabelEl) btnLabelEl.textContent = '👉 Log In Now';
    }
  }
}

async function launchServiceLogin(service) {
  try {
    const res = await fetch(`/api/tasks/login/${service}`, { method: 'POST' });
    const data = await res.json();

    if (!res.ok) {
      if (typeof showSnackbar === 'function') {
        showSnackbar({
          title: 'Cannot Launch Login',
          message: data.detail || data.message || 'Another task is currently running.',
          type: 'error',
        });
      } else if (typeof showAlert === 'function') {
        showAlert('Cannot Launch Login', data.detail || data.message || 'Another task is currently running.');
      }
      return;
    }

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Browser Login Launched',
        message: data.message || 'Opening headed Firefox. Complete login and close the browser window when done.',
        type: 'info',
        duration: 5000,
      });
    }

    if (typeof startTaskPolling === 'function') {
      startTaskPolling();
    }
    const card = document.getElementById('liveTaskCard');
    if (card) card.classList.remove('hidden');

  } catch (err) {
    console.error('Launch login error:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Network Error',
        message: 'Could not contact server to launch login session.',
        type: 'error',
      });
    }
  }
}

function dismissSystemAlert() {
  const banner = document.getElementById('systemAlertBanner');
  if (banner) banner.classList.add('hidden');
}

async function loadDashboardData() {
  await Promise.all([
    fetchStats(),
    fetchSettings(),
    fetchLocations(),
    loadRejectionReasonsFilter(),
  ]);

  if (state.activeTab === 'tabDiscovered') {
    await fetchDiscoveredPosts();
  } else if (state.activeTab === 'tabEasyApply') {
    if (typeof fetchEasyApplyPosts === 'function') await fetchEasyApplyPosts();
  } else if (state.activeTab === 'tabReview') {
    await fetchReviewPosts();
  } else if (state.activeTab === 'tabSent') {
    if (typeof currentHistoryView !== 'undefined' && currentHistoryView === 'logs') {
      if (typeof fetchActivityLogs === 'function') await fetchActivityLogs();
    } else {
      await fetchSentPosts();
    }
  } else if (state.activeTab === 'tabAnalytics') {
    await loadAnalytics(state.analyticsDays || 30);
  }
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const stats = await res.json();

    const discoveredTotal = stats.discovered_total !== undefined ? stats.discovered_total : (stats.total_posts || 0);
    const draftsReady = stats.emails_generated || 0;
    const sentCount = stats.applications_sent || 0;
    const outreachReady = stats.email_outreach_total || 0;
    const totalSourced = stats.total_posts || 0;
    const othersCount = stats.others_total !== undefined ? stats.others_total : (sentCount + (stats.rejected_total || 0));
    const pendingCount = stats.pending_generation !== undefined ? stats.pending_generation : 0;
    const cancelledCount = stats.rejected_total || 0;
    const spamCount = stats.potential_spam_total !== undefined ? stats.potential_spam_total : 0;
    const withEmails = stats.with_emails !== undefined ? stats.with_emails : outreachReady;

    // Top Metrics Summary Bar
    const elApplied = document.getElementById('statApplied');
    if (elApplied) elApplied.textContent = sentCount;

    const elGenerated = document.getElementById('statGenerated');
    if (elGenerated) elGenerated.textContent = draftsReady;

    const elOutreach = document.getElementById('statOutreach');
    if (elOutreach) elOutreach.textContent = outreachReady;

    const elTotalSourced = document.getElementById('statTotalSourced');
    if (elTotalSourced) elTotalSourced.textContent = totalSourced;

    // Backward compatibility for legacy elements if present
    const elDiscovered = document.getElementById('statDiscovered');
    if (elDiscovered) elDiscovered.textContent = discoveredTotal;
    const elPending = document.getElementById('statPending');
    if (elPending) elPending.textContent = pendingCount;
    const elSent = document.getElementById('statSent');
    if (elSent) elSent.textContent = othersCount;

    // Sidebar Navigation Badges:
    // 1. Discovered Jobs: count of yet to generate JDs
    const countDiscEl = document.getElementById('countDiscovered');
    if (countDiscEl) {
      countDiscEl.textContent = pendingCount;
      countDiscEl.title = `${pendingCount} direct email outreach jobs yet to generate`;
    }

    // 2. Review & Drafts: count of drafts ready for review
    const countRevEl = document.getElementById('countReview');
    if (countRevEl) {
      countRevEl.textContent = draftsReady;
      countRevEl.title = `${draftsReady} drafts ready for review`;
    }
    const reviewQueueBadge = document.getElementById('reviewQueueCount');
    if (reviewQueueBadge) {
      reviewQueueBadge.textContent = draftsReady;
    }

    // 2b. LinkedIn Easy Apply badge
    const countEasyApplyEl = document.getElementById('countEasyApply');
    if (countEasyApplyEl) {
      const eaPending = stats.easy_apply_pending !== undefined ? stats.easy_apply_pending : (stats.easy_apply_total || 0);
      countEasyApplyEl.textContent = eaPending;
      countEasyApplyEl.title = `${eaPending} Easy Apply jobs ready`;
    }

    // 3. Sent & History: Others tab counters
    const elOthersAll = document.getElementById('countOthersAll');
    if (elOthersAll) elOthersAll.textContent = othersCount;

    const elOthersSent = document.getElementById('countOthersSent');
    if (elOthersSent) elOthersSent.textContent = sentCount;

    const elOthersCancelled = document.getElementById('countOthersCancelled');
    if (elOthersCancelled) elOthersCancelled.textContent = cancelledCount;

    // 4. Executive Overview KPI Performance Cards (Analytics Tab)
    const kpiAppliedEl = document.getElementById('kpiApplied');
    if (kpiAppliedEl) kpiAppliedEl.textContent = Number(sentCount).toLocaleString();

    const kpiConvEl = document.getElementById('kpiConversionRate');
    if (kpiConvEl) {
      const conv = totalSourced > 0 ? (sentCount / totalSourced * 100).toFixed(1) : '0.0';
      kpiConvEl.textContent = `${conv}% conversion`;
    }

    const kpiDirectEl = document.getElementById('kpiDirectEmails');
    if (kpiDirectEl) kpiDirectEl.textContent = Number(withEmails).toLocaleString();

    const kpiEmailRateEl = document.getElementById('kpiEmailRate');
    if (kpiEmailRateEl) {
      const emailRate = totalSourced > 0 ? (withEmails / totalSourced * 100).toFixed(1) : '0.0';
      kpiEmailRateEl.textContent = `${emailRate}% emails found`;
    }

    const kpiDraftedEl = document.getElementById('kpiDrafted');
    if (kpiDraftedEl) kpiDraftedEl.textContent = Number(draftsReady).toLocaleString();

    const kpiDraftReadyEl = document.getElementById('kpiDraftReady');
    if (kpiDraftReadyEl) kpiDraftReadyEl.textContent = `${Number(draftsReady).toLocaleString()} ready to send`;

    const kpiPendingGenEl = document.getElementById('kpiPendingGen');
    if (kpiPendingGenEl) kpiPendingGenEl.textContent = `${Number(pendingCount).toLocaleString()} pending AI`;

    const kpiScrapedEl = document.getElementById('kpiScraped');
    if (kpiScrapedEl) kpiScrapedEl.textContent = Number(totalSourced).toLocaleString();

    const kpiRejectedEl = document.getElementById('kpiRejected');
    if (kpiRejectedEl) kpiRejectedEl.textContent = Number(cancelledCount).toLocaleString();

    const kpiSpamEl = document.getElementById('kpiSpamFlagged');
    if (kpiSpamEl) kpiSpamEl.textContent = `${Number(spamCount).toLocaleString()} potential spam`;

    // Smart change detection to trigger active tab view updates
    const prevStats = state.lastStatsSnapshot;
    const statsChanged = !prevStats || (
      prevStats.total_posts !== stats.total_posts ||
      prevStats.emails_generated !== stats.emails_generated ||
      prevStats.applications_sent !== stats.applications_sent ||
      prevStats.rejected_total !== stats.rejected_total ||
      prevStats.pending_generation !== stats.pending_generation ||
      prevStats.discovered_total !== stats.discovered_total ||
      prevStats.others_total !== stats.others_total
    );

    state.lastStatsSnapshot = { ...stats };
  } catch (err) {
    console.error('Error fetching stats:', err);
  }
}

function refreshActiveTabRealtime(stats) {
  const activeTab = state.activeTab;

  if (activeTab === 'tabDiscovered') {
    const searchInput = document.getElementById('inputSearch');
    const isSearching = searchInput && document.activeElement === searchInput;
    const hasSelection = state.selectedIds && state.selectedIds.size > 0;
    if (!isSearching && !hasSelection) {
      if (typeof fetchDiscoveredPosts === 'function') fetchDiscoveredPosts();
    }
  } else if (activeTab === 'tabReview') {
    const subjInput = document.getElementById('draftSubject');
    const bodyInput = document.getElementById('draftBody');
    const searchRevInput = document.getElementById('inputSearchReview');
    const isEditing = (subjInput && document.activeElement === subjInput) ||
                      (bodyInput && document.activeElement === bodyInput) ||
                      (searchRevInput && document.activeElement === searchRevInput);
    if (!isEditing) {
      if (typeof fetchReviewPosts === 'function') fetchReviewPosts();
    }
  } else if (activeTab === 'tabSent') {
    const searchSentInput = document.getElementById('inputSearchSent');
    const isSearching = searchSentInput && document.activeElement === searchSentInput;
    const hasSelection = state.selectedSentIds && state.selectedSentIds.size > 0;
    if (!isSearching && !hasSelection) {
      if (typeof fetchSentPosts === 'function') fetchSentPosts();
    }
  } else if (activeTab === 'tabAnalytics') {
    if (typeof loadAnalytics === 'function') {
      loadAnalytics(state.analyticsDays || 30);
    }
  }
}

let realtimeSyncCounter = 0;
async function syncRealtimeData() {
  realtimeSyncCounter++;

  // 1. Fetch updated stats and refresh metrics
  await fetchStats();

  // 2. Check task status - if an automation is running and polling is not active, start polling
  try {
    const res = await fetch('/api/tasks/status');
    if (res.ok) {
      const task = await res.json();
      if (task.status === 'running' && !state.pollingTimer) {
        if (typeof startTaskPolling === 'function') startTaskPolling();
      }
    }
  } catch (_) {}

  // 3. Periodic health diagnostics check every ~30 seconds (10 ticks)
  if (realtimeSyncCounter % 10 === 0) {
    if (typeof fetchHealth === 'function') fetchHealth();
  }
}

function startRealtimeSync() {
  if (state.liveSyncTimer) clearInterval(state.liveSyncTimer);
  state.liveSyncTimer = setInterval(syncRealtimeData, 3000);
}

function stopRealtimeSync() {
  if (state.liveSyncTimer) {
    clearInterval(state.liveSyncTimer);
    state.liveSyncTimer = null;
  }
}

function filterSentApplications() {
  switchTab('tabSent');
  if (typeof setOthersFilter === 'function') {
    setOthersFilter('SENT');
  }
}

function filterOutreachReady() {
  switchTab('tabDiscovered');
  const catSelect = document.getElementById('selectCategory');
  if (catSelect) catSelect.value = 'EMAIL_OUTREACH';
  state.categoryFilter = 'EMAIL_OUTREACH';
  const genSelect = document.getElementById('selectGenStatus');
  if (genSelect) {
    genSelect.value = 'ALL';
    state.genStatusFilter = 'ALL';
  }
  const srcSelect = document.getElementById('selectSource');
  if (srcSelect) {
    srcSelect.value = 'ALL';
    state.sourceFilter = 'ALL';
  }
  const searchInput = document.getElementById('inputSearch');
  if (searchInput) searchInput.value = '';
  state.searchQuery = '';
  if (typeof setExpFilter === 'function') {
    setExpFilter('ALL');
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    state.config = await res.json();

    const resumePath = state.config.resume_path || '';
    const filename = resumePath.split('/').pop() || 'No Resume Selected';
    const resNameEl = document.getElementById('resumeFileName');
    if (resNameEl) resNameEl.textContent = filename;
    const resPillEl = document.getElementById('resumePill');
    if (resPillEl) resPillEl.title = `Active Resume: ${resumePath}`;

    const crawlerLocSelect = document.getElementById('crawlerLocationSelect');
    if (crawlerLocSelect) {
      const savedCrawlerLoc = localStorage.getItem('reach_selected_crawler_location');
      if (savedCrawlerLoc !== null) {
        crawlerLocSelect.value = savedCrawlerLoc;
      } else if (state.config.search_location) {
        crawlerLocSelect.value = state.config.search_location;
      }
    }

    if (typeof updateCrawlerSearchPlaceholder === 'function') {
      updateCrawlerSearchPlaceholder();
    }

    if (typeof updateHeadlessUI === 'function') {
      updateHeadlessUI(state.config ? state.config.headless_mode : false);
    }
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function handleResumeUpload(files) {
  if (!files || files.length === 0) return;
  const file = files[0];

  const formData = new FormData();
  formData.append('file', file);

  showToast(`Uploading ${file.name}...`, 'info');

  try {
    const res = await fetch('/api/resume/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (res.ok) {
      showToast(`✓ Resume replaced: ${data.filename}`, 'success');
      state.config.resume_path = data.resume_path;
      const resNameEl = document.getElementById('resumeFileName');
      if (resNameEl) resNameEl.textContent = data.filename;
      const setPathEl = document.getElementById('settingResumePath');
      if (setPathEl) setPathEl.value = data.resume_path;
    } else {
      showAlert('Upload Error', data.detail || 'Could not upload resume.');
    }
  } catch (err) {
    showAlert('Upload Error', err.message);
  } finally {
    const fileInput = document.getElementById('resumeFileInput');
    if (fileInput) fileInput.value = '';
  }
}

// Global Bindings
window.fetchHealth = fetchHealth;
window.updateHealthPill = updateHealthPill;
window.launchServiceLogin = launchServiceLogin;
window.dismissSystemAlert = dismissSystemAlert;
window.loadDashboardData = loadDashboardData;
window.fetchStats = fetchStats;
window.filterSentApplications = filterSentApplications;
window.filterOutreachReady = filterOutreachReady;
window.fetchSettings = fetchSettings;
window.handleResumeUpload = handleResumeUpload;
window.refreshActiveTabRealtime = refreshActiveTabRealtime;
window.syncRealtimeData = syncRealtimeData;
window.startRealtimeSync = startRealtimeSync;
window.stopRealtimeSync = stopRealtimeSync;
