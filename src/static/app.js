/**
 * Reach — Job Outreach Automation Client Application
 */

const state = {
  activeTab: 'tabAnalytics',
  expFilter: 'ALL',
  categoryFilter: 'EMAIL_OUTREACH',
  genStatusFilter: 'PENDING',
  sourceFilter: 'ALL',
  othersFilter: 'ALL',
  pendingCancelPostId: null,
  searchQuery: '',
  searchReview: '',
  searchSent: '',
  page: 1,
  limit: 25,
  total: 0,
  posts: [],
  selectedIds: new Set(),
  selectedDraftIds: new Set(),
  reviewPosts: [],
  activeReviewPost: null,
  sentPosts: [],
  sentPage: 1,
  sentLimit: 25,
  sentTotal: 0,
  config: {},
  health: {},
  pollingTimer: null,
  healthTimer: null,
  showLogs: false,
  awaitingSentPost: null,
  analyticsDays: 30,
  analyticsData: null,
  charts: {},
  sortBy: 'default',
  dateFilter: 'ALL',
  othersReason: 'ALL',
  locationFilter: 'ALL',
  discoveredReason: 'ALL',
};

const DEFAULT_OPPORTUNITY_SUBJECT = "Full-Stack Software Engineer – Job Opportunities";
const DEFAULT_OPPORTUNITY_BODY = `Hi,

I’m Mohammed Rinshad, a Full-Stack Software Engineer with 3+ years of experience in web and enterprise application development.

My experience includes React, Next.js, Node.js, TypeScript, .NET Core, REST APIs, PostgreSQL, SQL Server, Azure, GCP, CI/CD, authentication, RBAC, and database design. I’ve worked on ERP, accounting, education, and enterprise applications, including both frontend and backend development.

I’m currently looking for opportunities in Frontend, Backend, Full-Stack, DevOps, or Cloud Engineering. I’m open to relocating for the right opportunity and am also interested in remote roles.

I’ve attached my resume for reference. If there are any current or upcoming openings that match my background, I’d be grateful to be considered.

Regards,
Mohammed Rinshad P
+91 98956 12423
rinshadmorayur09@gmail.com
LinkedIn: linkedin.com/in/mrinshad
GitHub: github.com/mrinshad`;

// --- Custom Dialog System (Replaces Native Alert & Confirm) ---
let dialogResolver = null;

function showConfirm(title, message, options = {}) {
  return new Promise((resolve) => {
    dialogResolver = resolve;
    const overlay = document.getElementById('customDialogOverlay');
    const titleEl = document.getElementById('dialogTitle');
    const msgEl = document.getElementById('dialogMessage');
    const confirmBtn = document.getElementById('dialogBtnConfirm');
    const cancelBtn = document.getElementById('dialogBtnCancel');
    const iconCircle = document.getElementById('dialogIconCircle');

    titleEl.textContent = title;
    msgEl.textContent = message;
    confirmBtn.textContent = options.confirmText || 'Confirm';
    cancelBtn.textContent = options.cancelText || 'Cancel';

    if (options.danger) {
      confirmBtn.className = 'btn btn-danger';
      iconCircle.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
      iconCircle.style.background = 'rgba(244, 63, 94, 0.15)';
    } else {
      confirmBtn.className = 'btn btn-primary';
      iconCircle.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
      iconCircle.style.background = 'rgba(99, 102, 241, 0.15)';
    }

    cancelBtn.style.display = options.alertOnly ? 'none' : 'inline-flex';
    overlay.classList.remove('hidden');
  });
}

function showCenterAlert(title, message, options = {}) {
  return showConfirm(title, message, {
    alertOnly: true,
    confirmText: options.confirmText || 'Dismiss',
    danger: options.danger !== undefined ? options.danger : true,
    ...options
  });
}

function closeCustomDialog(result) {
  const overlay = document.getElementById('customDialogOverlay');
  overlay.classList.add('hidden');
  if (dialogResolver) {
    dialogResolver(result);
    dialogResolver = null;
  }
}

// --- Stacked Expandable Snackbar Notification System ---
let snackbarCounter = 0;
const activeSnackbars = new Map();

function showSnackbar({
  title,
  message = '',
  type = 'info', // 'info' | 'success' | 'warn' | 'error'
  details = null,
  duration = null,
}) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const id = `sb-${Date.now()}-${++snackbarCounter}`;

  let heading = title;
  let preview = message;
  let fullDetails = details;

  // Derive heading & preview if not explicitly provided
  if (!heading) {
    if (type === 'error') {
      const lines = (message || '').split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length > 1) {
        heading = lines[0].slice(0, 45);
        preview = lines.slice(1)[0] || '';
        fullDetails = message;
      } else if (message && message.includes(':')) {
        const parts = message.split(':');
        heading = parts[0].trim();
        preview = parts.slice(1).join(':').trim();
        if (message.length > 70) fullDetails = message;
      } else {
        heading = 'Action Error';
        preview = message;
      }
    } else if (type === 'success') {
      heading = 'Success';
      preview = (message || '').replace(/^✓\s*/, '');
    } else if (type === 'warn') {
      heading = 'Notice';
      preview = message;
    } else {
      heading = 'Update';
      preview = message;
    }
  }

  // If text is long and no details given, preserve full text in expandable section
  if (!fullDetails && message && message.length > 70) {
    fullDetails = message;
  }

  const hasDetails = Boolean(fullDetails);

  // SVG Icons
  let iconSvg = '';
  if (type === 'error') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
  } else if (type === 'success') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  } else if (type === 'warn') {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
  } else {
    iconSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
  }

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const snackbarEl = document.createElement('div');
  snackbarEl.className = `snackbar-item snackbar-${type} ${hasDetails ? 'has-details' : ''}`;
  snackbarEl.id = id;

  snackbarEl.innerHTML = `
    <div class="snackbar-header" onclick="toggleSnackbar('${id}')" title="${hasDetails ? 'Click to expand/collapse details' : ''}">
      <div class="snackbar-icon">${iconSvg}</div>
      <div class="snackbar-titles">
        <span class="snackbar-heading">${escapeHtml(heading)}</span>
        ${preview ? `<span class="snackbar-preview">${escapeHtml(preview)}</span>` : ''}
      </div>
      <div class="snackbar-controls">
        ${
          hasDetails
            ? `<span class="snackbar-expand-icon" title="Toggle details">
                 <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
               </span>`
            : ''
        }
        <button class="snackbar-close" onclick="dismissSnackbar('${id}', event)" title="Dismiss">×</button>
      </div>
    </div>
    ${
      hasDetails
        ? `<div class="snackbar-details hidden" id="details-${id}">
             <div class="snackbar-details-content">
               <pre class="snackbar-pre">${escapeHtml(fullDetails)}</pre>
             </div>
             <div class="snackbar-details-footer">
               <button class="btn btn-outline btn-xs" onclick="copySnackbarText('${id}', event)">
                 <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                 <span>Copy Details</span>
               </button>
               <span class="snackbar-timestamp">${timeStr}</span>
             </div>
           </div>`
        : ''
    }
  `;

  activeSnackbars.set(id, {
    element: snackbarEl,
    fullText: fullDetails || `${heading}: ${preview}`,
    timer: null,
  });

  container.appendChild(snackbarEl);

  // Auto-dismiss timeout: errors stay longer (14s) or until dismissed; success/info 6s
  const autoTimeout = duration !== null ? duration : (type === 'error' ? 14000 : 6000);
  if (autoTimeout > 0) {
    const timer = setTimeout(() => dismissSnackbar(id), autoTimeout);
    activeSnackbars.get(id).timer = timer;

    // Pause on hover
    snackbarEl.addEventListener('mouseenter', () => {
      const itemData = activeSnackbars.get(id);
      if (itemData && itemData.timer) {
        clearTimeout(itemData.timer);
        itemData.timer = null;
      }
    });

    snackbarEl.addEventListener('mouseleave', () => {
      const itemData = activeSnackbars.get(id);
      if (itemData && !itemData.timer && !snackbarEl.classList.contains('expanded')) {
        itemData.timer = setTimeout(() => dismissSnackbar(id), 3000);
      }
    });
  }

  // Keep max 5 stacked snackbars
  const items = container.querySelectorAll('.snackbar-item');
  if (items.length > 5) {
    dismissSnackbar(items[0].id);
  }
}

function toggleSnackbar(id) {
  const item = document.getElementById(id);
  if (!item) return;
  const detailsEl = document.getElementById(`details-${id}`);
  if (!detailsEl) return;

  const isExpanded = item.classList.toggle('expanded');
  detailsEl.classList.toggle('hidden', !isExpanded);

  // When expanded, stop timer so user can read comfortably
  const itemData = activeSnackbars.get(id);
  if (itemData && itemData.timer && isExpanded) {
    clearTimeout(itemData.timer);
    itemData.timer = null;
  }
}

function dismissSnackbar(id, event) {
  if (event) event.stopPropagation();
  const item = document.getElementById(id);
  if (!item) return;

  const itemData = activeSnackbars.get(id);
  if (itemData && itemData.timer) {
    clearTimeout(itemData.timer);
  }
  activeSnackbars.delete(id);

  item.style.opacity = '0';
  item.style.transform = 'translateX(45px) scale(0.95)';
  item.style.transition = 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)';
  setTimeout(() => item.remove(), 230);
}

