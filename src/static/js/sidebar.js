/**
 * Reach — Sidebar Navigation, Tab Switching & Collapse Controller
 * (src/static/js/sidebar.js)
 */

function handleBrandLogoClick() {
  const sidebar = document.getElementById('appSidebar');
  if (sidebar && sidebar.classList.contains('collapsed')) {
    toggleSidebarCollapse();
  } else {
    switchTab('tabAnalytics');
  }
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar) sidebar.classList.add('collapsed');
  if (backdrop) backdrop.classList.add('hidden');
  updateSidebarCollapseUI();
}

function toggleSidebarCollapse() {
  const sidebar = document.getElementById('appSidebar');
  if (!sidebar) return;
  const isCollapsed = sidebar.classList.toggle('collapsed');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (backdrop) {
    if (window.innerWidth <= 768 && !isCollapsed) {
      backdrop.classList.remove('hidden');
    } else {
      backdrop.classList.add('hidden');
    }
  }
  try {
    localStorage.setItem('reach_sidebar_collapsed', isCollapsed ? 'true' : 'false');
  } catch (_) {}
  updateSidebarCollapseUI();
}

function initSidebarCollapse() {
  const sidebar = document.getElementById('appSidebar');
  if (!sidebar) return;
  try {
    const saved = localStorage.getItem('reach_sidebar_collapsed');
    if (saved === 'false') {
      sidebar.classList.remove('collapsed');
    } else {
      sidebar.classList.add('collapsed');
    }
  } catch (_) {
    sidebar.classList.add('collapsed');
  }
  updateSidebarCollapseUI();
}

