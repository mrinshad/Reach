/**
 * Reach — Screening Question & Answer Bank Workspace Controller
 * (src/static/js/question_bank.js)
 * 
 * Manages the dedicated Question Bank page:
 * - Querying, searching, filtering, and sorting screening questions
 * - Inline single and bulk answer editing and database persistence
 * - Single question deletion and batch multi-select deletion
 * - Custom question creation modal
 * - Real-time synchronization with LinkedIn Easy Apply automation
 */

const qbankState = {
  questions: [],
  totalCount: 0,
  answeredCount: 0,
  aiSuggestedCount: 0,
  unreasonableCount: 0,
  pendingCount: 0,
  statusFilter: 'all', // 'all' | 'ai_suggested' | 'pending' | 'answered' | 'unreasonable'
  categoryFilter: 'all',
  searchQuery: '',
  sortBy: 'occurrences',
  fromDate: '',
  toDate: '',
  selectedKeys: new Set(),
  modifiedAnswers: {}, // key -> newAnswer
  isLoading: false,
  searchDebounceTimer: null,
};

// --- Page Initialization & Data Fetching ---
async function loadQuestionBankPage(silent = false) {
  qbankState.isLoading = true;
  if (!silent) updateQuestionBankLoadingUI(true);
  updateQuestionBankClearFiltersButton();

  try {
    const params = new URLSearchParams();
    if (qbankState.categoryFilter && qbankState.categoryFilter !== 'all') {
      params.append('category', qbankState.categoryFilter);
    }
    if (qbankState.statusFilter && qbankState.statusFilter !== 'all') {
      params.append('status', qbankState.statusFilter);
    }
    if (qbankState.searchQuery && qbankState.searchQuery.trim()) {
      params.append('search', qbankState.searchQuery.trim());
    }
    if (qbankState.sortBy) {
      params.append('sort_by', qbankState.sortBy);
    }
    if (qbankState.fromDate) {
      params.append('from_date', qbankState.fromDate);
    }
    if (qbankState.toDate) {
      params.append('to_date', qbankState.toDate);
    }

    const res = await fetch(`/api/easy-apply/questions?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    qbankState.questions = data.questions || [];
    qbankState.totalCount = data.total_count || 0;
    qbankState.answeredCount = data.answered_count || 0;
    qbankState.aiSuggestedCount = data.ai_suggested_count || 0;
    qbankState.unreasonableCount = data.unreasonable_count || 0;
    qbankState.pendingCount = data.pending_count || 0;

    // Prune selected keys that no longer exist
    const currentKeys = new Set(qbankState.questions.map(q => q.key || q.id));
    for (const k of qbankState.selectedKeys) {
      if (!currentKeys.has(k)) {
        qbankState.selectedKeys.delete(k);
      }
    }

    updateQuestionBankKpis();
    updateQuestionBankStatusSegmentUI();
    renderQuestionBankCards();
    updateBatchBarUI();
    updateUnsavedToastUI();

  } catch (err) {
    console.error('Failed to load Question Bank:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Error Loading Questions',
        message: err.message || 'Could not fetch screening questions from database.',
        type: 'error',
      });
    }
  } finally {
    qbankState.isLoading = false;
    if (!silent) updateQuestionBankLoadingUI(false);
  }
}

// --- Loading State UI ---
function updateQuestionBankLoadingUI(loading) {
  const skeleton = document.getElementById('qbankSkeletonList');
  const grid = document.getElementById('qbankCardsGrid');
  const empty = document.getElementById('qbankEmptyState');

  if (skeleton) {
    skeleton.style.display = loading ? 'flex' : 'none';
  }
  if (loading) {
    if (grid) grid.style.display = 'none';
    if (empty) empty.classList.add('hidden');
  } else {
    if (grid) grid.style.display = 'flex';
  }
}

// --- Update KPI Metrics Ribbon ---
function updateQuestionBankKpis() {
  const elTotal = document.getElementById('qbankKpiTotal');
  if (elTotal) elTotal.textContent = qbankState.totalCount;

  const elAnswered = document.getElementById('qbankKpiAnswered');
  if (elAnswered) elAnswered.textContent = qbankState.answeredCount;

  const elAiSuggested = document.getElementById('qbankKpiAiSuggested');
  if (elAiSuggested) elAiSuggested.textContent = qbankState.aiSuggestedCount;

  const elPending = document.getElementById('qbankKpiPending');
  if (elPending) elPending.textContent = qbankState.pendingCount;

  const elRate = document.getElementById('qbankKpiAnswerRate');
  if (elRate) {
    const rate = qbankState.totalCount > 0 
      ? Math.round((qbankState.answeredCount / qbankState.totalCount) * 100) 
      : 0;
    elRate.textContent = `${rate}%`;
  }

  const elPendingBadge = document.getElementById('qbankKpiPendingBadge');
  if (elPendingBadge) {
    elPendingBadge.textContent = qbankState.pendingCount > 0 ? `${qbankState.pendingCount} Action Needed` : 'All Answered';
    elPendingBadge.className = qbankState.pendingCount > 0 ? 'kpi-trend warn' : 'kpi-trend ok';
  }

  // Also update sidebar badge in real-time (shows total actionable items: pending + review)
  const countQBankEl = document.getElementById('countSidebarQuestionBank');
  if (countQBankEl) {
    const totalNeedingAction = (qbankState.pendingCount || 0) + (qbankState.aiSuggestedCount || 0);
    countQBankEl.textContent = totalNeedingAction;
    countQBankEl.style.display = totalNeedingAction > 0 ? 'inline-flex' : 'none';
  }
}

// --- Update Status Segmented Buttons UI ---
function updateQuestionBankStatusSegmentUI() {
  const btnAll = document.getElementById('btnQbankStatAll');
  const btnAi = document.getElementById('btnQbankStatAi');
  const btnPending = document.getElementById('btnQbankStatPending');
  const btnAnswered = document.getElementById('btnQbankStatAnswered');
  const btnUnreasonable = document.getElementById('btnQbankStatUnreasonable');

  if (btnAll) btnAll.classList.toggle('active', qbankState.statusFilter === 'all');
  if (btnAi) btnAi.classList.toggle('active', qbankState.statusFilter === 'ai_suggested');
  if (btnPending) btnPending.classList.toggle('active', qbankState.statusFilter === 'pending');
  if (btnAnswered) btnAnswered.classList.toggle('active', qbankState.statusFilter === 'answered');
  if (btnUnreasonable) btnUnreasonable.classList.toggle('active', qbankState.statusFilter === 'unreasonable');

  const countAll = document.getElementById('qbankCountStatAll');
  if (countAll) countAll.textContent = qbankState.totalCount;

  const countAi = document.getElementById('qbankCountStatAi');
  if (countAi) countAi.textContent = qbankState.aiSuggestedCount;

  const countPending = document.getElementById('qbankCountStatPending');
  if (countPending) countPending.textContent = qbankState.pendingCount;

  const countAnswered = document.getElementById('qbankCountStatAnswered');
  if (countAnswered) countAnswered.textContent = qbankState.answeredCount;

  const countUnreasonable = document.getElementById('qbankCountStatUnreasonable');
  if (countUnreasonable) countUnreasonable.textContent = qbankState.unreasonableCount;
}

// --- Render Question Cards ---
function renderQuestionBankCards() {
  const grid = document.getElementById('qbankCardsGrid');
  const empty = document.getElementById('qbankEmptyState');
  const emptyDesc = document.getElementById('qbankEmptyDesc');
  if (!grid) return;

  if (qbankState.questions.length === 0) {
    grid.innerHTML = '';
    if (empty) empty.classList.remove('hidden');
    if (emptyDesc) {
      if (qbankState.searchQuery) {
        emptyDesc.textContent = `No questions found matching "${qbankState.searchQuery}". Try a different keyword or clear your search.`;
      } else if (qbankState.statusFilter === 'pending') {
        emptyDesc.textContent = 'Awesome! All questions have been answered. Your auto-apply submissions are fully trained!';
      } else if (qbankState.statusFilter === 'unreasonable') {
        emptyDesc.textContent = 'No unreasonable or spam screening questions detected.';
      } else if (qbankState.categoryFilter !== 'all') {
        emptyDesc.textContent = `No questions found under the "${qbankState.categoryFilter}" category.`;
      } else {
        emptyDesc.textContent = 'No screening questions cataloged yet. Crawl Easy Apply jobs or add a custom question to get started.';
      }
    }
    return;
  }

  if (empty) empty.classList.add('hidden');

  const escapeFn = typeof escapeHtml === 'function' ? escapeHtml : (str => String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));

  const html = qbankState.questions.map(q => {
    const key = q.key || q.id;
    const isSelected = qbankState.selectedKeys.has(key);
    const hasUnsavedEdit = Object.prototype.hasOwnProperty.call(qbankState.modifiedAnswers, key);
    const currentAnswer = hasUnsavedEdit ? qbankState.modifiedAnswers[key] : (q.answer || '');
    const isBlank = (currentAnswer === '__EMPTY__');
    const isAiSuggested = (q.status === 'AI_SUGGESTED');
    const isUnreasonable = (q.status === 'UNREASONABLE');
    const isAnswered = !isAiSuggested && !isUnreasonable && (isBlank || Boolean(currentAnswer && currentAnswer.trim()));
    const occurrences = q.occurrences || 1;
    const isStandard = Boolean(q.is_standard);
    const category = (q.category || 'profile').toLowerCase();
    const placeholder = isBlank 
      ? '(Intentionally left blank / N/A — will submit empty on apply)' 
      : (q.default_placeholder || 'Enter your standard answer...');

    // Sample jobs preview
    let sampleJobsHtml = '';
    if (Array.isArray(q.sample_jobs) && q.sample_jobs.length > 0) {
      const renderJobBtn = (jobItem) => {
        const jStr = String(jobItem || '').trim();
        const isGeneric = ['direct application flow', 'standard candidate profile question'].includes(jStr.toLowerCase());
        if (isGeneric) {
          return `<span class="sample-job-tag is-generic" title="${escapeFn(jStr)}">${escapeFn(jStr)}</span>`;
        }

        let roleAndComp = jStr;
        let locText = '';
        if (jStr.includes(' • 📍 ')) {
          const parts = jStr.split(' • 📍 ');
          roleAndComp = (parts[0] || '').trim();
          locText = (parts[1] || '').trim();
        } else if (jStr.includes(' • ')) {
          const parts = jStr.split(' • ');
          roleAndComp = (parts[0] || '').trim();
          locText = (parts[1] || '').trim();
        }

        const tooltip = locText 
          ? `Click to view '${escapeFn(roleAndComp)}' (📍 ${escapeFn(locText)}) job description on Easy Apply section` 
          : `Click to view '${escapeFn(roleAndComp)}' job description on Easy Apply section`;

        return `
          <button 
            type="button" 
            class="sample-job-tag is-clickable" 
            data-job="${escapeFn(roleAndComp)}" 
            data-loc="${escapeFn(locText)}"
            onclick="handleSampleJobClick(this, event)" 
            title="${tooltip}"
          >
            <span style="opacity: 0.85; flex-shrink: 0;">💼</span>
            <span class="sample-job-name">${escapeFn(roleAndComp)}</span>
            ${locText ? `<span class="sample-job-location-badge" title="Location: ${escapeFn(locText)}">📍 ${escapeFn(locText)}</span>` : ''}
            <span class="sample-job-arrow" aria-hidden="true">↗</span>
          </button>
        `;
      };

      const topJobs = q.sample_jobs.slice(0, 3);
      const tags = topJobs.map(renderJobBtn).join('');
      const moreCount = q.sample_jobs.length - topJobs.length;
      let moreTag = '';
      if (moreCount > 0) {
        const remainingJobs = q.sample_jobs.slice(3);
        const remainingHtml = remainingJobs.map(renderJobBtn).join('');
        moreTag = `
          <span class="sample-job-more-wrap">
            <button type="button" class="sample-job-tag is-more-toggle" onclick="toggleMoreSampleJobs(this, event)" title="Show ${moreCount} more jobs">+${moreCount} more</button>
            <span class="sample-jobs-expanded hidden" style="display: none; align-items: center; gap: 0.35rem; flex-wrap: wrap;">${remainingHtml}</span>
          </span>
        `;
      }

      sampleJobsHtml = `
        <div class="qbank-sample-jobs">
          <span class="qbank-sample-jobs-lbl" style="font-weight: 600; color: var(--text-dim);">Found on:</span>
          ${tags}
          ${moreTag}
        </div>
      `;
    }

    // Status badge
    let statusBadgeHtml = '';
    if (isBlank) {
      statusBadgeHtml = `<span class="qbank-badge badge-blank" title="Configured to leave blank on applications">🚫 Blank / N/A</span>`;
    } else if (isAiSuggested) {
      statusBadgeHtml = `<span class="qbank-badge badge-ai" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35); font-weight: 600;" title="Suggested by ChatGPT. Please review and save to confirm.">🤖 AI Suggested</span>`;
    } else if (isUnreasonable) {
      statusBadgeHtml = `<span class="qbank-badge status-unreasonable" title="Flagged as unreasonable / unanswerable recruiter screening question. Easy Apply halts on roles requiring this.">🚫 Unreasonable</span>`;
    } else if (isAnswered) {
      statusBadgeHtml = `<span class="qbank-badge status-ans">✓ Answered</span>`;
    } else {
      statusBadgeHtml = `<span class="qbank-badge status-pend">⚠️ Pending Answer</span>`;
    }

    // Multi-choice option pills
    let optionsHtml = '';
    if (q.options && Array.isArray(q.options) && q.options.length > 0) {
      optionsHtml = `
        <div class="qbank-options-pills">
          <span class="qbank-options-label">Select Option:</span>
          ${q.options.map(opt => {
            const isChosen = (!isBlank && currentAnswer.trim().toLowerCase() === String(opt).trim().toLowerCase());
            return `<button type="button" class="qbank-option-pill ${isChosen ? 'is-selected' : ''}" onclick="selectQuestionOption('${escapeFn(key)}', '${escapeFn(opt)}')">${escapeFn(opt)}</button>`;
          }).join('')}
        </div>
      `;
    }

    const cardStatusClass = isAnswered ? 'status-answered' : (isAiSuggested ? 'status-ai' : (isUnreasonable ? 'status-unreasonable' : 'status-pending'));
    const selectedClass = isSelected ? 'is-selected' : '';
    const dirtyClass = hasUnsavedEdit ? 'is-dirty' : '';

    return `
      <div class="qbank-card ${cardStatusClass} ${selectedClass}" id="qbankCard-${escapeFn(key)}" data-key="${escapeFn(key)}">
        <div class="qbank-card-header">
          <div class="card-header-left">
            <label class="qbank-checkbox-label" title="Select question for batch actions">
              <input 
                type="checkbox" 
                class="qbank-item-checkbox" 
                ${isSelected ? 'checked' : ''} 
                onchange="toggleQuestionSelection('${escapeFn(key)}', this.checked)" 
              />
              <span class="custom-checkbox"></span>
            </label>
            <div class="card-title-group">
              <h4 class="qbank-question-text">${escapeFn(q.question)}</h4>
              <div class="qbank-badges-row">
                <span class="qbank-badge cat-${escapeFn(category)}">${escapeFn(category)}</span>
                ${statusBadgeHtml}
                ${isStandard ? '<span class="qbank-badge badge-standard">⭐ Core Standard</span>' : '<span class="qbank-badge badge-occurrences">Discovered</span>'}
                ${occurrences > 1 ? `<span class="qbank-badge badge-occurrences" title="Asked across ${occurrences} job applications">🔥 ${occurrences}x</span>` : ''}
              </div>
            </div>
          </div>

          <div class="card-header-actions">
            <button 
              type="button"
              class="btn-card-action btn-card-delete" 
              onclick="handleCardDeleteClick('${escapeFn(key)}', event)" 
              title="Delete question from Question Bank"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span>Delete</span>
            </button>
          </div>
        </div>

        ${sampleJobsHtml}

        <div class="qbank-answer-field-wrap">
          ${optionsHtml}

          <textarea 
            class="qbank-answer-textarea ${dirtyClass}" 
            id="qbankTextarea-${escapeFn(key)}" 
            placeholder="${escapeFn(placeholder)}" 
            rows="2"
            oninput="handleQuestionBankAnswerInput('${escapeFn(key)}', this.value)"
          >${escapeFn(isBlank ? '__EMPTY__' : currentAnswer)}</textarea>

          <div class="qbank-card-footer">
            <div class="qbank-card-footer-left">
              <button 
                type="button" 
                class="btn-card-blank ${isBlank ? 'is-active' : ''}" 
                onclick="toggleQuestionBlank('${escapeFn(key)}')"
                title="Click to intentionally leave this field blank during Easy Apply (e.g. Middle Name)"
              >
                ${isBlank ? '✓ Set as Blank / N/A' : '🚫 Leave Blank'}
              </button>
              <div class="qbank-status-text ${hasUnsavedEdit ? 'modified' : (isAnswered ? 'saved' : (isAiSuggested ? 'ai-review' : ''))}" id="qbankFooterStatus-${escapeFn(key)}">
                ${hasUnsavedEdit ? '⚠️ Modified (Unsaved)' : (isBlank ? '✓ Auto-cleared on apply' : (isAnswered ? '✓ Auto-fill Ready' : (isAiSuggested ? '🤖 Suggested — Review & Approve' : 'Empty response')))}
              </div>
            </div>
            ${isAiSuggested ? `
              <button 
                type="button" 
                class="btn-approve-answer ${hasUnsavedEdit ? 'is-modified' : ''}" 
                id="btnCardApprove-${escapeFn(key)}" 
                onclick="approveSingleQuestionAnswer('${escapeFn(key)}')"
                title="Approve this AI suggested answer and promote to Answered for auto-apply"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <span>${hasUnsavedEdit ? 'Save & Approve' : 'Approve'}</span>
              </button>
            ` : `
              <button 
                type="button"
                class="card-save-btn ${hasUnsavedEdit ? '' : 'btn-disabled'}" 
                id="btnCardSave-${escapeFn(key)}" 
                onclick="saveSingleQuestionAnswer('${escapeFn(key)}')"
                title="Save changes to this question"
              >
                Save Answer
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');

  grid.innerHTML = html;
}