function copySnackbarText(id, event) {
  if (event) event.stopPropagation();
  const itemData = activeSnackbars.get(id);
  if (!itemData) return;

  navigator.clipboard.writeText(itemData.fullText).then(() => {
    const btn = event.currentTarget;
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `<span>✓ Copied</span>`;
      setTimeout(() => { btn.innerHTML = orig; }, 1600);
    }
  });
}

function showToast(message, type = 'info') {
  showSnackbar({ message, type });
}

function showAlert(title, message, options = {}) {
  const isErr = title.toLowerCase().includes('error') || title.toLowerCase().includes('failed') || title.toLowerCase().includes('stopped');
  showSnackbar({
    title: title,
    message: (message || '').split('\n')[0],
    details: (message && (message.includes('\n') || message.length > 70)) ? message : null,
    type: isErr ? 'error' : 'warn',
  });
  if (options.centerPopup || isErr) {
    showCenterAlert(title, message, { danger: isErr });
  }
}

// --- Multi-Channel In-App & Desktop Notification System ---
let notificationState = {
  list: [],
  unreadCount: 0,
  audioCtx: null,
};

function initNotificationSystem() {
  try {
    const saved = localStorage.getItem('reach_notifications');
    if (saved) {
      notificationState.list = JSON.parse(saved);
      notificationState.unreadCount = notificationState.list.filter(n => !n.read).length;
    }
  } catch (_) {
    notificationState.list = [];
  }
  updateNotificationBadgeUI();
  updateDesktopPermButtonUI();

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    const wrapper = document.querySelector('.notification-center-wrapper');
    const dropdown = document.getElementById('notificationDropdown');
    if (wrapper && dropdown && !wrapper.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

function updateDesktopPermButtonUI() {
  const btn = document.getElementById('btnDesktopPerm');
  if (!btn) return;
  if (!('Notification' in window)) {
    btn.style.display = 'none';
    return;
  }
  if (Notification.permission === 'granted') {
    btn.textContent = 'Desktop: On';
    btn.style.opacity = '0.7';
    btn.disabled = true;
  } else if (Notification.permission === 'denied') {
    btn.textContent = 'Desktop: Blocked';
    btn.disabled = true;
  } else {
    btn.textContent = 'Enable Desktop Alerts';
    btn.disabled = false;
  }
}

async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    showToast('Browser does not support desktop notifications', 'warn');
    return;
  }
  try {
    const perm = await Notification.requestPermission();
    updateDesktopPermButtonUI();
    if (perm === 'granted') {
      showToast('Desktop notifications enabled!', 'success');
      playNotificationSound();
    }
  } catch (err) {
    console.warn('Notification permission error:', err);
  }
}

function playNotificationSound() {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) return;
    if (!notificationState.audioCtx || notificationState.audioCtx.state === 'closed') {
      notificationState.audioCtx = new AudioCtxClass();
    }
    const ctx = notificationState.audioCtx;
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
    const now = ctx.currentTime;

    // Harmonic double chime (D5: 587.33Hz -> A5: 880Hz)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.001, now);
    gain1.gain.exponentialRampToValueAtTime(0.18, now + 0.04);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.3);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(880, now + 0.12);
    gain2.gain.setValueAtTime(0.001, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.2, now + 0.16);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.6);
  } catch (err) {
    console.debug('Audio chime error:', err);
  }
}

function sendAppNotification({ title, message, type = 'info' }) {
  const item = {
    id: 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
    title: title || 'System Update',
    message: message || '',
    type: type, // 'success', 'info', 'warn', 'error'
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: new Date().toLocaleDateString(),
    read: false,
  };

  notificationState.list.unshift(item);
  if (notificationState.list.length > 50) {
    notificationState.list = notificationState.list.slice(0, 50);
  }
  notificationState.unreadCount = notificationState.list.filter(n => !n.read).length;

  try {
    localStorage.setItem('reach_notifications', JSON.stringify(notificationState.list));
  } catch (_) {}

  updateNotificationBadgeUI();
  renderNotificationCenter();
  playNotificationSound();

  // Desktop native notification if permitted
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification(item.title, {
        body: item.message,
        icon: '/favicon.ico',
      });
    } catch (_) {}
  }
}

function updateNotificationBadgeUI() {
  const badge = document.getElementById('notificationBadge');
  const countBadge = document.getElementById('notificationCountBadge');
  const unread = notificationState.unreadCount;

  if (badge) {
    badge.textContent = unread > 99 ? '99+' : unread;
    badge.classList.toggle('hidden', unread === 0);
  }
  if (countBadge) {
    countBadge.textContent = notificationState.list.length;
  }
}

function toggleNotificationCenter() {
  const dropdown = document.getElementById('notificationDropdown');
  if (!dropdown) return;
  const isHidden = dropdown.classList.contains('hidden');
  if (isHidden) {
    renderNotificationCenter();
    dropdown.classList.remove('hidden');
    // Mark items as read
    notificationState.list.forEach(n => { n.read = true; });
    notificationState.unreadCount = 0;
    try {
      localStorage.setItem('reach_notifications', JSON.stringify(notificationState.list));
    } catch (_) {}
    updateNotificationBadgeUI();
  } else {
    dropdown.classList.add('hidden');
  }
}

function renderNotificationCenter() {
  const listEl = document.getElementById('notificationList');
  if (!listEl) return;

  if (notificationState.list.length === 0) {
    listEl.innerHTML = '<div class="notification-empty">No notifications yet</div>';
    return;
  }

  const icons = {
    success: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    error: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
    warn: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>',
    info: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
  };

  listEl.innerHTML = notificationState.list.map(n => `
    <div class="notification-item ${n.read ? '' : 'unread'}">
      <div class="notification-item-icon ${n.type || 'info'}">${icons[n.type] || icons.info}</div>
      <div class="notification-item-body">
        <div class="notification-item-title">${escapeHtml(n.title)}</div>
        <div class="notification-item-msg">${escapeHtml(n.message)}</div>
        <div class="notification-item-time">${n.date === new Date().toLocaleDateString() ? n.time : n.date + ' ' + n.time}</div>
      </div>
    </div>
  `).join('');
}

function clearAllNotifications() {
  notificationState.list = [];
  notificationState.unreadCount = 0;
  try {
    localStorage.removeItem('reach_notifications');
  } catch (_) {}
  updateNotificationBadgeUI();
  renderNotificationCenter();
}

// --- Sidebar Collapsible Mode ---
function toggleSidebarCollapse() {
  const sidebar = document.getElementById('appSidebar');
  if (!sidebar) return;
  const isCollapsed = sidebar.classList.toggle('collapsed');
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
    if (saved === 'true') {
      sidebar.classList.add('collapsed');
    }
  } catch (_) {}
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

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initSidebarCollapse();
  const validTabs = ['tabAnalytics', 'tabDiscovered', 'tabReview', 'tabSent'];
  const hashToTab = {
    '#analytics': 'tabAnalytics',
    '#discovered': 'tabDiscovered',
    '#review': 'tabReview',
    '#sent': 'tabSent',
    '#others': 'tabSent',
  };

  let startTab = 'tabAnalytics';
  const hash = (window.location.hash || '').toLowerCase();
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

  initNotificationSystem();
  switchTab(startTab);
  initCrawlerControls();
  fetchLocations();
  loadRejectionReasonsFilter();
  loadDashboardData();
  fetchHealth();
  fetchScrapers();
  pollTaskStatus();
  state.healthTimer = setInterval(fetchHealth, 30000);
});

