/**
 * Reach — Multi-Channel Push, Audio Chimes, Haptics & Notification Center
 * (src/static/js/notifications.js)
 */

let notificationState = {
  list: [],
  unreadCount: 0,
  audioCtx: null,
  swRegistration: null,
};

function isMobileDevice() {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth <= 768;
}

function registerReachServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => {
        notificationState.swRegistration = reg;
      })
      .catch((err) => {
        console.debug('Service Worker register notice:', err);
      });
  }
}

function unlockMobileAudioAndHaptics() {
  const unlock = () => {
    try {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) {
        if (!notificationState.audioCtx || notificationState.audioCtx.state === 'closed') {
          notificationState.audioCtx = new AudioCtxClass();
        }
        if (notificationState.audioCtx.state === 'suspended') {
          notificationState.audioCtx.resume();
        }
      }
    } catch (_) {}
    window.removeEventListener('touchstart', unlock, true);
    window.removeEventListener('touchend', unlock, true);
    window.removeEventListener('click', unlock, true);
  };
  window.addEventListener('touchstart', unlock, true);
  window.addEventListener('touchend', unlock, true);
  window.addEventListener('click', unlock, true);
}

function triggerHapticVibration(type = 'info') {
  if (!('vibrate' in navigator)) return;
  try {
    if (type === 'error') {
      navigator.vibrate([180, 80, 180, 80, 250]);
    } else if (type === 'success') {
      navigator.vibrate([120, 60, 140]);
    } else {
      navigator.vibrate([80]);
    }
  } catch (_) {}
}

let notifTitleFlashTimer = null;
function flashDocumentTitle(alertText) {
  if (!document.hidden) return;
  clearInterval(notifTitleFlashTimer);
  const originalTitle = document.title || 'Reach Job Automation';
  let flipped = false;
  let count = 0;
  notifTitleFlashTimer = setInterval(() => {
    document.title = flipped ? `🔔 ${alertText}` : originalTitle;
    flipped = !flipped;
    count++;
    if (count > 24) {
      clearInterval(notifTitleFlashTimer);
      document.title = originalTitle;
    }
  }, 900);

  const clearFlash = () => {
    if (!document.hidden) {
      clearInterval(notifTitleFlashTimer);
      document.title = originalTitle;
      document.removeEventListener('visibilitychange', clearFlash);
    }
  };
  document.addEventListener('visibilitychange', clearFlash);
}

function initNotificationSystem() {
  registerReachServiceWorker();
  unlockMobileAudioAndHaptics();
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
  const isMobile = isMobileDevice();

  if (!('Notification' in window)) {
    btn.textContent = isMobile ? 'Mobile Sound & Haptic' : 'Sound Alerts';
    btn.className = 'btn-link-xs text-success';
    btn.disabled = false;
    return;
  }

  const perm = Notification.permission;
  if (perm === 'granted') {
    btn.textContent = isMobile ? 'Mobile Alerts: On' : 'Desktop: On';
    btn.className = 'btn-link-xs text-success';
    btn.disabled = false;
    btn.title = 'Alerts are active. Tap to test or manage.';
  } else if (perm === 'denied') {
    btn.textContent = isMobile ? 'Mobile: Blocked (Fix)' : 'Desktop: Blocked (Fix)';
    btn.className = 'btn-link-xs text-danger';
    btn.disabled = false;
    btn.title = 'Notification permission blocked. Tap for guide on unblocking.';
  } else {
    btn.textContent = isMobile ? 'Enable Mobile Alerts' : 'Enable Desktop Alerts';
    btn.className = 'btn-link-xs';
    btn.disabled = false;
    btn.title = 'Enable browser notifications';
  }
}

async function handleNotificationPermClick() {
  if (!('Notification' in window)) {
    openNotificationHelpModal();
    return;
  }
  if (Notification.permission === 'denied' || Notification.permission === 'granted') {
    openNotificationHelpModal();
  } else {
    await requestNotificationPermission();
  }
}

function openNotificationHelpModal() {
  const modal = document.getElementById('notifHelpModal');
  if (!modal) return;

  const sysBadge = document.getElementById('notifStatusSystem');
  const vibBadge = document.getElementById('notifStatusVibration');
  const httpNotice = document.getElementById('notifHttpNotice');

  if (sysBadge) {
    if (!('Notification' in window)) {
      sysBadge.textContent = 'Not Supported';
      sysBadge.className = 'notif-status-badge';
    } else if (Notification.permission === 'granted') {
      sysBadge.textContent = 'Allowed';
      sysBadge.className = 'notif-status-badge badge-active';
    } else if (Notification.permission === 'denied') {
      sysBadge.textContent = 'Blocked';
      sysBadge.className = 'notif-status-badge badge-blocked';
    } else {
      sysBadge.textContent = 'Prompt Needed';
      sysBadge.className = 'notif-status-badge badge-prompt';
    }
  }

  if (vibBadge) {
    if ('vibrate' in navigator) {
      vibBadge.textContent = 'Active';
      vibBadge.className = 'notif-status-badge badge-active';
    } else {
      vibBadge.textContent = 'Desktop / N/A';
      vibBadge.className = 'notif-status-badge';
    }
  }

  if (httpNotice) {
    const isHttpsOrLocalhost = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    httpNotice.style.display = isHttpsOrLocalhost ? 'none' : 'block';
  }

  modal.classList.remove('hidden');
}