// --- Answer Input Handling & Tracking ---
function handleQuestionBankAnswerInput(key, value) {
  const question = qbankState.questions.find(q => (q.key || q.id) === key);
  if (!question) return;

  const originalAnswer = (question.answer || '').trim();
  const newAnswer = (value || '').trim();
  const isAiSuggested = (question.status === 'AI_SUGGESTED');

  const card = document.getElementById(`qbankCard-${key}`);
  const textarea = document.getElementById(`qbankTextarea-${key}`);
  const footerStatus = document.getElementById(`qbankFooterStatus-${key}`);
  const saveBtn = document.getElementById(`btnCardSave-${key}`);
  const approveBtn = document.getElementById(`btnCardApprove-${key}`);
  const blankBtn = card ? card.querySelector('.btn-card-blank') : null;

  const isBlank = (newAnswer === '__EMPTY__');

  // Update pills active state
  if (card) {
    const pills = card.querySelectorAll('.qbank-option-pill');
    pills.forEach(p => {
      const match = !isBlank && (p.textContent.trim().toLowerCase() === newAnswer.toLowerCase());
      p.classList.toggle('is-selected', match);
    });
  }

  if (blankBtn) {
    blankBtn.classList.toggle('is-active', isBlank);
    blankBtn.textContent = isBlank ? '✓ Set as Blank / N/A' : '🚫 Leave Blank';
  }

  if (newAnswer !== originalAnswer) {
    qbankState.modifiedAnswers[key] = value;
    if (textarea) textarea.classList.add('is-dirty');
    if (footerStatus) {
      footerStatus.className = 'qbank-status-text modified';
      footerStatus.textContent = isBlank ? '⚠️ Set to Blank (Unsaved)' : (isAiSuggested ? '⚠️ Edited Suggestion (Unsaved)' : '⚠️ Modified (Unsaved)');
    }
    if (saveBtn) saveBtn.classList.remove('btn-disabled');
    if (approveBtn) {
      approveBtn.classList.add('is-modified');
      const span = approveBtn.querySelector('span');
      if (span) span.textContent = 'Save & Approve';
    }
  } else {
    delete qbankState.modifiedAnswers[key];
    if (textarea) textarea.classList.remove('is-dirty');
    if (footerStatus) {
      const isAns = isBlank || Boolean(originalAnswer);
      footerStatus.className = `qbank-status-text ${isAns ? 'saved' : (isAiSuggested ? 'ai-review' : '')}`;
      footerStatus.textContent = isBlank ? '✓ Auto-cleared on apply' : (isAns ? (isAiSuggested ? '🤖 Suggested — Review & Approve' : '✓ Auto-fill Ready') : 'Empty response');
    }
    if (saveBtn) saveBtn.classList.add('btn-disabled');
    if (approveBtn) {
      approveBtn.classList.remove('is-modified');
      const span = approveBtn.querySelector('span');
      if (span) span.textContent = 'Approve';
    }
  }

  updateUnsavedToastUI();
}