function updateSidebarCollapseUI() {
  const sidebar = document.getElementById('appSidebar');
  if (!sidebar) return;
  const isCollapsed = sidebar.classList.contains('collapsed');
  const toggleBtn = document.getElementById('btnToggleSidebar');
  if (toggleBtn) {
    toggleBtn.setAttribute('title', isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar');
    toggleBtn.innerHTML = isCollapsed
      ? '<svg class="sidebar-collapse-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>'
      : '<svg class="sidebar-collapse-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>';
  }
  const topbarBtn = document.getElementById('btnTopbarSidebarToggle');
  if (topbarBtn) {
    topbarBtn.setAttribute('title', isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar');
  }
}

function switchTab(tabId) {
  if (tabId === 'crawlers') tabId = 'tabCrawlers';
  else if (tabId === 'discovered') tabId = 'tabDiscovered';
  else if (tabId === 'easy_apply' || tabId === 'easyApply') tabId = 'tabEasyApply';
  else if (tabId === 'review') tabId = 'tabReview';
  else if (tabId === 'sent') tabId = 'tabSent';
  else if (tabId === 'analytics') tabId = 'tabAnalytics';

  state.activeTab = tabId;

  if (window.innerWidth <= 768) {
    closeMobileSidebar();
  }

  try {
    localStorage.setItem('reach_active_tab', tabId);
    const tabToHash = {
      tabAnalytics: '#analytics',
      tabCrawlers: '#crawlers',
      tabDiscovered: '#discovered',
      tabEasyApply: '#easy-apply',
      tabReview: '#review',
      tabSent: '#sent',
    };
    if (tabToHash[tabId] && window.location.hash !== tabToHash[tabId]) {
      history.replaceState(null, '', tabToHash[tabId]);
    }
  } catch (_) {}

  // Update Topbar Title & Breadcrumb
  const pageMeta = {
    tabAnalytics: { title: 'Dashboard Overview', breadcrumb: 'Real-time database intelligence & automation metrics' },
    tabCrawlers: { title: 'Job Crawlers & Portals', breadcrumb: 'Launch active scrapers or explore upcoming major job portal engines' },
    tabDiscovered: { title: 'Discovered Jobs', breadcrumb: 'Explore, filter, and review crawled job postings' },
    tabEasyApply: { title: 'LinkedIn Job Portal & Easy Apply', breadcrumb: 'Autonomous direct job crawling, auto-apply submissions & questionnaire screening' },
    tabReview: { title: 'Review & Drafts', breadcrumb: 'Approve AI cover letters and dispatch outreach' },
    tabSent: { title: 'Sent & History', breadcrumb: 'Track dispatched applications and historical outreach' },
  };
  const meta = pageMeta[tabId] || { title: 'Dashboard', breadcrumb: '' };
  const titleEl = document.getElementById('pageTitleDisplay');
  if (titleEl) titleEl.textContent = meta.title;
  const breadcrumbEl = document.getElementById('pageBreadcrumbDisplay');
  if (breadcrumbEl) breadcrumbEl.textContent = meta.breadcrumb;

  const btnAnalytics = document.getElementById('btnTabAnalytics');
  if (btnAnalytics) btnAnalytics.classList.toggle('active', tabId === 'tabAnalytics');
  const btnCrawlers = document.getElementById('btnTabCrawlers');
  if (btnCrawlers) btnCrawlers.classList.toggle('active', tabId === 'tabCrawlers');
  const btnDiscovered = document.getElementById('btnTabDiscovered');
  if (btnDiscovered) btnDiscovered.classList.toggle('active', tabId === 'tabDiscovered');
  const btnEasyApply = document.getElementById('btnTabEasyApply');
  if (btnEasyApply) btnEasyApply.classList.toggle('active', tabId === 'tabEasyApply');
  const btnReview = document.getElementById('btnTabReview');
  if (btnReview) btnReview.classList.toggle('active', tabId === 'tabReview');
  const btnSent = document.getElementById('btnTabSent');
  if (btnSent) btnSent.classList.toggle('active', tabId === 'tabSent');

  const panelAnalytics = document.getElementById('tabAnalytics');
  if (panelAnalytics) panelAnalytics.classList.toggle('hidden', tabId !== 'tabAnalytics');
  const panelCrawlers = document.getElementById('tabCrawlers');
  if (panelCrawlers) panelCrawlers.classList.toggle('hidden', tabId !== 'tabCrawlers');
  const panelDiscovered = document.getElementById('tabDiscovered');
  if (panelDiscovered) panelDiscovered.classList.toggle('hidden', tabId !== 'tabDiscovered');
  const panelEasyApply = document.getElementById('tabEasyApply');
  if (panelEasyApply) panelEasyApply.classList.toggle('hidden', tabId !== 'tabEasyApply');
  const panelReview = document.getElementById('tabReview');
  if (panelReview) panelReview.classList.toggle('hidden', tabId !== 'tabReview');
  const panelSent = document.getElementById('tabSent');
  if (panelSent) panelSent.classList.toggle('hidden', tabId !== 'tabSent');

  fetchStats();

  if (tabId === 'tabCrawlers') {
    if (typeof fetchHealth === 'function') fetchHealth();
    if (typeof fetchScrapers === 'function') fetchScrapers();
  } else if (tabId === 'tabDiscovered') {
    fetchDiscoveredPosts();
  } else if (tabId === 'tabEasyApply') {
    if (typeof fetchEasyApplyPosts === 'function') fetchEasyApplyPosts();
  } else if (tabId === 'tabReview') {
    fetchReviewPosts();
  } else if (tabId === 'tabSent') {
    loadRejectionReasonsFilter();
    fetchSentPosts();
  } else if (tabId === 'tabAnalytics') {
    loadAnalytics(state.analyticsDays || 30);
  }
}

// --- Interactive Jump Links from Dashboard KPI Cards ---
function jumpToSentApplications() {
  switchTab('tabSent');
}

function jumpToOutreachReady() {
  switchTab('tabDiscovered');
  const catEl = document.getElementById('selectCategory');
  if (catEl) catEl.value = 'EMAIL_OUTREACH';
  const genEl = document.getElementById('selectGenStatus');
  if (genEl) genEl.value = 'ALL';
  applyFilters();
}

function jumpToReviewDrafts() {
  switchTab('tabReview');
}

function jumpToDiscovered() {
  switchTab('tabDiscovered');
  const genEl = document.getElementById('selectGenStatus');
  if (genEl) genEl.value = 'PENDING';
  const catEl = document.getElementById('selectCategory');
  if (catEl) catEl.value = 'ALL';
  applyFilters();
}

function jumpToScreenedApplications() {
  switchTab('tabDiscovered');
  const genEl = document.getElementById('selectGenStatus');
  if (genEl) genEl.value = 'REJECTED';
  applyFilters();
}

// Global Bindings
window.handleBrandLogoClick = handleBrandLogoClick;
window.closeMobileSidebar = closeMobileSidebar;
window.toggleSidebarCollapse = toggleSidebarCollapse;
window.initSidebarCollapse = initSidebarCollapse;
window.updateSidebarCollapseUI = updateSidebarCollapseUI;
window.switchTab = switchTab;
window.jumpToSentApplications = jumpToSentApplications;
window.jumpToOutreachReady = jumpToOutreachReady;
window.jumpToReviewDrafts = jumpToReviewDrafts;
window.jumpToDiscovered = jumpToDiscovered;
window.jumpToScreenedApplications = jumpToScreenedApplications;
