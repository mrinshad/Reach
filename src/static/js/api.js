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

    if (state.health.has_issues && state.health.issues.length > 0) {
      if (msgEl) msgEl.textContent = state.health.issues.join(' | ');
      if (banner) banner.classList.remove('hidden');
    } else {
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
  } else if (state.activeTab === 'tabReview') {
    await fetchReviewPosts();
  } else if (state.activeTab === 'tabSent') {
    await fetchSentPosts();
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
    if (elPending) elPending.textContent = stats.pending_generation || 0;
    const elSent = document.getElementById('statSent');
    if (elSent) elSent.textContent = othersCount;

    // Sidebar Navigation Badges:
    // 1. Discovered Jobs: count of yet to generate JDs
    const countDiscEl = document.getElementById('countDiscovered');
    if (countDiscEl) {
      const pendingCount = stats.pending_generation !== undefined ? stats.pending_generation : 0;
      countDiscEl.textContent = pendingCount;
      countDiscEl.title = `${pendingCount} direct email outreach jobs yet to generate`;
    }

    // 2. Review & Drafts: count of drafts ready for review
    const countRevEl = document.getElementById('countReview');
    if (countRevEl) {
      countRevEl.textContent = draftsReady;
      countRevEl.title = `${draftsReady} drafts ready for review`;
    }

    // 3. Sent & History: show nothing (no badge)

    const cancelledCount = stats.rejected_total || 0;
    const elOthersAll = document.getElementById('countOthersAll');
    if (elOthersAll) elOthersAll.textContent = othersCount;

    const elOthersSent = document.getElementById('countOthersSent');
    if (elOthersSent) elOthersSent.textContent = sentCount;

    const elOthersCancelled = document.getElementById('countOthersCancelled');
    if (elOthersCancelled) elOthersCancelled.textContent = cancelledCount;
  } catch (err) {
    console.error('Error fetching stats:', err);
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
window.dismissSystemAlert = dismissSystemAlert;
window.loadDashboardData = loadDashboardData;
window.fetchStats = fetchStats;
window.filterSentApplications = filterSentApplications;
window.filterOutreachReady = filterOutreachReady;
window.fetchSettings = fetchSettings;
window.handleResumeUpload = handleResumeUpload;