function selectQuestionOption(key, optionText) {
  const textarea = document.getElementById(`qbankTextarea-${key}`);
  if (textarea) {
    textarea.value = optionText;
    handleQuestionBankAnswerInput(key, optionText);
  }
}

function toggleQuestionBlank(key) {
  const q = (qbankState.questions || []).find(item => (item.key || item.id) === key);
  const currentVal = qbankState.modifiedAnswers[key] !== undefined ? qbankState.modifiedAnswers[key] : (q ? q.answer : '');
  const textarea = document.getElementById(`qbankTextarea-${key}`);

  if (currentVal === '__EMPTY__') {
    // Revert blank to empty string for custom input
    if (textarea) textarea.value = '';
    handleQuestionBankAnswerInput(key, '');
  } else {
    // Set to __EMPTY__
    if (textarea) textarea.value = '__EMPTY__';
    handleQuestionBankAnswerInput(key, '__EMPTY__');
  }
}

function handleCardDeleteClick(key, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const q = (qbankState.questions || []).find(item => (item.key === key || item.id === key));
  const questionText = q ? q.question : 'this question';
  deleteSingleQuestion(key, questionText);
}

function updateUnsavedToastUI() {
  const toast = document.getElementById('qbankUnsavedToast');
  const countEl = document.getElementById('qbankUnsavedCount');
  const count = Object.keys(qbankState.modifiedAnswers).length;

  if (toast && countEl) {
    countEl.textContent = count;
    if (count > 0) {
      toast.classList.remove('hidden');
    } else {
      toast.classList.add('hidden');
    }
  }
}

