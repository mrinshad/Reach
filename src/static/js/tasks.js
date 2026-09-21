/**
 * Reach — Real-time Task Drawer, Execution Queue, Log Streaming & Alerts
 * (src/static/js/tasks.js)
 */

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

    if (!card || !titleEl || !subEl || !countEl || !fillEl || !logsEl) return;

    // Render task queue drawer if queued tasks exist
    const queueSection = document.getElementById('taskQueueSection');
    const queueBadge = document.getElementById('taskQueueCountBadge');
    const queueList = document.getElementById('taskQueueList');
    const queue = task.queue || [];

    if (queueSection && queueList) {
      if (queue.length > 0) {
        queueSection.classList.remove('hidden');
        if (queueBadge) queueBadge.textContent = queue.length;
        queueList.innerHTML = queue.map((item, idx) => `
          <div class="task-queue-card" id="queueItem_${escapeHtml(item.id)}">
            <div class="task-queue-card-left">
              <span class="queue-pos-badge">#${idx + 1}</span>
              <span class="queue-card-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
            </div>
            <button class="btn-cancel-queue-item" onclick="cancelQueuedTask('${escapeHtml(item.id)}')" title="Cancel pending task">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        `).join('');
      } else {
        queueSection.classList.add('hidden');
        if (queueBadge) queueBadge.textContent = '0';
        queueList.innerHTML = '';
      }
    }

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

      logsEl.innerHTML = (task.logs || []).map((l) => `<div>${escapeHtml(l)}</div>`).join('');
      logsEl.scrollTop = logsEl.scrollHeight;

      state.lastHandledTaskKey = null;
    } else if (task.status === 'completed' || task.status === 'error') {
      const hasQueuedItems = (queue.length > 0);
      const taskEventKey = `${task.task_name}_${task.started_at}_${task.status}`;
      const isNewCompletion = (state.lastHandledTaskKey !== taskEventKey);

      if (isNewCompletion) {
        state.lastHandledTaskKey = taskEventKey;
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

          if (typeof sendAppNotification === 'function') {
            sendAppNotification({
              title: task.task_name || 'Task Complete',
              message: notifMsg,
              type: 'success',
            });
          }
        } else {
          const firstLine = (task.error || 'Operation failed').split('\n')[0];
          subEl.textContent = `Failed: ${firstLine}`;

          if (typeof sendAppNotification === 'function') {
            sendAppNotification({
              title: task.task_name || 'Task Failed',
              message: firstLine,
              type: 'error',
            });
          }

          if (typeof showSnackbar === 'function') {
            showSnackbar({
              title: `Task Error: ${task.task_name || 'Automation'}`,
              message: firstLine,
              details: task.error,
              type: 'error',
            });
          }
          if (typeof showCenterAlert === 'function') {
            showCenterAlert(
              `Automation Stopped: ${task.task_name || 'Task'}`,
              task.error || 'The automation task encountered an issue and stopped.'
            );
          }
        }
        if (typeof loadDashboardData === 'function') loadDashboardData();
      }

      if (hasQueuedItems) {
        card.classList.remove('hidden');
        subEl.textContent = `✓ ${task.task_name} finished. Next queued task starting...`;
        if (!state.pollingTimer) {
          state.pollingTimer = setInterval(pollTaskStatus, 1500);
        }
      } else {
        stopTaskPolling();
        setTimeout(() => {
          if (!state.pollingTimer) {
            card.classList.add('hidden');
            fetch('/api/tasks/clear', { method: 'POST' }).catch(() => {});
          }
        }, task.crawl_stats ? 3000 : 1500);
      }
    } else {
      const hasQueuedItems = (queue.length > 0);
      if (hasQueuedItems) {
        card.classList.remove('hidden');
        titleEl.textContent = 'Queue Active';
        subEl.textContent = `Waiting for next task to start (${queue.length} in queue)...`;
        if (!state.pollingTimer) {
          state.pollingTimer = setInterval(pollTaskStatus, 1500);
        }
      } else {
        card.classList.add('hidden');
        stopTaskPolling();
      }
    }
  } catch (err) {
    console.error('Task poll error:', err);
    stopTaskPolling();
  }
}

async function cancelQueuedTask(taskId) {
  try {
    const res = await fetch(`/api/tasks/queue/cancel/${encodeURIComponent(taskId)}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Queued task cancelled', 'info');
      pollTaskStatus();
    } else {
      showToast(data.detail || 'Could not cancel task', 'error');
    }
  } catch (err) {
    showToast('Network error cancelling task: ' + err.message, 'error');
  }
}

async function clearTaskQueue() {
  try {
    const res = await fetch('/api/tasks/queue/clear', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Queue cleared', 'info');
      pollTaskStatus();
    } else {
      showToast(data.detail || 'Could not clear queue', 'error');
    }
  } catch (err) {
    showToast('Network error clearing queue: ' + err.message, 'error');
  }
}

function showCrawlSummaryModal(taskName, stats) {
  const modal = document.getElementById('crawlSummaryModal');
  const title = document.getElementById('crawlSummaryTitle');
  const grid = document.getElementById('crawlSummaryGrid');
  if (!modal || !grid) return;

  if (title) title.textContent = `${taskName || 'Crawler'} Summary`;

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
  const drawer = document.getElementById('taskLogsDrawer');
  if (drawer) drawer.classList.toggle('hidden', !state.showLogs);
}

// Global Bindings
window.startTaskPolling = startTaskPolling;
window.stopTaskPolling = stopTaskPolling;
window.pollTaskStatus = pollTaskStatus;
window.cancelQueuedTask = cancelQueuedTask;
window.clearTaskQueue = clearTaskQueue;
window.showCrawlSummaryModal = showCrawlSummaryModal;
window.closeCrawlSummaryModal = closeCrawlSummaryModal;
window.toggleTaskLogs = toggleTaskLogs;
window.toggleTaskDrawer = toggleTaskLogs;
