/**
 * Reach — Analytics Engine, Trend Graphs & Conversion Visualizations
 * (src/static/js/analytics.js)
 */

const chartDefaultOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: '#94a3b8',
        font: { family: "'Plus Jakarta Sans', sans-serif", size: 11, weight: '500' },
      },
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
    },
  },
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
      labels: timeline.map((d) => d.label),
      datasets: [
        {
          label: 'Applications Applied',
          data: timeline.map((d) => d.count),
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
        },
      ],
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 },
        },
      },
    },
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
      labels: timeline.map((d) => d.label),
      datasets: [
        {
          label: 'JDs Discovered',
          data: timeline.map((d) => d.count),
          backgroundColor: 'rgba(14, 165, 233, 0.75)',
          hoverBackgroundColor: '#38bdf8',
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...chartDefaultOptions,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8', font: { size: 10 }, maxRotation: 45 },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 },
        },
      },
    },
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
      labels: statuses.map((s) => s.label),
      datasets: [
        {
          data: statuses.map((s) => s.count),
          backgroundColor: statuses.map((s) => s.color),
          borderColor: '#0f172a',
          borderWidth: 2,
          hoverOffset: 4,
        },
      ],
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
            font: { size: 11 },
          },
        },
      },
    },
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
      labels: sources.map((s) => s.source),
      datasets: [
        {
          data: sources.map((s) => s.total_scraped),
          backgroundColor: colors.slice(0, sources.length),
          borderColor: '#0f172a',
          borderWidth: 2,
          hoverOffset: 4,
        },
      ],
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
            font: { size: 11 },
          },
        },
      },
    },
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
      labels: experiences.map((e) => e.exp_tier),
      datasets: [
        {
          data: experiences.map((e) => e.count),
          backgroundColor: colors.slice(0, experiences.length),
          borderColor: '#0f172a',
          borderWidth: 2,
          hoverOffset: 4,
        },
      ],
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
            font: { size: 11 },
          },
        },
      },
    },
  });
}

function renderRejectionReasonsChart(reasons) {
  const canvas = document.getElementById('chartRejectionReasons');
  if (!canvas || typeof Chart === 'undefined') return;
  if (state.charts.rejectionReasons) {
    state.charts.rejectionReasons.destroy();
  }
  const cleanReasons = (reasons && reasons.length > 0) ? reasons : [{ reason: 'No cancellations recorded', count: 0 }];

  const container = document.getElementById('chartReasonsContainer');
  const dynamicHeight = Math.max(260, cleanReasons.length * 36);
  if (container) {
    container.style.height = `${dynamicHeight}px`;
  }

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

  const truncLabel = (s) => (s.length > 35 ? s.slice(0, 32).trimEnd() + '...' : s);
  const fullLabels = cleanReasons.map((r) => r.reason);
  const displayLabels = fullLabels.map(truncLabel);

  state.charts.rejectionReasons = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: displayLabels,
      datasets: [
        {
          label: 'Screened / Cancelled Count',
          data: cleanReasons.map((r) => r.count),
          backgroundColor: 'rgba(244, 63, 94, 0.75)',
          hoverBackgroundColor: '#fb7185',
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...chartDefaultOptions,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        ...(chartDefaultOptions.plugins || {}),
        tooltip: {
          callbacks: {
            title: (items) => fullLabels[items[0].dataIndex] || displayLabels[items[0].dataIndex],
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8', font: { size: 10 }, precision: 0 },
        },
        y: {
          grid: { display: false },
          ticks: { color: '#cbd5e1', font: { size: 11 } },
        },
      },
    },
  });
}

async function loadAnalytics(days = 30) {
  state.analyticsDays = days;
  const param = days && days > 0 ? `days=${days}` : `days=0`;
  try {
    const res = await fetch(`/api/analytics?${param}`);
    if (!res.ok) throw new Error('Failed to fetch analytics data');
    const data = await res.json();
    state.analyticsData = data;

    // Update KPI metrics
    if (data.summary) {
      const elApplied = document.getElementById('kpiApplied');
      if (elApplied) elApplied.textContent = Number(data.summary.total_sent || 0).toLocaleString();
      const elConv = document.getElementById('kpiConversionRate');
      if (elConv) elConv.textContent = `${data.summary.sent_conversion_pct || 0}% conversion`;
      const elScraped = document.getElementById('kpiScraped');
      if (elScraped) elScraped.textContent = Number(data.summary.total_scraped || 0).toLocaleString();
      const elRate = document.getElementById('kpiEmailRate');
      if (elRate) elRate.textContent = `${data.summary.email_rate_pct || 0}% emails found`;
      const elDirect = document.getElementById('kpiDirectEmails');
      if (elDirect) elDirect.textContent = Number(data.summary.with_emails || 0).toLocaleString();
      const elDrafted = document.getElementById('kpiDrafted');
      if (elDrafted) elDrafted.textContent = Number(data.summary.total_drafted || 0).toLocaleString();
      const elDraftReady = document.getElementById('kpiDraftReady');
      if (elDraftReady) elDraftReady.textContent = `${Number(data.summary.total_drafted || 0).toLocaleString()} ready to send`;
      const elPendingGen = document.getElementById('kpiPendingGen');
      if (elPendingGen) elPendingGen.textContent = `${Number(data.summary.pending_review || 0).toLocaleString()} pending AI`;
      const elRejected = document.getElementById('kpiRejected');
      if (elRejected) elRejected.textContent = Number(data.summary.total_rejected || 0).toLocaleString();
      const elSpamFlagged = document.getElementById('kpiSpamFlagged');
      if (elSpamFlagged) elSpamFlagged.textContent = `${Number(data.summary.potential_spam_total || 0).toLocaleString()} potential spam`;
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
  pills.forEach((p) => {
    p.classList.toggle('active', parseInt(p.getAttribute('data-days')) === days);
  });
  loadAnalytics(days);
}

// Global Bindings
window.renderDailyAppliedChart = renderDailyAppliedChart;
window.renderDailyScrapedChart = renderDailyScrapedChart;
window.renderStatusBreakdownChart = renderStatusBreakdownChart;
window.renderSourceBreakdownChart = renderSourceBreakdownChart;
window.renderExperienceBreakdownChart = renderExperienceBreakdownChart;
window.renderRejectionReasonsChart = renderRejectionReasonsChart;
window.loadAnalytics = loadAnalytics;
window.setAnalyticsTimeframe = setAnalyticsTimeframe;