function discardQuestionBankEdits() {
  qbankState.modifiedAnswers = {};
  renderQuestionBankCards();
  updateUnsavedToastUI();
  if (typeof showSnackbar === 'function') {
    showSnackbar({
      title: 'Edits Discarded',
      message: 'All unsaved question answer changes have been reverted.',
      type: 'info',
      duration: 3000,
    });
  }
}

// --- Save Single Question Answer ---
async function saveSingleQuestionAnswer(key) {
  const textarea = document.getElementById(`qbankTextarea-${key}`);
  let newAnswer = qbankState.modifiedAnswers[key] !== undefined 
    ? qbankState.modifiedAnswers[key] 
    : (textarea ? textarea.value : '');

  const isNowAnswered = Boolean(newAnswer.trim() || newAnswer === '__EMPTY__');

  // If filtered by pending or ai_suggested and answered, remove card immediately
  if (isNowAnswered && (qbankState.statusFilter === 'pending' || qbankState.statusFilter === 'ai_suggested')) {
    const cardEl = document.getElementById(`qbankCard-${key}`);
    if (cardEl) {
      cardEl.style.transition = 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)';
      cardEl.style.opacity = '0';
      cardEl.style.transform = 'translateY(-10px) scale(0.98)';
      setTimeout(() => { if (cardEl && cardEl.parentNode) cardEl.remove(); }, 220);
    }
    qbankState.questions = qbankState.questions.filter(q => (q.key || q.id) !== key);
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: { [key]: newAnswer } }),
    });

    if (!res.ok) {
      throw new Error(`Failed to save answer (HTTP ${res.status})`);
    }

    const data = await res.json();
    delete qbankState.modifiedAnswers[key];

    if (data.answered_count !== undefined) {
      qbankState.answeredCount = data.answered_count;
      qbankState.pendingCount = data.pending_count;
      if (data.ai_suggested_count !== undefined) {
        qbankState.aiSuggestedCount = data.ai_suggested_count;
      }
      updateQuestionBankKpis();
      updateQuestionBankStatusSegmentUI();
    }

    // Refresh immediately from database (silent refresh keeps UI stable)
    await loadQuestionBankPage(true);

    if (typeof fetchStats === 'function') fetchStats();

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Answer Saved',
        message: newAnswer === '__EMPTY__' 
          ? 'Question configured to be submitted blank on applications.' 
          : 'Screening answer updated and synced for Easy Apply automation.',
        type: 'success',
        duration: 3500,
      });
    }

  } catch (err) {
    console.error('Error saving single answer:', err);
    await loadQuestionBankPage(true);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Save Failed',
        message: err.message || 'Could not update answer in database.',
        type: 'error',
      });
    }
  }
}

