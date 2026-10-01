/**
 * Reach — Application Entry Point & Master Bootstrapper
 * (src/static/app.js)
 * 
 * Modular scripts in /static/js/ are loaded prior to this file:
 * - state.js: Global state & configuration defaults
 * - utils.js: Dialogs, expandable snackbars, string escaping & date formatters
 * - notifications.js: Service worker, audio chimes, haptics & notification center
 * - sidebar.js: Tab switching, responsive collapse & navigation shortcuts
 * - api.js: Live session health, KPI statistics & resume uploader
 * - discovered.js: Discovered jobs table, 2-tier filtering & batch selection
 * - review.js: Candidate queue, AI email draft editor & Gmail dispatch
 * - history.js: Sent & cancelled history table & rejection filters
 * - crawler.js: Crawler trigger, scraper registry & spam reporting
 * - tasks.js: Real-time task drawer, execution queue & log streaming
 * - modals.js: Dialog overlays & Headless mode controls
 * - analytics.js: Chart.js visualizations & trend graphs
 */

document.addEventListener('DOMContentLoaded', () => {
  if (typeof initSidebarCollapse === 'function') initSidebarCollapse();

  const validTabs = ['tabAnalytics', 'tabCrawlers', 'tabDiscovered', 'tabEasyApply', 'tabQuestionBank', 'tabReview', 'tabSent'];
  const hashToTab = {
    '#analytics': 'tabAnalytics',
    '#crawlers': 'tabCrawlers',
    '#discovered': 'tabDiscovered',
    '#easy-apply': 'tabEasyApply',
    '#questions': 'tabQuestionBank',
    '#question-bank': 'tabQuestionBank',
    '#screening': 'tabQuestionBank',
    '#review': 'tabReview',
    '#sent': 'tabSent',
    '#others': 'tabSent',
    '#logs': 'tabSent',
    '#activity': 'tabSent',
  };

  let startTab = 'tabAnalytics';
  const hash = (window.location.hash || '').toLowerCase();
  if (hash === '#logs' || hash === '#activity') {
    try {
      localStorage.setItem('reach_history_view', 'logs');
    } catch (_) {}
  } else if (hash === '#sent' || hash === '#others') {
    try {
      localStorage.setItem('reach_history_view', 'applications');
    } catch (_) {}
  }

  if (hash && hashToTab[hash]) {
    startTab = hashToTab[hash];
  } else {
    try {
      const saved = localStorage.getItem('reach_active_tab');
      if (saved && validTabs.includes(saved)) {
        startTab = saved;
      }
    } catch (_) {}
  }

  if (typeof initNotificationSystem === 'function') initNotificationSystem();
  if (typeof switchTab === 'function') switchTab(startTab);
  if (typeof initCrawlerControls === 'function') initCrawlerControls();
  if (typeof fetchLocations === 'function') fetchLocations();
  if (typeof loadRejectionReasonsFilter === 'function') loadRejectionReasonsFilter();
  if (typeof loadDashboardData === 'function') loadDashboardData();
  if (typeof fetchHealth === 'function') fetchHealth();
  if (typeof fetchScrapers === 'function') fetchScrapers();
  if (typeof pollTaskStatus === 'function') pollTaskStatus();
  if (typeof startRealtimeSync === 'function') startRealtimeSync();
  if (typeof fetchActivityLogCounts === 'function') fetchActivityLogCounts();

  window.addEventListener('hashchange', () => {
    const newHash = (window.location.hash || '').toLowerCase();
    if (newHash === '#logs' || newHash === '#activity') {
      try {
        localStorage.setItem('reach_history_view', 'logs');
      } catch (_) {}
      if (typeof switchTab === 'function') switchTab('tabSent');
      if (typeof switchHistoryView === 'function') switchHistoryView('logs');
    } else if (newHash && hashToTab[newHash]) {
      if (typeof switchTab === 'function') switchTab(hashToTab[newHash]);
    }
  });

  if (window.state) {
    window.state.healthTimer = setInterval(() => {
      if (typeof fetchHealth === 'function') fetchHealth();
    }, 30000);
  }
});