// --- Tab Switching ---
function switchTab(tabId) {
  state.activeTab = tabId;

  try {
    localStorage.setItem('reach_active_tab', tabId);
    const tabToHash = {
      tabAnalytics: '#analytics',
      tabDiscovered: '#discovered',
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
    tabDiscovered: { title: 'Discovered Jobs', breadcrumb: 'Explore, filter, and review crawled job postings' },
    tabReview: { title: 'Review & Drafts', breadcrumb: 'Approve AI cover letters and dispatch outreach' },
    tabSent: { title: 'Sent & History', breadcrumb: 'Track dispatched applications and historical outreach' },
  };
  const meta = pageMeta[tabId] || { title: 'Dashboard', breadcrumb: '' };
  const titleEl = document.getElementById('pageTitleDisplay');
  if (titleEl) titleEl.textContent = meta.title;
  const breadcrumbEl = document.getElementById('pageBreadcrumbDisplay');
  if (breadcrumbEl) breadcrumbEl.textContent = meta.breadcrumb;

  const btnDiscovered = document.getElementById('btnTabDiscovered');
  if (btnDiscovered) btnDiscovered.classList.toggle('active', tabId === 'tabDiscovered');
  const btnReview = document.getElementById('btnTabReview');
  if (btnReview) btnReview.classList.toggle('active', tabId === 'tabReview');
  const btnSent = document.getElementById('btnTabSent');
  if (btnSent) btnSent.classList.toggle('active', tabId === 'tabSent');
  const btnAnalytics = document.getElementById('btnTabAnalytics');
  if (btnAnalytics) btnAnalytics.classList.toggle('active', tabId === 'tabAnalytics');

  const panelDiscovered = document.getElementById('tabDiscovered');
  if (panelDiscovered) panelDiscovered.classList.toggle('hidden', tabId !== 'tabDiscovered');
  const panelReview = document.getElementById('tabReview');
  if (panelReview) panelReview.classList.toggle('hidden', tabId !== 'tabReview');
  const panelSent = document.getElementById('tabSent');
  if (panelSent) panelSent.classList.toggle('hidden', tabId !== 'tabSent');
  const panelAnalytics = document.getElementById('tabAnalytics');
  if (panelAnalytics) panelAnalytics.classList.toggle('hidden', tabId !== 'tabAnalytics');

  fetchStats();

  if (tabId === 'tabDiscovered') {
    fetchDiscoveredPosts();
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

// --- Health Status & Indicators ---
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
      msgEl.textContent = state.health.issues.join(' | ');
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
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

  // Also update corresponding status label in dashboard section if present
  const suffix = elementId.replace('health', '');
  const labelEl = document.getElementById(`healthLabel${suffix}`);
  if (labelEl) {
    labelEl.textContent = serviceData.label || (serviceData.connected ? 'Online' : 'Not Connected');
    labelEl.style.color = serviceData.connected ? '#a7f3d0' : '#fde68a';
  }
}

function dismissSystemAlert() {
  document.getElementById('systemAlertBanner').classList.add('hidden');
}

// --- Dashboard Data Loading ---
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

    // Tab Header Count Badges
    const countDiscEl = document.getElementById('countDiscovered');
    if (countDiscEl && state.activeTab !== 'tabDiscovered') {
      countDiscEl.textContent = discoveredTotal;
    }

    const countRevEl = document.getElementById('countReview');
    if (countRevEl) countRevEl.textContent = draftsReady;

    const countSentEl = document.getElementById('countSent');
    if (countSentEl && state.activeTab !== 'tabSent') {
      countSentEl.textContent = othersCount;
    }

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
  setOthersFilter('SENT');
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
  setExpFilter('ALL');
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    state.config = await res.json();

    const resumePath = state.config.resume_path || '';
    const filename = resumePath.split('/').pop() || 'No Resume Selected';
    document.getElementById('resumeFileName').textContent = filename;
    document.getElementById('resumePill').title = `Active Resume: ${resumePath}`;

    const crawlerLocSelect = document.getElementById('crawlerLocationSelect');
    if (crawlerLocSelect) {
      const savedCrawlerLoc = localStorage.getItem('reach_selected_crawler_location');
      if (savedCrawlerLoc !== null) {
        crawlerLocSelect.value = savedCrawlerLoc;
      } else if (state.config.search_location) {
        crawlerLocSelect.value = state.config.search_location;
      }
    }
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

// --- Resume Replacement Upload ---
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
      document.getElementById('resumeFileName').textContent = data.filename;
      document.getElementById('settingResumePath').value = data.resume_path;
    } else {
      showAlert('Upload Error', data.detail || 'Could not upload resume.');
    }
  } catch (err) {
    showAlert('Upload Error', err.message);
  } finally {
    document.getElementById('resumeFileInput').value = '';
  }
}

// --- TAB 1: Discovered Posts (Paginated Table) ---
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

    const countDiscEl = document.getElementById('countDiscovered');
    if (countDiscEl) countDiscEl.textContent = state.total;

    const discBadge = document.getElementById('discoveredResultsBadge');
    // Clear Filters button: visible whenever any filter is not default/ALL
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
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem;">Error loading posts: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderSkeletonRows() {
  const tbody = document.getElementById('postsTableBody');
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
  tbody.innerHTML = '';

  if (state.posts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 3rem; color: #64748b;">No matching jobs found. Try adjusting filters or scrape today's Infopark jobs.</td></tr>`;
    return;
  }

  state.posts.forEach((post) => {
    const tr = document.createElement('tr');
    tr.id = `row-${post.id}`;
    if (state.selectedIds.has(post.id)) tr.classList.add('selected');

    // Experience badge
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

    // Date cell: dd/mm/yyyy hh:mm AM/PM (1 hr)
    const dateStr = formatPostDateTimeWithRelative(post);
    const dateHtml = `<span class="table-date-badge" title="${escapeHtml(post.posted_date_raw || post.created_at || '')}">${escapeHtml(dateStr || '—')}</span>`;

    // Email cell
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

function copyEmailToClipboard(email) {
  navigator.clipboard.writeText(email).then(() => {
    showToast(`Copied: ${email}`, 'success');
  });
}

function renderPagination() {
  const totalPages = Math.ceil(state.total / state.limit) || 1;
  const startRow = state.total === 0 ? 0 : (state.page - 1) * state.limit + 1;
  const endRow = Math.min(state.page * state.limit, state.total);

  document.getElementById('paginationInfo').textContent = `Showing ${startRow}–${endRow} of ${state.total} posts`;

  const container = document.getElementById('pageButtons');
  container.innerHTML = '';

  // Prev Button
  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '‹';
  prevBtn.disabled = state.page <= 1;
  prevBtn.onclick = () => goToPage(state.page - 1);
  container.appendChild(prevBtn);

  // Page Numbers (up to 5 pages around current)
  const startPage = Math.max(1, state.page - 2);
  const endPage = Math.min(totalPages, state.page + 2);

  for (let p = startPage; p <= endPage; p++) {
    const pBtn = document.createElement('button');
    pBtn.className = `page-btn ${p === state.page ? 'active' : ''}`;
    pBtn.textContent = String(p);
    pBtn.onclick = () => goToPage(p);
    container.appendChild(pBtn);
  }

  // Next Button
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

// --- Filters & Selection ---
function setExpFilter(tier) {
  state.expFilter = tier;
  state.page = 1;
  document.querySelectorAll('#expPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.exp === tier);
  });
  fetchDiscoveredPosts();
}

function applyFilters() {
  state.categoryFilter = document.getElementById('selectCategory').value;
  const genSelect = document.getElementById('selectGenStatus');
  if (genSelect) {
    state.genStatusFilter = genSelect.value;
  }
  const srcSelect = document.getElementById('selectSource');
  if (srcSelect) {
    state.sourceFilter = srcSelect.value;
  }
  const dateSelect = document.getElementById('selectDateFilter');
  if (dateSelect) {
    state.dateFilter = dateSelect.value;
  }
  const locSelect = document.getElementById('selectLocationFilter');
  if (locSelect) {
    state.locationFilter = locSelect.value;
  }
  const discReasonSelect = document.getElementById('selectReasonFilterDiscovered');
  if (discReasonSelect) {
    state.discoveredReason = discReasonSelect.value;
  }
  const sortSelect = document.getElementById('selectSortBy');
  if (sortSelect) {
    state.sortBy = sortSelect.value;
    updateSortIndicators();
  }
  state.searchQuery = document.getElementById('inputSearch').value.trim();
  state.page = 1;
  fetchDiscoveredPosts();
}

function handleSortSelectChange(val) {
  state.sortBy = val;
  updateSortIndicators();
  state.page = 1;
  fetchDiscoveredPosts();
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
  // Reset ALL filters to 'ALL' (show everything)
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
  document.getElementById('selectCategory').value = 'EMAIL_OUTREACH';
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

  if (count > 0) {
    batchBtn.classList.remove('hidden');
    countBadge.textContent = String(count);
  } else {
    batchBtn.classList.add('hidden');
  }
}

// --- TAB 2: Review & Drafts Workspace ---
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

    document.getElementById('reviewQueueCount').textContent = String(state.reviewPosts.length);
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
      document.getElementById('emptyReviewState').classList.remove('hidden');
      document.getElementById('workspacePanel').classList.add('hidden');
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
      const exists = state.reviewPosts.find(p => p.id === state.activeReviewPost.id);
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

  document.getElementById('emptyReviewState').classList.add('hidden');
  document.getElementById('workspacePanel').classList.remove('hidden');

  const authorEl = document.getElementById('reviewAuthorName');
  if (authorEl) {
    authorEl.innerHTML = `${escapeHtml(post.author_name)} ${getSourceBadgeHtml(post)} ${post.location ? `<span class="pill-badge badge-location" title="Location: ${escapeHtml(post.location)}">📍 ${escapeHtml(post.location)}</span>` : ''}`;
  }
  document.getElementById('reviewHeadline').textContent = post.author_headline || 'N/A';
  document.getElementById('reviewTargetEmail').textContent = (post.contact_emails || []).join(', ') || 'None';

  const expLabel = post.is_fresher ? 'Fresher' : (post.raw_experience || `${post.min_experience || 0}+ yrs`);
  document.getElementById('reviewExpPill').textContent = expLabel;

  document.getElementById('reviewFullText').textContent = post.full_text;

  const postLink = document.getElementById('reviewPostLink');
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

  document.getElementById('draftSubject').value = post.generated_subject || '';
  document.getElementById('draftBody').value = post.generated_body || '';

  const resume = state.config.resume_path || '';
  document.getElementById('draftResumeFilename').textContent = resume.split('/').pop() || 'None';
}

async function openPostInReview(postId) {
  switchTab('tabReview');
  let post = state.reviewPosts.find(p => p.id === postId) || state.posts.find(p => p.id === postId);
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

  const subject = document.getElementById('draftSubject').value.trim();
  const body = document.getElementById('draftBody').value.trim();

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

// --- Batch & Direct Sending Functions ---

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
    state.reviewPosts.forEach(p => state.selectedDraftIds.add(p.id));
  } else {
    state.selectedDraftIds.clear();
  }
  updateSelectedDraftsUI();
}

function updateSelectedDraftsUI() {
  const count = state.selectedDraftIds.size;
  const countEl = document.getElementById('selectedDraftsCount');
  const btnBatch = document.getElementById('btnSendBatchDrafts');
  const checkAll = document.getElementById('selectAllDraftsCheckbox');

  if (countEl) countEl.textContent = String(count);
  if (btnBatch) {
    btnBatch.classList.toggle('hidden', count === 0);
  }
  if (checkAll) {
    checkAll.checked = state.reviewPosts.length > 0 && count === state.reviewPosts.length;
    checkAll.indeterminate = count > 0 && count < state.reviewPosts.length;
  }

  document.querySelectorAll('.draft-checkbox').forEach(cb => {
    cb.checked = state.selectedDraftIds.has(cb.value);
  });
}