// --- Approve Single AI-Suggested Question Answer ---
async function approveSingleQuestionAnswer(key) {
  const textarea = document.getElementById(`qbankTextarea-${key}`);
  let newAnswer = qbankState.modifiedAnswers[key] !== undefined 
    ? qbankState.modifiedAnswers[key] 
    : (textarea ? textarea.value : '');

  // If answer is empty and not deliberately blank, alert user
  if (!newAnswer || !newAnswer.trim()) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Cannot Approve Empty Answer',
        message: 'Please provide an answer or click "Leave Blank" before approving.',
        type: 'warning',
        duration: 3500,
      });
    }
    return;
  }

  // 1. Immediately remove from DOM & local memory list (instant responsiveness)
  const cardEl = document.getElementById(`qbankCard-${key}`);
  const removedIdx = qbankState.questions.findIndex(q => (q.key || q.id) === key);
  let removedQ = null;
  if (removedIdx !== -1) {
    removedQ = qbankState.questions[removedIdx];
    qbankState.questions.splice(removedIdx, 1);
  }
  delete qbankState.modifiedAnswers[key];
  qbankState.selectedKeys.delete(key);

  // Optimistically update counts immediately
  qbankState.aiSuggestedCount = Math.max(0, (qbankState.aiSuggestedCount || 1) - 1);
  qbankState.answeredCount = (qbankState.answeredCount || 0) + 1;
  updateQuestionBankKpis();
  updateQuestionBankStatusSegmentUI();
  updateBatchBarUI();
  updateUnsavedToastUI();

  // Smoothly collapse and remove card element from DOM
  if (cardEl) {
    cardEl.style.transition = 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)';
    cardEl.style.opacity = '0';
    cardEl.style.transform = 'translateY(-10px) scale(0.98)';
    setTimeout(() => {
      if (cardEl && cardEl.parentNode) cardEl.remove();
      if (qbankState.questions.length === 0) {
        renderQuestionBankCards();
      }
    }, 220);
  } else if (qbankState.questions.length === 0) {
    renderQuestionBankCards();
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: { [key]: newAnswer } }),
    });

    if (!res.ok) {
      throw new Error(`Failed to approve answer (HTTP ${res.status})`);
    }

    const data = await res.json();

    if (data.answered_count !== undefined) {
      qbankState.answeredCount = data.answered_count;
      qbankState.pendingCount = data.pending_count;
      if (data.ai_suggested_count !== undefined) {
        qbankState.aiSuggestedCount = data.ai_suggested_count;
      }
      updateQuestionBankKpis();
      updateQuestionBankStatusSegmentUI();
    }

    // Refresh Question Bank list immediately from database (silent refresh keeps UI stable)
    await loadQuestionBankPage(true);

    if (typeof fetchStats === 'function') fetchStats();

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Answer Approved!',
        message: 'Promoted to Ready for Auto-Apply.',
        type: 'success',
        duration: 2500,
      });
    }

  } catch (err) {
    console.error('Error approving answer:', err);
    // Rollback question on network failure
    if (removedQ && removedIdx !== -1) {
      qbankState.questions.splice(removedIdx, 0, removedQ);
      renderQuestionBankCards();
    }
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Approval Failed',
        message: err.message || 'Could not approve answer in database.',
        type: 'error',
      });
    }
  }
}

