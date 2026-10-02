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
  pendingCount: 0,
  statusFilter: 'all', // 'all' | 'pending' | 'answered'
  categoryFilter: 'all',
  searchQuery: '',
  sortBy: 'occurrences',
  selectedKeys: new Set(),
  modifiedAnswers: {}, // key -> newAnswer
  isLoading: false,
  searchDebounceTimer: null,
};

// --- Page Initialization & Data Fetching ---
async function loadQuestionBankPage() {
  qbankState.isLoading = true;
  updateQuestionBankLoadingUI(true);

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

    const res = await fetch(`/api/easy-apply/questions?${params.toString()}`);
    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    qbankState.questions = data.questions || [];
    qbankState.totalCount = data.total_count || 0;
    qbankState.answeredCount = data.answered_count || 0;
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
    updateQuestionBankLoadingUI(false);
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

  // Also update sidebar badge in real-time
  const countQBankEl = document.getElementById('countSidebarQuestionBank');
  if (countQBankEl) {
    countQBankEl.textContent = qbankState.pendingCount;
    countQBankEl.style.display = qbankState.pendingCount > 0 ? 'inline-flex' : 'none';
  }
}

// --- Update Status Segmented Buttons UI ---
function updateQuestionBankStatusSegmentUI() {
  const btnAll = document.getElementById('btnQbankStatAll');
  const btnPending = document.getElementById('btnQbankStatPending');
  const btnAnswered = document.getElementById('btnQbankStatAnswered');

  if (btnAll) btnAll.classList.toggle('active', qbankState.statusFilter === 'all');
  if (btnPending) btnPending.classList.toggle('active', qbankState.statusFilter === 'pending');
  if (btnAnswered) btnAnswered.classList.toggle('active', qbankState.statusFilter === 'answered');

  const countAll = document.getElementById('qbankCountStatAll');
  if (countAll) countAll.textContent = qbankState.totalCount;

  const countPending = document.getElementById('qbankCountStatPending');
  if (countPending) countPending.textContent = qbankState.pendingCount;

  const countAnswered = document.getElementById('qbankCountStatAnswered');
  if (countAnswered) countAnswered.textContent = qbankState.answeredCount;
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
    const isAnswered = isBlank || Boolean(currentAnswer && currentAnswer.trim());
    const occurrences = q.occurrences || 1;
    const isStandard = Boolean(q.is_standard);
    const category = (q.category || 'profile').toLowerCase();
    const placeholder = isBlank 
      ? '(Intentionally left blank / N/A — will submit empty on apply)' 
      : (q.default_placeholder || 'Enter your standard answer...');

    // Sample jobs preview
    let sampleJobsHtml = '';
    if (Array.isArray(q.sample_jobs) && q.sample_jobs.length > 0) {
      const topJobs = q.sample_jobs.slice(0, 3);
      const tags = topJobs.map(j => `<span class="sample-job-tag" title="${escapeFn(j)}">${escapeFn(j)}</span>`).join('');
      const moreCount = q.sample_jobs.length - topJobs.length;
      const moreTag = moreCount > 0 ? `<span class="sample-job-tag">+${moreCount} more</span>` : '';
      sampleJobsHtml = `
        <div class="qbank-sample-jobs">
          <span>Found on:</span>
          ${tags}
          ${moreTag}
        </div>
      `;
    }

    // Status badge
    let statusBadgeHtml = '';
    if (isBlank) {
      statusBadgeHtml = `<span class="qbank-badge badge-blank" title="Configured to leave blank on applications">🚫 Blank / N/A</span>`;
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

    const cardStatusClass = isAnswered ? 'status-answered' : 'status-pending';
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
              <div class="qbank-status-text ${hasUnsavedEdit ? 'modified' : (isAnswered ? 'saved' : '')}" id="qbankFooterStatus-${escapeFn(key)}">
                ${hasUnsavedEdit ? '⚠️ Modified (Unsaved)' : (isBlank ? '✓ Auto-cleared on apply' : (isAnswered ? '✓ Auto-fill Ready' : 'Empty response'))}
              </div>
            </div>
            <button 
              type="button"
              class="card-save-btn ${hasUnsavedEdit ? '' : 'btn-disabled'}" 
              id="btnCardSave-${escapeFn(key)}" 
              onclick="saveSingleQuestionAnswer('${escapeFn(key)}')"
              title="Save changes to this question"
            >
              Save Answer
            </button>
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

  const card = document.getElementById(`qbankCard-${key}`);
  const textarea = document.getElementById(`qbankTextarea-${key}`);
  const footerStatus = document.getElementById(`qbankFooterStatus-${key}`);
  const saveBtn = document.getElementById(`btnCardSave-${key}`);
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
      footerStatus.textContent = isBlank ? '⚠️ Set to Blank (Unsaved)' : '⚠️ Modified (Unsaved)';
    }
    if (saveBtn) saveBtn.classList.remove('btn-disabled');
  } else {
    delete qbankState.modifiedAnswers[key];
    if (textarea) textarea.classList.remove('is-dirty');
    if (footerStatus) {
      const isAns = isBlank || Boolean(originalAnswer);
      footerStatus.className = `qbank-status-text ${isAns ? 'saved' : ''}`;
      footerStatus.textContent = isBlank ? '✓ Auto-cleared on apply' : (isAns ? '✓ Auto-fill Ready' : 'Empty response');
    }
    if (saveBtn) saveBtn.classList.add('btn-disabled');
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

    // Update local state item
    const targetQ = qbankState.questions.find(q => (q.key || q.id) === key);
    if (targetQ) {
      targetQ.answer = newAnswer;
      targetQ.status = (newAnswer.trim() || newAnswer === '__EMPTY__') ? 'ANSWERED' : 'PENDING';
    }

    if (data.answered_count !== undefined) {
      qbankState.answeredCount = data.answered_count;
      qbankState.pendingCount = data.pending_count;
      updateQuestionBankKpis();
      updateQuestionBankStatusSegmentUI();
    }

    // Refresh card UI
    renderQuestionBankCards();
    updateUnsavedToastUI();

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
    if (typeof showSnackbar === 'function') {
      showSnackbar({
        title: 'Save Failed',
        message: err.message || 'Could not update answer in database.',
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

// --- Search & Filtering Handlers ---
function handleQuestionBankSearchInput(value) {
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (clearBtn) {
    clearBtn.classList.toggle('hidden', !value || !value.trim());
  }

  qbankState.searchQuery = value;
  clearTimeout(qbankState.searchDebounceTimer);
  qbankState.searchDebounceTimer = setTimeout(() => {
    loadQuestionBankPage();
  }, 250);
}

function clearQuestionBankSearch() {
  const input = document.getElementById('qbankPageSearchInput');
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (input) input.value = '';
  if (clearBtn) clearBtn.classList.add('hidden');
  qbankState.searchQuery = '';
  loadQuestionBankPage();
}

function setQuestionBankStatusFilter(status) {
  if (qbankState.statusFilter === status) return;
  qbankState.statusFilter = status;
  loadQuestionBankPage();
}

function setQuestionBankCategoryFilter(cat) {
  qbankState.categoryFilter = cat;
  const select = document.getElementById('selectQbankCategory');
  if (select) select.value = cat;
  loadQuestionBankPage();
}

function setQuestionBankSort(sortVal) {
  qbankState.sortBy = sortVal;
  const select = document.getElementById('selectQbankSort');
  if (select) select.value = sortVal;
  loadQuestionBankPage();
}

function resetQuestionBankFilters() {
  qbankState.statusFilter = 'all';
  qbankState.categoryFilter = 'all';
  qbankState.searchQuery = '';
  qbankState.sortBy = 'occurrences';

  const searchInput = document.getElementById('qbankPageSearchInput');
  if (searchInput) searchInput.value = '';
  const clearBtn = document.getElementById('btnQbankSearchClear');
  if (clearBtn) clearBtn.classList.add('hidden');

  const catSelect = document.getElementById('selectQbankCategory');
  if (catSelect) catSelect.value = 'all';

  const sortSelect = document.getElementById('selectQbankSort');
  if (sortSelect) sortSelect.value = 'occurrences';

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

// Global window registrations
window.qbankState = qbankState;
window.loadQuestionBankPage = loadQuestionBankPage;
window.renderQuestionBankCards = renderQuestionBankCards;
window.handleQuestionBankSearchInput = handleQuestionBankSearchInput;
window.clearQuestionBankSearch = clearQuestionBankSearch;
window.setQuestionBankStatusFilter = setQuestionBankStatusFilter;
window.setQuestionBankCategoryFilter = setQuestionBankCategoryFilter;
window.setQuestionBankSort = setQuestionBankSort;
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
