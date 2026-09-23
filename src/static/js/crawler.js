/**
 * Reach — Crawler Trigger, Scraper Registry & Scraper Controls
 * (src/static/js/crawler.js)
 */

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
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Scraper Busy', err.detail || 'Cannot start scraper.');
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

const CRAWLER_SEARCH_OVERRIDE_KEY = 'reach_crawler_search_override';

function handleCrawlerSourceChange() {
  const sourceSelect = document.getElementById('crawlerSourceSelect');
  const locSelect = document.getElementById('crawlerLocationSelect');
  const searchInput = document.getElementById('crawlerSearchInput');
  const timeSelect = document.getElementById('crawlerTimeSelect');
  const customTimeVal = document.getElementById('crawlerCustomTimeValue');
  const customTimeUnit = document.getElementById('crawlerCustomTimeUnit');
  if (!sourceSelect || !locSelect) return;
  const sourceId = sourceSelect.value;
  if (sourceId === 'infopark') {
    locSelect.disabled = true;
    locSelect.title = "Infopark crawler discovers jobs in Kochi, Kerala";
    if (searchInput) {
      searchInput.disabled = true;
      searchInput.title = "Search keyword override is only supported by the LinkedIn crawler";
    }
    if (timeSelect) timeSelect.disabled = true;
    if (customTimeVal) customTimeVal.disabled = true;
    if (customTimeUnit) customTimeUnit.disabled = true;
  } else {
    locSelect.disabled = false;
    locSelect.title = "Target Job Location / Area";
    if (searchInput) {
      searchInput.disabled = false;
      searchInput.title = "Optional — takes priority over Settings → Target LinkedIn Search Keywords when filled. Leave empty to use the Settings keywords.";
    }
    if (timeSelect) timeSelect.disabled = false;
    if (customTimeVal) customTimeVal.disabled = false;
    if (customTimeUnit) customTimeUnit.disabled = false;
  }
}

function handleCrawlerTimeChange() {
  const timeSelect = document.getElementById('crawlerTimeSelect');
  const customWrapper = document.getElementById('crawlerCustomTimeWrapper');
  if (!timeSelect || !customWrapper) return;
  const isCustom = timeSelect.value === 'custom';
  customWrapper.classList.toggle('hidden', !isCustom);
  localStorage.setItem('reach_selected_crawler_time', timeSelect.value);
}

function updateCrawlerSearchPlaceholder() {
  const searchInput = document.getElementById('crawlerSearchInput');
  if (!searchInput) return;
  const settingsQuery = (state.config && state.config.search_query) ? String(state.config.search_query).trim() : '';
  searchInput.placeholder = settingsQuery
    ? `Settings default: "${settingsQuery}"`
    : 'e.g. Full Stack Developer';
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
  const searchInput = document.getElementById('crawlerSearchInput');
  if (searchInput) {
    const savedQuery = localStorage.getItem(CRAWLER_SEARCH_OVERRIDE_KEY);
    if (savedQuery !== null) {
      searchInput.value = savedQuery;
    }
    searchInput.addEventListener('input', () => {
      localStorage.setItem(CRAWLER_SEARCH_OVERRIDE_KEY, searchInput.value);
    });
  }
  const timeSelect = document.getElementById('crawlerTimeSelect');
  if (timeSelect) {
    const savedTime = localStorage.getItem('reach_selected_crawler_time');
    if (savedTime !== null) {
      timeSelect.value = savedTime;
    }
    handleCrawlerTimeChange();
  }
  updateCrawlerSearchPlaceholder();
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
      select.innerHTML = scrapers.map((s) => `
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
  const searchInput = document.getElementById('crawlerSearchInput');
  const searchOverride = (searchInput && !searchInput.disabled) ? (searchInput.value || '').trim() : '';

  let searchDetails = '';
  if (sourceId === 'linkedin') {
    const settingsQuery = (state.config && state.config.search_query) || 'Full stack developer';
    const baseQuery = searchOverride || settingsQuery;
    const priorityNote = searchOverride
      ? '\nPriority: Sidebar search bar (overrides Settings → Target LinkedIn Search Keywords)'
      : '\nPriority: Settings → Target LinkedIn Search Keywords (sidebar search bar is empty)';
    let timeFilter = '24h';
    let timeFilterLabel = 'Last 24 Hours';
    const timeSelect = document.getElementById('crawlerTimeSelect');
    const customTimeVal = document.getElementById('crawlerCustomTimeValue');
    const customTimeUnit = document.getElementById('crawlerCustomTimeUnit');
    if (timeSelect && !timeSelect.disabled) {
      if (timeSelect.value === 'custom') {
        const val = parseInt(customTimeVal?.value || '12', 10);
        const unit = customTimeUnit?.value || 'hours';
        timeFilter = `${unit === 'hours' ? 'custom_hours' : 'custom_days'}:${val}`;
        timeFilterLabel = `Custom: ${val} ${unit}`;
      } else {
        timeFilter = timeSelect.value;
        timeFilterLabel = timeSelect.options[timeSelect.selectedIndex]?.text || timeFilter;
      }
    }

    if (selectedLocation) {
      searchDetails = `\n\nSearch Query: "${baseQuery} ${selectedLocation}"${priorityNote}\nSaved Location: "${selectedLocation}"\nTime Window: ${timeFilterLabel}`;
    } else {
      searchDetails = `\n\nSearch Query: "${baseQuery}" (No specific location appended)${priorityNote}\nTime Window: ${timeFilterLabel}`;
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
    if (sourceId === 'linkedin') {
      if (selectedLocation) {
        payload.location = selectedLocation;
      }
      if (searchOverride) {
        // Sidebar search keyword takes priority over Settings → Target LinkedIn Search Keywords
        payload.search_query = searchOverride;
      }
      const timeSelect = document.getElementById('crawlerTimeSelect');
      const customTimeVal = document.getElementById('crawlerCustomTimeValue');
      const customTimeUnit = document.getElementById('crawlerCustomTimeUnit');
      if (timeSelect && !timeSelect.disabled) {
        if (timeSelect.value === 'custom') {
          const val = parseInt(customTimeVal?.value || '12', 10);
          const unit = customTimeUnit?.value || 'hours';
          payload.time_filter = `${unit === 'hours' ? 'custom_hours' : 'custom_days'}:${val}`;
        } else {
          payload.time_filter = timeSelect.value;
        }
      }
    }
    const res = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued ${sourceName} crawler (Position #${data.position})`, 'info');
      } else {
        showToast(`${sourceName} crawler started`, 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
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
  const p = (state.posts || []).find((item) => item.id === postId);
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(postId, p?.author_name || '', 'Scam', true);
  }
}