function closeNotificationHelpModal() {
  const modal = document.getElementById('notifHelpModal');
  if (modal) modal.classList.add('hidden');
}

function testNotificationAlert() {
  playNotificationSound();
  triggerHapticVibration('success');
  flashDocumentTitle('Test Alert Received!');

  if ('Notification' in window && Notification.permission === 'granted') {
    if (navigator.serviceWorker && navigator.serviceWorker.ready) {
      navigator.serviceWorker.ready.then((reg) => {
        reg.showNotification('Reach Automation Alert', {
          body: 'Test notification verified! Alerts, sound & vibration are active.',
          icon: '/favicon.ico',
          badge: '/favicon.ico',
          tag: 'reach-test-' + Date.now(),
          renotify: true,
        }).catch(() => {
          try {
            new Notification('Reach Automation Alert', {
              body: 'Test notification verified! Alerts, sound & vibration are active.',
              icon: '/favicon.ico',
            });
          } catch (_) {}
        });
      }).catch(() => {});
    } else {
      try {
        new Notification('Reach Automation Alert', {
          body: 'Test notification verified! Alerts, sound & vibration are active.',
          icon: '/favicon.ico',
        });
      } catch (_) {}
    }
  }

  showToast('🔊 Test alert fired! Sound, vibration & notifications active.', 'success');
}

async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    showToast('Browser does not support system notifications', 'warn');
    return;
  }
  try {
    const perm = await Notification.requestPermission();
    updateDesktopPermButtonUI();
    if (perm === 'granted') {
      showToast('Notifications enabled successfully!', 'success');
      playNotificationSound();
      triggerHapticVibration('success');
    } else if (perm === 'denied') {
      showToast('Notifications blocked. Tap to view unblock instructions.', 'warn');
      openNotificationHelpModal();
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
    console.debug('Audio chime notice:', err);
  }
}

function sendAppNotification({ title, message, type = 'info' }) {
  const item = {
    id: 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 4),
    title: title || 'System Update',
    message: message || '',
    type: type,
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
  triggerHapticVibration(type);
  flashDocumentTitle(item.title);

  if ('Notification' in window && Notification.permission === 'granted') {
    if (navigator.serviceWorker && navigator.serviceWorker.ready) {
      navigator.serviceWorker.ready.then((reg) => {
        reg.showNotification(item.title, {
          body: item.message,
          icon: '/favicon.ico',
          badge: '/favicon.ico',
          tag: 'reach-task-' + Date.now(),
          renotify: true,
        }).catch(() => {
          try {
            new Notification(item.title, {
              body: item.message,
              icon: '/favicon.ico',
            });
          } catch (_) {}
        });
      }).catch(() => {});
    } else {
      try {
        new Notification(item.title, {
          body: item.message,
          icon: '/favicon.ico',
        });
      } catch (_) {}
    }
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
    info: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="8"></line></svg>',
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

// Bind globally
window.notificationState = notificationState;
window.isMobileDevice = isMobileDevice;
window.registerReachServiceWorker = registerReachServiceWorker;
window.unlockMobileAudioAndHaptics = unlockMobileAudioAndHaptics;
window.triggerHapticVibration = triggerHapticVibration;
window.flashDocumentTitle = flashDocumentTitle;
window.initNotificationSystem = initNotificationSystem;
window.updateDesktopPermButtonUI = updateDesktopPermButtonUI;
window.handleNotificationPermClick = handleNotificationPermClick;
window.openNotificationHelpModal = openNotificationHelpModal;
window.closeNotificationHelpModal = closeNotificationHelpModal;
window.testNotificationAlert = testNotificationAlert;
window.requestNotificationPermission = requestNotificationPermission;
window.playNotificationSound = playNotificationSound;
window.sendAppNotification = sendAppNotification;
window.updateNotificationBadgeUI = updateNotificationBadgeUI;
window.toggleNotificationCenter = toggleNotificationCenter;
window.renderNotificationCenter = renderNotificationCenter;
window.clearAllNotifications = clearAllNotifications;