// --- Save All Modified Answers in Batch ---
async function saveAllQuestionBankPageAnswers() {
  const keys = Object.keys(qbankState.modifiedAnswers);
  if (keys.length === 0) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'No Changes to Save',
        message: 'All screening answers are already synchronized.',
        type: 'info',
        duration: 3000,
      });
    }
    return;
  }

  const payload = { answers: {} };
  for (const k of keys) {
    payload.answers[k] = qbankState.modifiedAnswers[k];
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`Failed to batch save answers (HTTP ${res.status})`);
    }

    const data = await res.json();
    const savedCount = data.saved_count || keys.length;
    qbankState.modifiedAnswers = {};

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'All Changes Saved',
        message: `Successfully persisted ${savedCount} answers to Question Bank.`,
        type: 'success',
        duration: 4000,
      });
    }

    await loadQuestionBankPage();
    if (typeof fetchStats === 'function') fetchStats();

  } catch (err) {
    console.error('Error saving all answers:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Batch Save Failed',
        message: err.message || 'Could not save answers to database.',
        type: 'error',
      });
    }
  }
}

// --- Single Question Deletion ---
async function deleteSingleQuestion(key, questionText) {
  const confirmMsg = `Are you sure you want to delete this question from the Question Bank?\n\n"${questionText}"\n\nFuture Easy Apply submissions will not auto-fill this question.`;
  
  let confirmed = false;
  if (typeof showConfirm === 'function') {
    confirmed = await showConfirm(
      'Delete Screening Question',
      confirmMsg,
      { danger: true, confirmText: 'Delete Question' }
    );
  } else {
    confirmed = window.confirm(confirmMsg);
  }

  if (!confirmed) return;

  try {
    const res = await fetch(`/api/easy-apply/questions/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed with status ${res.status}`);
    }

    delete qbankState.modifiedAnswers[key];
    qbankState.selectedKeys.delete(key);

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Question Deleted',
        message: `Successfully deleted question from Question Bank.`,
        type: 'success',
        duration: 3500,
      });
    }

    await loadQuestionBankPage();
    if (typeof fetchStats === 'function') fetchStats();

  } catch (err) {
    console.error('Error deleting question:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Delete Failed',
        message: err.message || 'Could not delete question from database.',
        type: 'error',
      });
    }
  }
}

// --- Multi-Select & Batch Actions ---
function toggleQuestionSelection(key, checked) {
  if (checked) {
    qbankState.selectedKeys.add(key);
  } else {
    qbankState.selectedKeys.delete(key);
  }

  const card = document.getElementById(`qbankCard-${key}`);
  if (card) card.classList.toggle('is-selected', checked);

  updateBatchBarUI();
}

function toggleSelectAllQuestions(checked) {
  for (const q of qbankState.questions) {
    const key = q.key || q.id;
    if (checked) {
      qbankState.selectedKeys.add(key);
    } else {
      qbankState.selectedKeys.delete(key);
    }
  }

  const checkboxes = document.querySelectorAll('.qbank-item-checkbox');
  checkboxes.forEach(cb => { cb.checked = checked; });

  const cards = document.querySelectorAll('.qbank-card');
  cards.forEach(c => { c.classList.toggle('is-selected', checked); });

  updateBatchBarUI();
}

function clearQuestionBankSelection() {
  qbankState.selectedKeys.clear();

  const checkboxes = document.querySelectorAll('.qbank-item-checkbox');
  checkboxes.forEach(cb => { cb.checked = false; });

  const selectAll = document.getElementById('qbankSelectAllCheckbox');
  if (selectAll) selectAll.checked = false;

  const cards = document.querySelectorAll('.qbank-card');
  cards.forEach(c => { c.classList.remove('is-selected'); });

  updateBatchBarUI();
}

function updateBatchBarUI() {
  const batchBar = document.getElementById('qbankBatchBar');
  const countEl = document.getElementById('qbankBatchSelectedCount');
  const selectAllCb = document.getElementById('qbankSelectAllCheckbox');
  const count = qbankState.selectedKeys.size;

  if (batchBar && countEl) {
    countEl.textContent = `${count} selected`;
    if (count > 0) {
      batchBar.classList.remove('hidden');
    } else {
      batchBar.classList.add('hidden');
    }
  }

  if (selectAllCb) {
    const totalVisible = qbankState.questions.length;
    if (totalVisible > 0 && count === totalVisible) {
      selectAllCb.checked = true;
      selectAllCb.indeterminate = false;
    } else if (count > 0 && count < totalVisible) {
      selectAllCb.checked = false;
      selectAllCb.indeterminate = true;
    } else {
      selectAllCb.checked = false;
      selectAllCb.indeterminate = false;
    }
  }
}

async function triggerBatchDeleteQuestions() {
  const keys = Array.from(qbankState.selectedKeys);
  if (keys.length === 0) return;

  const confirmMsg = `Are you sure you want to delete ${keys.length} selected screening questions from the Question Bank?\n\nThis action cannot be undone.`;
  
  let confirmed = false;
  if (typeof showConfirm === 'function') {
    confirmed = await showConfirm(
      'Delete Selected Questions',
      confirmMsg,
      { danger: true, confirmText: `Delete ${keys.length} Questions` }
    );
  } else {
    confirmed = window.confirm(confirmMsg);
  }

  if (!confirmed) return;

  try {
    const res = await fetch('/api/easy-apply/questions/delete-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Batch delete failed with status ${res.status}`);
    }

    const data = await res.json();
    const deletedCount = data.deleted_count || keys.length;

    for (const k of keys) {
      delete qbankState.modifiedAnswers[k];
    }
    qbankState.selectedKeys.clear();

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Questions Deleted',
        message: `Successfully deleted ${deletedCount} questions from Question Bank.`,
        type: 'success',
        duration: 3500,
      });
    }

    await loadQuestionBankPage();
    if (typeof fetchStats === 'function') fetchStats();

  } catch (err) {
    console.error('Error in batch delete:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Batch Delete Failed',
        message: err.message || 'Could not delete selected questions from database.',
        type: 'error',
      });
    }
  }
}