function cancelDiscoveredPost(postId, authorName) {
  const p = (state.posts || []).find((item) => item.id === postId);
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(postId, authorName || p?.author_name || '', '', false);
  }
}

function markActivePostSpam() {
  const active = state.activeReviewPost || (state.reviewPosts && state.reviewPosts.length > 0 ? state.reviewPosts[0] : null);
  if (!active) {
    showToast('No active post selected in Review workspace', 'warn');
    return;
  }
  state.activeReviewPost = active;
  state.activePostId = active.id;
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(active.id, active.author_name || 'Job Post', 'Scam', true);
  }
}

function markPostModalSpam() {
  const postId = state.currentModalPostId;
  if (!postId) return;
  const p = (state.posts && state.posts.find((item) => item.id === postId)) ||
            (state.reviewPosts && state.reviewPosts.find((item) => item.id === postId)) ||
            (state.sentPosts && state.sentPosts.find((item) => item.id === postId));
  if (typeof closePostModal === 'function') closePostModal();
  if (typeof openCancelReasonModal === 'function') {
    openCancelReasonModal(postId, p?.author_name || 'Job Post', 'Scam', true);
  }
}

async function generateSingleChatGPT(postId) {
  try {
    const res = await fetch(`/api/generate-email/${postId}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      if (data.queued) {
        showToast(`Enqueued email generation (Position #${data.position})`, 'info');
      } else {
        showToast('ChatGPT email generation launched in headed Firefox', 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
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
      const data = await res.json();
      state.selectedIds.clear();
      updateSelectedCountUI();
      if (data.queued) {
        showToast(`Enqueued batch generation for ${ids.length} posts (Position #${data.position})`, 'info');
      } else {
        showToast(`Batch generation started for ${ids.length} posts`, 'info');
      }
      if (typeof startTaskPolling === 'function') startTaskPolling();
    } else {
      const err = await res.json();
      showAlert('Cannot Start', err.detail);
    }
  } catch (err) {
    showAlert('Error', err.message);
  }
}

// Global Bindings
window.triggerInfoparkScrape = triggerInfoparkScrape;
window.handleCrawlerSourceChange = handleCrawlerSourceChange;
window.initCrawlerControls = initCrawlerControls;
window.updateCrawlerSearchPlaceholder = updateCrawlerSearchPlaceholder;
window.fetchScrapers = fetchScrapers;
window.fetchLocations = fetchLocations;
window.triggerSelectedCrawl = triggerSelectedCrawl;
window.handleCrawlerTimeChange = handleCrawlerTimeChange;
window.triggerLinkedInScrape = triggerLinkedInScrape;
window.markPostAsSpam = markPostAsSpam;
window.cancelDiscoveredPost = cancelDiscoveredPost;
window.markActivePostSpam = markActivePostSpam;
window.markPostModalSpam = markPostModalSpam;
window.generateSingleChatGPT = generateSingleChatGPT;
window.generateBatchChatGPT = generateBatchChatGPT;