async function sendActiveDraftDirectly() {
  if (!state.activeReviewPost) return;

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
      showToast('Sending email directly via Gmail...', 'info');
      state.selectedDraftIds.delete(state.activeReviewPost.id);
      updateSelectedDraftsUI();
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Send Direct Error', err.detail || 'Cannot send email directly.');
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

  const confirmed = await showConfirm(
    'Batch Direct Send',
    `Send ${ids.length} selected applications directly via Gmail in a single browser session? Each recipient will be emailed and attached your resume sequentially.`,
    { confirmText: `Send ${ids.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/send-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids })
    });
    if (res.ok) {
      showToast(`Dispatched batch send task for ${ids.length} emails. Monitor progress in live widget.`, 'info');
      state.selectedDraftIds.clear();
      updateSelectedDraftsUI();
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Batch Send Error', err.detail || 'Cannot initiate batch send.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- 1-Click Copy Actions for JD and Draft ---

async function copyJobDescription() {
  const textEl = document.getElementById('reviewFullText');
  const text = textEl ? textEl.textContent : '';
  if (!text) {
    showToast('No job description text to copy.', 'warn');
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.getElementById('btnCopyJd');
    if (btn) {
      btn.classList.add('copied');
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>`;
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span>Copy JD</span>`;
      }, 1800);
    }
    showToast('✓ Job description copied to clipboard', 'success');
  } catch (err) {
    showAlert('Copy Failed', err.message);
  }
}

async function copyEmailDraft() {
  const subject = (document.getElementById('draftSubject')?.value || '').trim();
  const body = (document.getElementById('draftBody')?.value || '').trim();
  if (!subject && !body) {
    showToast('No draft content to copy.', 'warn');
    return;
  }
  const fullDraftText = `Subject: ${subject}\n\n${body}`;
  try {
    await navigator.clipboard.writeText(fullDraftText);
    const btn = document.getElementById('btnCopyDraft');
    if (btn) {
      btn.classList.add('copied');
      btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Copied!</span>`;
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span>Copy Email</span>`;
      }, 1800);
    }
    showToast('✓ Email draft copied to clipboard', 'success');
  } catch (err) {
    showAlert('Copy Failed', err.message);
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
      showToast('Launching Gmail compose in headed Firefox...', 'info');
      startTaskPolling();
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

function openCancelReasonModal(postId, candidateName, defaultReason = '', isSpamMode = false) {
  state.pendingCancelPostId = postId;
  state.isSpamCancelMode = !!isSpamMode;

  // Resolve candidate name if not provided
  if (!candidateName) {
    const p = (state.discoveredPosts || []).find(item => item.id === postId)
           || (state.posts || []).find(item => item.id === postId)
           || (state.reviewPosts || []).find(item => item.id === postId);
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

  // Update chip active states
  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach(c => {
    const chipVal = c.getAttribute('data-reason') || c.textContent.trim();
    c.classList.toggle('active', !!(defaultReason && chipVal.toLowerCase() === defaultReason.toLowerCase()));
  });

  document.getElementById('cancelReasonModal')?.classList.remove('hidden');
  setTimeout(() => {
    input?.focus();
    if (defaultReason) input?.select();
  }, 50);
}

function closeCancelReasonModal() {
  state.pendingCancelPostId = null;
  state.isSpamCancelMode = false;
  document.getElementById('cancelReasonModal')?.classList.add('hidden');
}

function selectPreMadeReason(reason) {
  const input = document.getElementById('inputCancelReason');
  if (input) {
    input.value = reason;
    input.focus();
  }
  document.querySelectorAll('#cancelReasonModal .reason-chip').forEach(chip => {
    const chipVal = chip.getAttribute('data-reason') || chip.textContent.trim();
    chip.classList.toggle('active', chipVal.toLowerCase() === reason.toLowerCase());
  });
}

async function confirmCancelWithReason() {
  const postId = state.pendingCancelPostId;
  if (!postId) return;
  const input = document.getElementById('inputCancelReason');
  const reason = (input?.value || '').trim() || (state.isSpamCancelMode ? 'Scam' : 'Unspecified');

  try {
    const endpoint = (state.isSpamCancelMode || reason.toLowerCase() === 'scam' || reason.toLowerCase().includes('spam'))
      ? `/api/posts/${postId}/spam`
      : `/api/posts/${postId}/reject`;

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason })
    });
    if (res.ok) {
      showToast(`✕ Application cancelled: ${reason}`, 'info');
      closeCancelReasonModal();
      if (state.activeReviewPost && state.activeReviewPost.id === postId) {
        state.activeReviewPost = null;
      }
      await loadDashboardData();

      // If in Review workspace, move to next or show empty state
      if (state.currentTab === 'review' || (state.reviewPosts && state.reviewPosts.length > 0)) {
        const remaining = state.reviewPosts.filter(p => p.id !== postId);
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

// Mail Return Prompt: Detect window focus after returning from Gmail compose
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

function setOthersFilter(filter) {
  state.othersFilter = filter;
  state.sentPage = 1;
  document.querySelectorAll('#othersPills .pill').forEach(pill => {
    pill.classList.toggle('active', pill.dataset.others === filter);
  });
  fetchSentPosts();
}

// --- TAB 3: Others (Sent & Cancelled Applications History) ---
let sentSearchDebounce = null;
function handleSearchSentKeyUp(e) {
  if (e.key === 'Enter') {
    state.searchSent = (document.getElementById('inputSearchSent')?.value || '').trim();
    state.sentPage = 1;
    fetchSentPosts();
  } else {
    clearTimeout(sentSearchDebounce);
    sentSearchDebounce = setTimeout(() => {
      state.searchSent = (document.getElementById('inputSearchSent')?.value || '').trim();
      state.sentPage = 1;
      fetchSentPosts();
    }, 300);
  }
}

function clearSentFilters() {
  state.othersFilter = 'ALL';
  document.querySelectorAll('#othersPills .pill').forEach((pill) => {
    pill.classList.toggle('active', pill.dataset.others === 'ALL');
  });

  state.othersReason = 'ALL';
  const reasonSel = document.getElementById('selectReasonFilter');
  if (reasonSel) reasonSel.value = 'ALL';

  state.searchSent = '';
  const searchInput = document.getElementById('inputSearchSent');
  if (searchInput) searchInput.value = '';

  state.sentPage = 1;
  fetchSentPosts();
}

async function loadRejectionReasonsFilter(selectedReason = null) {
  try {
    const res = await fetch('/api/reasons');
    if (!res.ok) return;
    const data = await res.json();
    const items = data.counts || (data.reasons || []).map(r => ({ reason: r, count: null }));

    // Update Sent / Cancelled tab reason filter
    const sentSelect = document.getElementById('selectReasonFilter');
    if (sentSelect) {
      const currentSentVal = selectedReason || state.othersReason || 'ALL';
      let html = '<option value="ALL">All Reasons</option>';
      items.forEach(item => {
        const countTxt = item.count !== null && item.count !== undefined ? ` (${item.count})` : '';
        const isSel = item.reason === currentSentVal ? 'selected' : '';
        html += `<option value="${escapeHtml(item.reason)}" ${isSel}>${escapeHtml(item.reason)}${countTxt}</option>`;
      });
      sentSelect.innerHTML = html;
      sentSelect.value = currentSentVal;
    }

    // Update Discovered tab reason filter
    const discSelect = document.getElementById('selectReasonFilterDiscovered');
    if (discSelect) {
      const currentDiscVal = state.discoveredReason || 'ALL';
      let html = '<option value="ALL">All Reasons</option>';
      items.forEach(item => {
        const countTxt = item.count !== null && item.count !== undefined ? ` (${item.count})` : '';
        const isSel = item.reason === currentDiscVal ? 'selected' : '';
        html += `<option value="${escapeHtml(item.reason)}" ${isSel}>${escapeHtml(item.reason)}${countTxt}</option>`;
      });
      discSelect.innerHTML = html;
      discSelect.value = currentDiscVal;
    }

    if (selectedReason) {
      state.othersReason = selectedReason;
    }
  } catch (e) {
    console.error('Error loading rejection reasons:', e);
  }
}

function applySentReasonFilter() {
  const select = document.getElementById('selectReasonFilter');
  if (select) {
    state.othersReason = select.value;
  }
  state.sentPage = 1;
  fetchSentPosts();
}

function filterOthersByReason(reason) {
  switchTab('tabSent');
  setOthersFilter('REJECTED');
  loadRejectionReasonsFilter(reason).then(() => {
    state.othersReason = reason;
    const select = document.getElementById('selectReasonFilter');
    if (select) select.value = reason;
    state.sentPage = 1;
    fetchSentPosts();
  });
}

async function fetchSentPosts() {
  const tbody = document.getElementById('sentTableBody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem;">Loading history...</td></tr>';

  try {
    const statusVal = state.othersFilter === 'ALL' ? 'OTHERS' : state.othersFilter;
    const params = new URLSearchParams({
      status: statusVal,
      order_by: 'updated_at',
      limit: String(state.sentLimit),
      offset: String((state.sentPage - 1) * state.sentLimit),
    });
    if (state.searchSent) {
      params.append('search', state.searchSent);
    }
    if (state.othersReason && state.othersReason !== 'ALL') {
      params.append('reason', state.othersReason);
    }

    const res = await fetch(`/api/posts?${params.toString()}`);
    const data = await res.json();
    state.sentPosts = data.posts || [];
    state.sentTotal = data.total !== undefined ? data.total : (data.posts ? data.posts.length : 0);

    const countSentEl = document.getElementById('countSent');
    if (countSentEl) countSentEl.textContent = state.sentTotal;

    const sentBadge = document.getElementById('sentResultsBadge');
    const isSentFiltered = state.othersFilter !== 'ALL' || (state.searchSent && state.searchSent.trim() !== '') || (state.othersReason && state.othersReason !== 'ALL');
    if (sentBadge) {
      if (isSentFiltered) {
        sentBadge.textContent = `${state.sentTotal} result${state.sentTotal === 1 ? '' : 's'}`;
        sentBadge.classList.remove('hidden');
      } else {
        sentBadge.classList.add('hidden');
      }
    }

    const clearSentBtn = document.getElementById('btnClearSentFilters');
    if (clearSentBtn) {
      clearSentBtn.classList.toggle('hidden', !isSentFiltered);
    }

    tbody.innerHTML = '';
    if (state.sentPosts.length === 0) {
      const emptyMsg = state.searchSent
        ? `No applications matching "${escapeHtml(state.searchSent)}" found.`
        : 'No applications in Others history yet.';
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 3rem; color: #64748b;">${emptyMsg}</td></tr>`;
      renderSentPagination();
      return;
    }

    state.sentPosts.forEach((post) => {
      const tr = document.createElement('tr');
      tr.className = 'clickable-card sent-table-row';
      tr.onclick = (e) => {
        if (!e.target.closest('button, a, input')) {
          openPostModal(post.id);
        }
      };

      const email = (post.contact_emails && post.contact_emails[0]) || 'N/A';
      const updatedDate = formatDateTime(post.sent_at || post.updated_at || post.created_at);

      const isSent = post.status === 'SENT';
      const isRejected = post.status === 'REJECTED';

      let statusBadge = '';
      if (isSent) {
        statusBadge = `<span class="badge-status-sent" style="display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>Sent</span>`;
      } else if (isRejected) {
        statusBadge = `<span class="badge-status-rejected" style="display: inline-flex; align-items: center; gap: 0.3rem;"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Cancelled</span>`;
        if (post.rejection_reason) {
          statusBadge += `<span class="badge-rejection-reason" title="${escapeHtml(post.rejection_reason)}">${escapeHtml(post.rejection_reason)}</span>`;
        }
      } else {
        statusBadge = `<span class="pill-badge badge-none">${escapeHtml(post.status)}</span>`;
      }

      const noteOrSubject = escapeHtml(post.generated_subject || (post.full_text ? post.full_text.slice(0, 65) + '...' : '—'));

      tr.innerHTML = `
        <td>
          <div class="recruiter-cell" onclick="openPostModal('${post.id}')" title="Click to view full application details" style="cursor: pointer;">
            <div style="display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap;">
              <strong>${escapeHtml(post.author_name)}</strong>
              ${getSourceBadgeHtml(post)}
              ${post.location ? `<span class="pill-badge badge-location" style="display: inline-flex; align-items: center; gap: 0.2rem;" title="Location: ${escapeHtml(post.location)}"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>${escapeHtml(post.location)}</span>` : ''}
            </div>
            <span class="recruiter-headline">${escapeHtml(post.author_headline || '')}</span>
          </div>
        </td>
        <td><code>${escapeHtml(email)}</code></td>
        <td>
          <div style="font-size: 0.78rem; color: var(--text-dim); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer;" title="Click to view details: ${noteOrSubject}" onclick="openPostModal('${post.id}')">
            ${noteOrSubject}
          </div>
        </td>
        <td>${statusBadge}</td>
        <td style="font-size: 0.76rem; color: var(--text-muted); white-space: nowrap;">${updatedDate}</td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end; gap: 0.35rem;">
            ${
              post.post_url && !post.post_url.startsWith('manual://') && !post.post_url.startsWith('direct://')
                ? `<a href="${post.post_url}" target="_blank" class="icon-btn sm" title="Open source post">
                     <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                   </a>`
                : ''
            }
            <button class="btn btn-outline btn-sm" onclick="openPostModal('${post.id}')" title="View details">
              <span>View</span>
            </button>
            <button class="btn btn-outline btn-sm" onclick="revertPostToDraft('${post.id}')" title="Restore back to active drafts/discovered">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>
              <span>Restore</span>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    renderSentPagination();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem;">Error: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderSentPagination() {
  const totalPages = Math.ceil(state.sentTotal / state.sentLimit) || 1;
  const startRow = state.sentTotal === 0 ? 0 : (state.sentPage - 1) * state.sentLimit + 1;
  const endRow = Math.min(state.sentPage * state.sentLimit, state.sentTotal);

  const info = document.getElementById('sentPaginationInfo');
  if (info) {
    info.textContent = `Showing ${startRow}–${endRow} of ${state.sentTotal} applications`;
  }

  const container = document.getElementById('sentPageButtons');
  if (!container) return;
  container.innerHTML = '';

  // Prev Button
  const prevBtn = document.createElement('button');
  prevBtn.className = 'page-btn';
  prevBtn.textContent = '‹';
  prevBtn.disabled = state.sentPage <= 1;
  prevBtn.onclick = () => goToSentPage(state.sentPage - 1);
  container.appendChild(prevBtn);

  // Page Numbers (up to 5 pages around current)
  const startPage = Math.max(1, state.sentPage - 2);
  const endPage = Math.min(totalPages, state.sentPage + 2);

  for (let p = startPage; p <= endPage; p++) {
    const pBtn = document.createElement('button');
    pBtn.className = `page-btn ${p === state.sentPage ? 'active' : ''}`;
    pBtn.textContent = String(p);
    pBtn.onclick = () => goToSentPage(p);
    container.appendChild(pBtn);
  }

  // Next Button
  const nextBtn = document.createElement('button');
  nextBtn.className = 'page-btn';
  nextBtn.textContent = '›';
  nextBtn.disabled = state.sentPage >= totalPages;
  nextBtn.onclick = () => goToSentPage(state.sentPage + 1);
  container.appendChild(nextBtn);
}

function goToSentPage(p) {
  state.sentPage = p;
  fetchSentPosts();
}

function changeSentRowsPerPage(val) {
  state.sentLimit = parseInt(val, 10) || 25;
  state.sentPage = 1;
  fetchSentPosts();
}

async function revertPostToDraft(postId) {
  const confirmed = await showConfirm(
    'Revert Sent Application?',
    'This will return this application back to the Review & Drafts workspace, allowing you to edit the email draft and re-send or modify it.',
    { confirmText: 'Revert to Draft' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/posts/${postId}/revert`, { method: 'POST' });
    if (res.ok) {
      showToast('Application reverted back to Review & Drafts', 'success');
      await fetchSentPosts();
      await fetchReviewPosts();
      switchTab('tabReview');
      const target = state.reviewPosts.find(p => p.id === postId);
      if (target) selectReviewPost(target);
    } else {
      const err = await res.json();
      showAlert('Error', err.detail || 'Failed to revert post.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Automation Triggers ---
async function triggerInfoparkScrape() {
  const confirmed = await showConfirm(
    'Scrape Today\'s Infopark Jobs',
    'Fetch today\'s job postings directly from infopark.in/companies-job? The scraper visits each details page, extracting the complete job description (JD) and company recruiter emails.',
    { confirmText: 'Scrape Infopark' }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/scrape/infopark', { method: 'POST' });
    if (res.ok) {
      showToast('Infopark scraper started', 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Scraper Busy', err.detail || 'Cannot start scraper.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

function handleCrawlerSourceChange() {
  const sourceSelect = document.getElementById('crawlerSourceSelect');
  const locSelect = document.getElementById('crawlerLocationSelect');
  if (!sourceSelect || !locSelect) return;
  const sourceId = sourceSelect.value;
  if (sourceId === 'infopark') {
    locSelect.disabled = true;
    locSelect.title = "Infopark crawler discovers jobs in Kochi, Kerala";
  } else {
    locSelect.disabled = false;
    locSelect.title = "Target Job Location / Area";
  }
}

function initCrawlerControls() {
  const locSelect = document.getElementById('crawlerLocationSelect');
  if (locSelect) {
    const saved = localStorage.getItem('reach_selected_crawler_location');
    if (saved !== null) {
      locSelect.value = saved;
    }
    locSelect.onchange = () => {
      localStorage.setItem('reach_selected_crawler_location', locSelect.value);
    };
  }
  handleCrawlerSourceChange();
}

async function fetchScrapers() {
  try {
    const res = await fetch('/api/scrapers');
    if (!res.ok) return;
    const scrapers = await res.json();
    const select = document.getElementById('crawlerSourceSelect');
    if (select && scrapers && scrapers.length > 0) {
      const saved = localStorage.getItem('reach_selected_crawler_source');
      select.innerHTML = scrapers.map(s => `
        <option value="${escapeHtml(s.id)}" ${saved === s.id ? 'selected' : ''}>
          ${escapeHtml(s.icon || '🌐')} ${escapeHtml(s.name)}
        </option>
      `).join('');
      select.onchange = () => {
        localStorage.setItem('reach_selected_crawler_source', select.value);
        handleCrawlerSourceChange();
      };
      handleCrawlerSourceChange();
    }
  } catch (err) {
    console.error('Error fetching scrapers:', err);
  }
}

async function fetchLocations() {
  try {
    const res = await fetch('/api/locations');
    if (!res.ok) return;
    const data = await res.json();
    const savedLocations = data.locations || [];
    const presets = data.presets || [];

    const filterSelect = document.getElementById('selectLocationFilter');
    if (!filterSelect) return;

    const currentVal = state.locationFilter || 'ALL';

    let html = `<option value="ALL">All Locations</option>`;
    if (savedLocations.length > 0) {
      html += `<optgroup label="Locations with Discovered Posts">`;
      savedLocations.forEach((loc) => {
        html += `<option value="${escapeHtml(loc)}" ${currentVal === loc ? 'selected' : ''}>📍 ${escapeHtml(loc)}</option>`;
      });
      html += `</optgroup>`;
    }

    const remainingPresets = presets.filter((p) => !savedLocations.includes(p));
    if (remainingPresets.length > 0) {
      html += `<optgroup label="Major Job Hubs">`;
      remainingPresets.forEach((loc) => {
        html += `<option value="${escapeHtml(loc)}" ${currentVal === loc ? 'selected' : ''}>${escapeHtml(loc)}</option>`;
      });
      html += `</optgroup>`;
    }

    filterSelect.innerHTML = html;
    filterSelect.value = currentVal;
  } catch (err) {
    console.error('Error loading locations:', err);
  }
}

async function triggerSelectedCrawl() {
  const select = document.getElementById('crawlerSourceSelect');
  const locSelect = document.getElementById('crawlerLocationSelect');
  const sourceId = select ? select.value : 'linkedin';
  const sourceName = select ? select.options[select.selectedIndex]?.text.trim() : 'Selected Source';
  const selectedLocation = (locSelect && !locSelect.disabled) ? (locSelect.value || '').trim() : '';

  let searchDetails = '';
  if (sourceId === 'linkedin') {
    const baseQuery = (state.config && state.config.search_query) || 'Full stack developer';
    if (selectedLocation) {
      searchDetails = `\n\nSearch Query: "${baseQuery} ${selectedLocation}"\nSaved Location: "${selectedLocation}"`;
    } else {
      searchDetails = `\n\nSearch Query: "${baseQuery}" (No specific location appended)`;
    }
  } else if (sourceId === 'infopark') {
    searchDetails = `\n\nSource: Infopark Kochi Portal\nSaved Location: "Kochi"`;
  }

  const confirmed = await showConfirm(
    `Start Crawling: ${sourceName}`,
    `Launch the ${sourceName} scraper? It will run visibly with a 90-second inactivity watchdog and automatically save discovered jobs to the database.${searchDetails}`,
    { confirmText: `Start Crawl` }
  );
  if (!confirmed) return;

  try {
    const payload = { source: sourceId };
    if (selectedLocation && sourceId === 'linkedin') {
      payload.location = selectedLocation;
    }
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast(`${sourceName} crawler started`, 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Scraper Busy', err.detail || 'Cannot start scraper.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function triggerLinkedInScrape() {
  const select = document.getElementById('crawlerSourceSelect');
  if (select) select.value = 'linkedin';
  await triggerSelectedCrawl();
}

function markPostAsSpam(postId) {
  const p = (state.discoveredPosts || []).find(item => item.id === postId)
         || (state.posts || []).find(item => item.id === postId);
  openCancelReasonModal(postId, p?.author_name || '', 'Scam', true);
}

function cancelDiscoveredPost(postId, authorName) {
  const p = (state.discoveredPosts || []).find(item => item.id === postId)
         || (state.posts || []).find(item => item.id === postId);
  openCancelReasonModal(postId, authorName || p?.author_name || '', '', false);
}

function markActivePostSpam() {
  const active = state.activeReviewPost || (state.reviewPosts && state.reviewPosts.length > 0 ? state.reviewPosts[0] : null);
  if (!active) {
    showToast('No active post selected in Review workspace', 'warning');
    return;
  }
  state.activeReviewPost = active;
  state.activePostId = active.id;
  openCancelReasonModal(active.id, active.author_name || 'Job Post', 'Scam', true);
}

function markPostModalSpam() {
  const postId = state.currentModalPostId;
  if (!postId) return;
  const p = (state.posts && state.posts.find(item => item.id === postId)) ||
            (state.reviewPosts && state.reviewPosts.find(item => item.id === postId)) ||
            (state.sentPosts && state.sentPosts.find(item => item.id === postId));
  closePostModal();
  openCancelReasonModal(postId, p?.author_name || 'Job Post', 'Scam', true);
}

async function generateSingleChatGPT(postId) {
  try {
    const res = await fetch(`/api/generate-email/${postId}`, { method: 'POST' });
    if (res.ok) {
      showToast('ChatGPT email generation launched in headed Firefox', 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail);
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

async function generateBatchChatGPT() {
  const ids = Array.from(state.selectedIds);
  if (ids.length === 0) return;

  const confirmed = await showConfirm(
    'Generate Outreach Emails',
    `Generate tailored outreach emails for ${ids.length} selected post(s) using ChatGPT in headed Firefox?`,
    { confirmText: `Generate ${ids.length} Emails` }
  );
  if (!confirmed) return;

  try {
    const res = await fetch('/api/generate-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_ids: ids }),
    });

    if (res.ok) {
      state.selectedIds.clear();
      updateSelectedCountUI();
      showToast(`Batch generation started for ${ids.length} posts`, 'info');
      startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail);
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Real-Data Task Polling & Animations ---
function startTaskPolling() {
  if (state.pollingTimer) clearInterval(state.pollingTimer);
  state.pollingTimer = setInterval(pollTaskStatus, 1500);
  pollTaskStatus();
}

function stopTaskPolling() {
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
    state.pollingTimer = null;
  }
}

async function pollTaskStatus() {
  try {
    const res = await fetch('/api/tasks/status');
    if (!res.ok) return;
    const task = await res.json();

    const card = document.getElementById('liveTaskCard');
    const titleEl = document.getElementById('taskTitle');
    const subEl = document.getElementById('taskSubtitle');
    const countEl = document.getElementById('taskCounterPill');
    const fillEl = document.getElementById('taskProgressFill');
    const logsEl = document.getElementById('logsStream');

    if (task.status === 'running') {
      if (!state.pollingTimer) {
        state.pollingTimer = setInterval(pollTaskStatus, 1500);
      }
      card.classList.remove('hidden');
      titleEl.textContent = task.task_name;
      subEl.textContent = task.current_step;

      const total = task.total_items || 1;
      const done = task.completed_items || 0;
      countEl.textContent = `${done} / ${total}`;

      const pct = Math.min(100, Math.round((done / total) * 100));
      fillEl.style.width = `${Math.max(5, pct)}%`;

      logsEl.innerHTML = (task.logs || []).map(l => `<div>${escapeHtml(l)}</div>`).join('');
      logsEl.scrollTop = logsEl.scrollHeight;

      // Reset handled task event key while running
      state.lastHandledTaskKey = null;
    } else if (task.status === 'completed' || task.status === 'error') {
      const taskEventKey = `${task.task_name}_${task.started_at}_${task.status}`;
      if (state.lastHandledTaskKey === taskEventKey) {
        // Already handled! Stop polling and do not reload again
        stopTaskPolling();
        return;
      }
      state.lastHandledTaskKey = taskEventKey;
      stopTaskPolling();

      if (task.status === 'completed') {
        fillEl.style.width = '100%';
        let notifMsg = `${task.task_name || 'Automation'} completed successfully.`;
        if (task.crawl_stats) {
          const s = task.crawl_stats;
          subEl.textContent = `Crawled ${s.total_crawled || 0} posts • Added ${s.newly_added || 0} new • Skipped ${s.skipped_already_added || 0} existing`;
          notifMsg = `Crawled ${s.total_crawled || 0} posts: ${s.newly_added || 0} new jobs added, ${s.skipped_already_added || 0} existing skipped.`;
          showCrawlSummaryModal(task.task_name, s);
        } else {
          subEl.textContent = 'Completed successfully';
          if (task.completed_items) {
            notifMsg = `${task.task_name || 'Task'} finished: ${task.completed_items}/${task.total_items || task.completed_items} processed.`;
          }
        }

        sendAppNotification({
          title: task.task_name || 'Task Complete',
          message: notifMsg,
          type: 'success',
        });

        setTimeout(() => {
          card.classList.add('hidden');
          fetch('/api/tasks/clear', { method: 'POST' }).catch(() => {});
          loadDashboardData();
        }, task.crawl_stats ? 3000 : 1500);
      } else {
        const firstLine = (task.error || 'Operation failed').split('\n')[0];
        subEl.textContent = `Failed: ${firstLine}`;

        sendAppNotification({
          title: task.task_name || 'Task Failed',
          message: firstLine,
          type: 'error',
        });

        showSnackbar({
          title: `Task Error: ${task.task_name || 'Automation'}`,
          message: firstLine,
          details: task.error,
          type: 'error',
        });
        showCenterAlert(
          `Automation Stopped: ${task.task_name || 'Task'}`,
          task.error || 'The automation task encountered an issue and stopped.'
        );
        setTimeout(() => {
          card.classList.add('hidden');
          fetch('/api/tasks/clear', { method: 'POST' }).catch(() => {});
          loadDashboardData();
        }, 2000);
      }
    } else {
      card.classList.add('hidden');
      stopTaskPolling();
    }
  } catch (err) {
    console.error('Task poll error:', err);
    stopTaskPolling();
  }
}

function showCrawlSummaryModal(taskName, stats) {
  const modal = document.getElementById('crawlSummaryModal');
  const title = document.getElementById('crawlSummaryTitle');
  const grid = document.getElementById('crawlSummaryGrid');
  if (!modal || !grid) return;

  title.textContent = `${taskName || 'Crawler'} Summary`;

  const total = stats.total_crawled !== undefined ? stats.total_crawled : 0;
  const added = stats.newly_added !== undefined ? stats.newly_added : 0;
  const emailOutreach = stats.new_email_outreach !== undefined ? stats.new_email_outreach : 0;
  const draftPortal = stats.new_draft_portal !== undefined ? stats.new_draft_portal : 0;
  const skippedInDb = stats.skipped_already_added !== undefined ? stats.skipped_already_added : 0;
  const skippedOther = stats.skipped_other !== undefined ? stats.skipped_other : 0;

  grid.innerHTML = `
    <div class="crawl-stat-card" style="border-left: 3px solid #38bdf8;">
      <div class="crawl-stat-val" style="color: #38bdf8;">${total}</div>
      <div class="crawl-stat-lbl">Total Posts Scanned</div>
    </div>
    <div class="crawl-stat-card" style="border-left: 3px solid #34d399;">
      <div class="crawl-stat-val" style="color: #34d399;">${added}</div>
      <div class="crawl-stat-lbl">Newly Added Jobs</div>
    </div>
    <div class="crawl-stat-card" style="border-left: 3px solid #818cf8;">
      <div class="crawl-stat-val" style="color: #818cf8;">${emailOutreach}</div>
      <div class="crawl-stat-lbl">Direct Email Outreach</div>
    </div>
    <div class="crawl-stat-card" style="border-left: 3px solid #f59e0b;">
      <div class="crawl-stat-val" style="color: #f59e0b;">${draftPortal}</div>
      <div class="crawl-stat-lbl">Drafts & Portals</div>
    </div>
    <div class="crawl-stat-card" style="border-left: 3px solid #94a3b8;">
      <div class="crawl-stat-val" style="color: #94a3b8;">${skippedInDb}</div>
      <div class="crawl-stat-lbl">Skipped (Already in DB)</div>
    </div>
    <div class="crawl-stat-card" style="border-left: 3px solid #f43f5e;">
      <div class="crawl-stat-val" style="color: #f43f5e;">${skippedOther}</div>
      <div class="crawl-stat-lbl">Skipped (No Match / Filtered)</div>
    </div>
  `;

  modal.classList.remove('hidden');
}

function closeCrawlSummaryModal() {
  const modal = document.getElementById('crawlSummaryModal');
  if (modal) modal.classList.add('hidden');
}

function toggleTaskLogs() {
  state.showLogs = !state.showLogs;
  document.getElementById('taskLogsDrawer').classList.toggle('hidden', !state.showLogs);
}

// --- Post Full Text Modal ---
function openPostModal(postId) {
  state.currentModalPostId = postId;
  const post = (state.posts && state.posts.find(p => p.id === postId)) ||
               (state.reviewPosts && state.reviewPosts.find(p => p.id === postId)) ||
               (state.sentPosts && state.sentPosts.find(p => p.id === postId));
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

  const authorBadgeHtml = getSourceBadgeHtml(post);
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

  // Status Banner (for Sent / Cancelled / Scam / Potential Scam applications)
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
        revertPostToDraft(post.id);
      };
    } else {
      restoreBtn.classList.add('hidden');
    }
  }

  const linkEl = document.getElementById('modalPostLink');
  if (linkEl) {
    if (post.post_url && !post.post_url.startsWith('manual://')) {
      linkEl.href = post.post_url;
      linkEl.style.display = 'inline-flex';
      linkEl.textContent = post.post_url.includes('infopark.in') ? 'View on Infopark ↗' : 'View on LinkedIn ↗';
    } else {
      linkEl.style.display = 'none';
    }
  }
  document.getElementById('modalPostContent').textContent = post.full_text;
  document.getElementById('postModal').classList.remove('hidden');
}

function closePostModal() {
  document.getElementById('postModal').classList.add('hidden');
}

// --- Manual JD Entry Modal ---
function openAddJdModal() {
  document.getElementById('manualJdTitle').value = '';
  document.getElementById('manualJdCompany').value = '';
  if (document.getElementById('manualJdLocation')) document.getElementById('manualJdLocation').value = '';
  document.getElementById('manualJdContent').value = '';
  document.getElementById('modalAddJd').classList.remove('hidden');
}

function closeAddJdModal() {
  document.getElementById('modalAddJd').classList.add('hidden');
}

async function submitManualJd() {
  const content = (document.getElementById('manualJdContent').value || '').trim();
  if (!content) {
    showAlert('Missing Content', 'Please paste the job description text.');
    return;
  }
  const title = (document.getElementById('manualJdTitle').value || '').trim();
  const company = (document.getElementById('manualJdCompany').value || '').trim();
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
      loadDashboardData();
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
      startTaskPolling();
      loadDashboardData();
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
  document.getElementById('settingResumePath').value = state.config.resume_path || '';
  document.getElementById('settingSearchQuery').value = state.config.search_query || '';
  const settingLoc = document.getElementById('settingSearchLocation');
  if (settingLoc) settingLoc.value = state.config.search_location || '';
  document.getElementById('settingChatGptUrl').value = state.config.chatgpt_url || '';
  document.getElementById('settingsModal').classList.remove('hidden');
}

function closeSettingsModal() {
  document.getElementById('settingsModal').classList.add('hidden');
}

async function saveSettings() {
  const payload = {
    resume_path: document.getElementById('settingResumePath').value.trim(),
    search_query: document.getElementById('settingSearchQuery').value.trim(),
    search_location: document.getElementById('settingSearchLocation') ? document.getElementById('settingSearchLocation').value.trim() : '',
    chatgpt_url: document.getElementById('settingChatGptUrl').value.trim(),
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeSettingsModal();
      await fetchSettings();
      showToast('✓ Settings updated successfully', 'success');
    } else {
      showAlert('Save Error', 'Could not save settings.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// --- Utilities ---
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatRelativeLabel(raw) {
  if (!raw) return '';
  const trimmed = raw.trim();
  const match = trimmed.match(/^(\d+)\s*([a-zA-Z]+)$/);
  if (!match) return trimmed;
  const num = parseInt(match[1], 10);
  const unit = match[2].toLowerCase();
  if (unit === 'h' || unit.startsWith('hr')) {
    return num === 1 ? '1 hr' : `${num} hrs`;
  }
  if (unit === 'm' || unit.startsWith('min')) {
    return num === 1 ? '1 min' : `${num} mins`;
  }
  if (unit === 'd' || unit.startsWith('day')) {
    return num === 1 ? '1 day' : `${num} days`;
  }
  if (unit === 'w' || unit.startsWith('wk') || unit.startsWith('week')) {
    return num === 1 ? '1 week' : `${num} weeks`;
  }
  if (unit === 'mo' || unit.startsWith('mon') || unit.startsWith('month')) {
    return num === 1 ? '1 mo' : `${num} mos`;
  }
  if (unit === 'y' || unit.startsWith('yr') || unit.startsWith('year')) {
    return num === 1 ? '1 yr' : `${num} yrs`;
  }
  return trimmed;
}

function formatPostDateTimeWithRelative(post) {
  if (!post) return '—';

  let baseDate = null;
  if (post.created_at) {
    baseDate = new Date(post.created_at);
  }
  if (!baseDate || isNaN(baseDate.getTime())) {
    baseDate = new Date();
  }

  const raw = (post.posted_date_raw || '').trim();
  let computedDate = new Date(baseDate.getTime());
  let relativeLabel = '';

  if (raw) {
    // If raw is already a date like "20-09-2026" or "2026-09-20"
    if (/^\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}/.test(raw)) {
      relativeLabel = '';
    } else {
      const match = raw.match(/^(\d+)\s*([a-zA-Z]+)$/);
      if (match) {
        const val = parseInt(match[1], 10);
        const unit = match[2].toLowerCase();
        let msOffset = 0;

        if (unit.startsWith('m') && !unit.startsWith('mo')) {
          msOffset = val * 60 * 1000;
        } else if (unit.startsWith('h')) {
          msOffset = val * 60 * 60 * 1000;
        } else if (unit.startsWith('d')) {
          msOffset = val * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('w')) {
          msOffset = val * 7 * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('mo')) {
          msOffset = val * 30 * 24 * 60 * 60 * 1000;
        } else if (unit.startsWith('y')) {
          msOffset = val * 365 * 24 * 60 * 60 * 1000;
        }

        if (msOffset > 0) {
          computedDate = new Date(baseDate.getTime() - msOffset);
        }
        relativeLabel = formatRelativeLabel(raw);
      } else {
        relativeLabel = raw;
      }
    }
  }

  const day = String(computedDate.getDate()).padStart(2, '0');
  const month = String(computedDate.getMonth() + 1).padStart(2, '0');
  const year = computedDate.getFullYear();

  let hours = computedDate.getHours();
  const minutes = String(computedDate.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const hoursStr = String(hours).padStart(2, '0');

  const formattedDate = `${day}/${month}/${year} ${hoursStr}:${minutes} ${ampm}`;
  if (relativeLabel) {
    return `${formattedDate} (${relativeLabel})`;
  }
  return formattedDate;
}

function formatDateTime(dateVal) {
  if (!dateVal) return '—';
  const d = new Date(dateVal);
  if (isNaN(d.getTime())) return String(dateVal);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  let hours = d.getHours();
  const minutes = String(d.getMinutes()).padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const hoursStr = String(hours).padStart(2, '0');
  return `${day}/${month}/${year} ${hoursStr}:${minutes} ${ampm}`;
}

// ==========================================================================
// Analytics & Trend Graph Engine
// ==========================================================================

const chartDefaultOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#94a3b8',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: '500' }
      }
    },
    tooltip: {
      backgroundColor: '#0f172a',
      titleColor: '#f8fafc',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(255, 255, 255, 0.12)',
      borderWidth: 1,
      padding: 10,
      boxPadding: 4,
      usePointStyle: true,
    }
  }
};

function renderDailyAppliedChart(timeline) {
  const canvas = document.getElementById('chartDailyApplied');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.dailyApplied) {
    state.charts.dailyApplied.destroy();
  }
  const ctx = canvas.getContext('2d');
  
  const gradient = ctx.createLinearGradient(0, 0, 0, 260);
  gradient.addColorStop(0, 'rgba(16, 185, 129, 0.35)');
  gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

  state.charts.dailyApplied = new Chart(ctx, {
    type: 'line',
    data: {
      labels: timeline.map(d => d.label),
      datasets: [{
        label: 'Applications Applied',
        data: timeline.map(d => d.count),
        borderColor: '#10b981',
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#10b981',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1.5,
        pointRadius: timeline.length > 30 ? 2 : 4,
        pointHoverRadius: 6,
      }]
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        }
      }
    }
  });
}

function renderDailyScrapedChart(timeline) {
  const canvas = document.getElementById('chartDailyScraped');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.dailyScraped) {
    state.charts.dailyScraped.destroy();
  }
  const ctx = canvas.getContext('2d');

  state.charts.dailyScraped = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: timeline.map(d => d.label),
      datasets: [{
        label: 'JDs Discovered',
        data: timeline.map(d => d.count),
        backgroundColor: 'rgba(14, 165, 233, 0.75)',
        hoverBackgroundColor: '#38bdf8',
        borderRadius: 4,
      }]
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        }
      }
    }
  });
}

function renderStatusBreakdownChart(statuses) {
  const canvas = document.getElementById('chartStatusBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.statusBreakdown) {
    state.charts.statusBreakdown.destroy();
  }
  state.charts.statusBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: statuses.map(s => s.label),
      datasets: [{
        data: statuses.map(s => s.count),
        backgroundColor: statuses.map(s => s.color),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderSourceBreakdownChart(sources) {
  const canvas = document.getElementById('chartSourceBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.sourceBreakdown) {
    state.charts.sourceBreakdown.destroy();
  }
  const colors = ['#0ea5e9', '#6366f1', '#10b981', '#f59e0b'];
  state.charts.sourceBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: sources.map(s => s.source),
      datasets: [{
        data: sources.map(s => s.total_scraped),
        backgroundColor: colors.slice(0, sources.length),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderExperienceBreakdownChart(experiences) {
  const canvas = document.getElementById('chartExperienceBreakdown');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.experienceBreakdown) {
    state.charts.experienceBreakdown.destroy();
  }
  const colors = ['#8b5cf6', '#3b82f6', '#10b981', '#64748b'];
  state.charts.experienceBreakdown = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: experiences.map(e => e.exp_tier),
      datasets: [{
        data: experiences.map(e => e.count),
        backgroundColor: colors.slice(0, experiences.length),
        borderColor: '#0f172a',
        borderWidth: 2,
        hoverOffset: 4
      }]
    },
    options: {
      ...chartDefaultOptions,
      cutout: '66%',
      plugins: {
        ...chartDefaultOptions.plugins,
        legend: {
          position: 'right',
          labels: {
            boxWidth: 10,
            boxHeight: 10,
            color: '#cbd5e1',
            font: { size: 11 }
          }
        }
      }
    }
  });
}

function renderRejectionReasonsChart(reasons) {
  const canvas = document.getElementById('chartRejectionReasons');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.rejectionReasons) {
    state.charts.rejectionReasons.destroy();
  }
  const cleanReasons = (reasons && reasons.length > 0) ? reasons : [{ reason: 'No cancellations recorded', count: 0 }];

  // Dynamic height adjustment: comfortable spacing per reason bar so all reasons render cleanly
  const container = document.getElementById('chartReasonsContainer');
  const dynamicHeight = Math.max(260, cleanReasons.length * 36);
  if (container) {
    container.style.height = `${dynamicHeight}px`;
  }

  // Populate companion analytical breakdown list
  const listEl = document.getElementById('reasonsAnalyticsList');
  if (listEl) {
    const totalCancellations = cleanReasons.reduce((acc, r) => acc + (r.count || 0), 0);
    if (!reasons || reasons.length === 0 || totalCancellations === 0) {
      listEl.innerHTML = '<div style="font-size:0.78rem; color:#64748b; padding:0.5rem;">No cancellation reasons recorded yet.</div>';
    } else {
      listEl.innerHTML = cleanReasons.map((r, idx) => {
        const pct = totalCancellations > 0 ? Math.round((r.count / totalCancellations) * 100) : 0;
        return `
          <div class="reasons-analytics-row">
            <span class="reasons-rank-badge">#${idx + 1}</span>
            <span class="reasons-name" title="${escapeHtml(r.reason)}">${escapeHtml(r.reason)}</span>
            <div class="reasons-stats">
              <span class="reasons-pct-badge">${pct}%</span>
              <span class="reasons-count-badge">${r.count}</span>
              <button class="reasons-filter-btn" onclick="filterOthersByReason('${escapeHtml(r.reason).replace(/'/g, "\\'")}')" title="Filter applications in Others by this reason">
                Filter Others ↗
              </button>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Truncate Y-axis labels to max 35 chars for display; full text shown in tooltip
  const truncLabel = (s) => s.length > 35 ? s.slice(0, 32).trimEnd() + '...' : s;
  const fullLabels = cleanReasons.map(r => r.reason);
  const displayLabels = fullLabels.map(truncLabel);

  state.charts.rejectionReasons = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: displayLabels,
      datasets: [{
        label: 'Screened / Cancelled Count',
        data: cleanReasons.map(r => r.count),
        backgroundColor: 'rgba(244, 63, 94, 0.75)',
        hoverBackgroundColor: '#fb7185',
        borderRadius: 4,
      }]
    },
    options: {
      ...chartDefaultOptions,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        ...((chartDefaultOptions.plugins) || {}),
        tooltip: {
          callbacks: {
            title: (items) => fullLabels[items[0].dataIndex] || displayLabels[items[0].dataIndex],
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#cbd5e1', font: { size: 11 } }
        }
      }
    }
  });
}

async function loadAnalytics(days = 30) {
  state.analyticsDays = days;
  const param = (days && days > 0) ? `days=${days}` : `days=0`;
  try {
    const res = await fetch(`/api/analytics?${param}`);
    if (!res.ok) throw new Error('Failed to fetch analytics data');
    const data = await res.json();
    state.analyticsData = data;

    // Update KPI metrics
    if (data.summary) {
      document.getElementById('kpiApplied').textContent = data.summary.total_sent || 0;
      document.getElementById('kpiConversionRate').textContent = `${data.summary.sent_conversion_pct || 0}% conversion`;
      document.getElementById('kpiScraped').textContent = data.summary.total_scraped || 0;
      document.getElementById('kpiEmailRate').textContent = `${data.summary.email_rate_pct || 0}% emails found`;
      document.getElementById('kpiDirectEmails').textContent = `${data.summary.with_emails || 0} outreach ready`;
      document.getElementById('kpiDrafted').textContent = data.summary.total_drafted || 0;
      document.getElementById('kpiDraftReady').textContent = `${data.summary.total_drafted || 0} ready to send`;
      document.getElementById('kpiPendingGen').textContent = `${data.summary.pending_review || 0} pending AI`;
      document.getElementById('kpiRejected').textContent = data.summary.total_rejected || 0;
      document.getElementById('kpiSpamFlagged').textContent = `${data.summary.potential_spam_total || 0} potential spam`;
    }

    // Update timeline badges
    const totalAppliedInPeriod = (data.timeline_applied || []).reduce((acc, curr) => acc + curr.count, 0);
    const totalScrapedInPeriod = (data.timeline_scraped || []).reduce((acc, curr) => acc + curr.count, 0);
    const badgeApplied = document.getElementById('chartAppliedTotalBadge');
    if (badgeApplied) badgeApplied.textContent = `${totalAppliedInPeriod} Applications`;
    const badgeScraped = document.getElementById('chartScrapedTotalBadge');
    if (badgeScraped) badgeScraped.textContent = `${totalScrapedInPeriod} Discovered`;

    // Render Charts
    renderDailyAppliedChart(data.timeline_applied || []);
    renderDailyScrapedChart(data.timeline_scraped || []);
    renderStatusBreakdownChart(data.status_breakdown || []);
    renderSourceBreakdownChart(data.source_breakdown || []);
    renderExperienceBreakdownChart(data.experience_breakdown || []);
    renderRejectionReasonsChart(data.rejection_reasons || []);
  } catch (err) {
    console.error('Analytics load error:', err);
  }
}

function setAnalyticsTimeframe(days) {
  state.analyticsDays = days;
  const pills = document.querySelectorAll('#timeframePills .pill');
  pills.forEach(p => {
    p.classList.toggle('active', parseInt(p.getAttribute('data-days')) === days);
  });
  loadAnalytics(days);
}