// --- Batch Approve Selected Questions ---
async function triggerBatchApproveQuestions() {
  const selectedKeys = Array.from(qbankState.selectedKeys);
  if (selectedKeys.length === 0) return;

  // Gather answers for all selected questions
  const answersToApprove = {};
  let count = 0;
  for (const k of selectedKeys) {
    const q = qbankState.questions.find(item => (item.key || item.id) === k);
    let ans = qbankState.modifiedAnswers[k] !== undefined ? qbankState.modifiedAnswers[k] : (q ? q.answer : '');
    if (ans && (ans.trim() || ans === '__EMPTY__')) {
      answersToApprove[k] = ans;
      count++;
    }
  }

  if (count === 0) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'No Answers to Approve',
        message: 'None of the selected questions have answers provided. Please enter an answer or choose "Leave Blank" first.',
        type: 'warning',
        duration: 3500,
      });
    }
    return;
  }

  const approvedKeySet = new Set(Object.keys(answersToApprove));

  // 1. Instantly animate and remove cards from DOM
  approvedKeySet.forEach(k => {
    const cardEl = document.getElementById(`qbankCard-${k}`);
    if (cardEl) {
      cardEl.style.transition = 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)';
      cardEl.style.opacity = '0';
      cardEl.style.transform = 'translateY(-10px) scale(0.98)';
      setTimeout(() => {
        if (cardEl && cardEl.parentNode) cardEl.remove();
      }, 220);
    }
    delete qbankState.modifiedAnswers[k];
  });

  // Remove from state questions array immediately
  qbankState.questions = qbankState.questions.filter(q => !approvedKeySet.has(q.key || q.id));
  clearQuestionBankSelection();

  // Optimistically update counts immediately
  qbankState.aiSuggestedCount = Math.max(0, (qbankState.aiSuggestedCount || count) - count);
  qbankState.answeredCount = (qbankState.answeredCount || 0) + count;
  updateQuestionBankKpis();
  updateQuestionBankStatusSegmentUI();
  updateUnsavedToastUI();

  if (qbankState.questions.length === 0) {
    setTimeout(() => {
      renderQuestionBankCards();
    }, 230);
  }

  try {
    const res = await fetch('/api/easy-apply/questions/answers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: answersToApprove }),
    });

    if (!res.ok) {
      throw new Error(`Failed to batch approve (HTTP ${res.status})`);
    }

    const data = await res.json();

    if (data.answered_count !== undefined) {
      qbankState.answeredCount = data.answered_count;
      qbankState.pendingCount = data.pending_count;
      if (data.ai_suggested_count !== undefined) {
        qbankState.aiSuggestedCount = data.ai_suggested_count;
      }
      updateQuestionBankKpis();
      updateQuestionBankStatusSegmentUI();
    }

    // Refresh Question Bank list immediately from database (silent refresh keeps UI stable)
    await loadQuestionBankPage(true);

    if (typeof fetchStats === 'function') fetchStats();

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Batch Approved!',
        message: `Successfully approved ${count} question(s) and removed from review.`,
        type: 'success',
        duration: 3000,
      });
    }
  } catch (err) {
    console.error('Error in batch approve:', err);
    await loadQuestionBankPage(true);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Batch Approval Failed',
        message: err.message || 'Could not approve selected questions in database.',
        type: 'error',
      });
    }
  }
}

// --- Search & Filtering Handlers ---
function updateQuestionBankClearFiltersButton() {
  const btn = document.getElementById('btnClearQbankFilters');
  if (!btn) return;
  const isFiltered = (
    qbankState.statusFilter !== 'all' ||
    qbankState.categoryFilter !== 'all' ||
    Boolean(qbankState.searchQuery && qbankState.searchQuery.trim()) ||
    Boolean(qbankState.fromDate) ||
    Boolean(qbankState.toDate) ||
    (qbankState.sortBy && qbankState.sortBy !== 'occurrences')
  );
  btn.classList.toggle('hidden', !isFiltered);
}

function handleQuestionBankSearchInput(value) {
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', !value || !value.trim());
  }

  qbankState.searchQuery = value;
  clearTimeout(qbankState.searchDebounceTimer);
  qbankState.searchDebounceTimer = setTimeout(() => {
    updateQuestionBankClearFiltersButton();
    loadQuestionBankPage();
  }, 250);
}

function clearQuestionBankSearch() {
  const input = document.getElementById('qbankPageSearchInput');
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (input) input.value = '';
  if (clearBtn) clearBtn.classList.add('hidden');
  qbankState.searchQuery = '';
  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

function setQuestionBankStatusFilter(status) {
  if (qbankState.statusFilter === status) return;
  qbankState.statusFilter = status;
  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

function setQuestionBankCategoryFilter(cat) {
  qbankState.categoryFilter = cat;
  const select = document.getElementById('selectQbankCategory');
  if (select) select.value = cat;
  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

function setQuestionBankSort(sortVal) {
  qbankState.sortBy = sortVal;
  const select = document.getElementById('selectQbankSort');
  if (select) select.value = sortVal;
  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

function applyQuestionBankDateFilter() {
  const fromEl = document.getElementById('qbankDateFrom');
  const toEl = document.getElementById('qbankDateTo');
  qbankState.fromDate = fromEl ? fromEl.value.trim() : '';
  qbankState.toDate = toEl ? toEl.value.trim() : '';
  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

function resetQuestionBankFilters() {
  qbankState.statusFilter = 'all';
  qbankState.categoryFilter = 'all';
  qbankState.searchQuery = '';
  qbankState.sortBy = 'occurrences';
  qbankState.fromDate = '';
  qbankState.toDate = '';

  const searchInput = document.getElementById('qbankPageSearchInput');
  if (searchInput) searchInput.value = '';
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (clearBtn) clearBtn.classList.add('hidden');

  const catSelect = document.getElementById('selectQbankCategory');
  if (catSelect) catSelect.value = 'all';

  const sortSelect = document.getElementById('selectQbankSort');
  if (sortSelect) sortSelect.value = 'occurrences';

  const fromEl = document.getElementById('qbankDateFrom');
  if (fromEl) fromEl.value = '';
  const toEl = document.getElementById('qbankDateTo');
  if (toEl) toEl.value = '';

  updateQuestionBankClearFiltersButton();
  loadQuestionBankPage();
}

// --- Add Question Modal ---
function openAddQuestionModal() {
  const modal = document.getElementById('modalAddQuestion');
  const form = document.getElementById('formAddQuestion');
  if (form) form.reset();
  if (modal) modal.classList.remove('hidden');

  setTimeout(() => {
    const input = document.getElementById('inputAddQuestionText');
    if (input) input.focus();
  }, 100);
}

function closeAddQuestionModal(event) {
  if (event && event.target && event.target.id !== 'modalAddQuestion') {
    return;
  }
  const modal = document.getElementById('modalAddQuestion');
  if (modal) modal.classList.add('hidden');
}

async function submitAddQuestion(event) {
  if (event) event.preventDefault();

  const qText = (document.getElementById('inputAddQuestionText')?.value || '').trim();
  const category = document.getElementById('selectAddQuestionCategory')?.value || 'profile';
  const placeholder = (document.getElementById('inputAddQuestionPlaceholder')?.value || '').trim();
  const optionsRaw = (document.getElementById('inputAddQuestionOptions')?.value || '').trim();
  const answer = (document.getElementById('inputAddQuestionAnswer')?.value || '').trim();

  const options = optionsRaw ? optionsRaw.split(',').map(s => s.trim()).filter(Boolean) : null;

  if (!qText) {
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Missing Question Prompt',
        message: 'Please provide the question prompt text.',
        type: 'warn',
      });
    }
    return;
  }

  const submitBtn = document.getElementById('btnSubmitAddQuestion');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Adding...</span>';
  }

  try {
    const res = await fetch('/api/easy-apply/questions/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: qText,
        category: category,
        default_placeholder: placeholder || null,
        answer: answer || null,
        options: options,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to create question (HTTP ${res.status})`);
    }

    closeAddQuestionModal();

    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Question Added',
        message: `"${qText}" added to the Question Bank.`,
        type: 'success',
        duration: 3500,
      });
    }

    await loadQuestionBankPage();
    if (typeof fetchStats === 'function') fetchStats();

  } catch (err) {
    console.error('Error creating question:', err);
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Creation Failed',
        message: err.message || 'Could not add question to database.',
        type: 'error',
      });
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Add to Question Bank</span>';
    }
  }
}

function toggleMoreSampleJobs(btn, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const wrap = btn ? btn.closest('.sample-job-more-wrap') : null;
  if (!wrap) return;
  const exp = wrap.querySelector('.sample-jobs-expanded');
  if (!exp) return;
  const isHidden = exp.style.display === 'none' || exp.classList.contains('hidden');
  if (isHidden) {
    exp.style.display = 'inline-flex';
    exp.classList.remove('hidden');
    btn.style.display = 'none';
  } else {
    exp.style.display = 'none';
    exp.classList.add('hidden');
    btn.style.display = 'inline-flex';
  }
}

function handleSampleJobClick(btn, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const jobLabel = btn ? (btn.getAttribute('data-job') || btn.textContent) : '';
  const locHint = btn ? (btn.getAttribute('data-loc') || '') : '';
  if (typeof navigateToJobInEasyApply === 'function') {
    navigateToJobInEasyApply(jobLabel, event, locHint);
  } else {
    console.warn('navigateToJobInEasyApply is not defined yet');
  }
}

// Global window registrations
window.qbankState = qbankState;
window.toggleMoreSampleJobs = toggleMoreSampleJobs;
window.handleSampleJobClick = handleSampleJobClick;
window.loadQuestionBankPage = loadQuestionBankPage;
window.renderQuestionBankCards = renderQuestionBankCards;
window.handleQuestionBankSearchInput = handleQuestionBankSearchInput;
window.clearQuestionBankSearch = clearQuestionBankSearch;
window.setQuestionBankStatusFilter = setQuestionBankStatusFilter;
window.setQuestionBankCategoryFilter = setQuestionBankCategoryFilter;
window.setQuestionBankSort = setQuestionBankSort;
window.applyQuestionBankDateFilter = applyQuestionBankDateFilter;
window.resetQuestionBankFilters = resetQuestionBankFilters;
window.handleQuestionBankAnswerInput = handleQuestionBankAnswerInput;
window.saveSingleQuestionAnswer = saveSingleQuestionAnswer;
window.saveAllQuestionBankPageAnswers = saveAllQuestionBankPageAnswers;
window.discardQuestionBankEdits = discardQuestionBankEdits;
window.deleteSingleQuestion = deleteSingleQuestion;
window.toggleQuestionSelection = toggleQuestionSelection;
window.toggleSelectAllQuestions = toggleSelectAllQuestions;
window.clearQuestionBankSelection = clearQuestionBankSelection;
window.triggerBatchDeleteQuestions = triggerBatchDeleteQuestions;
window.openAddQuestionModal = openAddQuestionModal;
window.closeAddQuestionModal = closeAddQuestionModal;
window.submitAddQuestion = submitAddQuestion;
