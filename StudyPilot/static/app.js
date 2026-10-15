const state = {
  user: null,
  questions: [],
  answers: new Map(),
  mode: 'diagnostic',
  focusTopic: null,
  activeSubject: null,
  lastResult: null,
  dashboard: null,
};
const $ = (id) => document.getElementById(id);
const views = ['overviewView', 'quizView', 'resultsView', 'historyView'];
let toastTimer = null;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function notify(message, kind = 'success') {
  const el = $('toast');
  el.textContent = message;
  el.className = `toast ${kind}`;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3200);
}
function setAuthMessage(message, kind = 'error') {
  const el = $('authMessage');
  el.textContent = message;
  el.className = `auth-message ${kind}`;
}
function clearAuthMessage() { $('authMessage').classList.add('hidden'); }
async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  let data = {};
  try { data = await response.json(); } catch { /* server returned no JSON */ }
  if (!response.ok) {
    if (response.status === 401) showAuth();
    throw new Error(data.error || `Request failed (${response.status})`);
  }
  return data;
}
function showAuth() {
  $('appView').classList.add('hidden');
  $('authView').classList.remove('hidden');
  setAuthTab('login');
}
function setAuthTab(tab) {
  const login = tab === 'login';
  $('loginTab').classList.toggle('active', login);
  $('registerTab').classList.toggle('active', !login);
  $('loginForm').classList.toggle('hidden', !login);
  $('registerForm').classList.toggle('hidden', login);
  $('authTitle').textContent = login ? 'Welcome back' : 'Create your learning space';
  $('authSubtitle').textContent = login ? 'Pick up where your learning left off.' : 'A few details help us shape your learning path.';
  clearAuthMessage();
}
function setView(viewId, title) {
  views.forEach((id) => $(id).classList.toggle('hidden', id !== viewId));
  $('pageTitle').textContent = title;
  $('navOverview').classList.toggle('active', viewId === 'overviewView');
  $('navPlan').classList.toggle('active', false);
  $('navHistory').classList.toggle('active', viewId === 'historyView');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function cleanName(name) {
  const trimmed = String(name || 'Student').trim().slice(0, 70);
  return trimmed || 'Student';
}
function setLoading(el, loading) { if (el) el.classList.toggle('loading', loading); }
function setBusy(button, busy, text) {
  if (!button) return;
  button.disabled = busy;
  if (busy) { button.dataset.originalText = button.innerHTML; button.textContent = text || 'Please wait…'; }
  else if (button.dataset.originalText) button.innerHTML = button.dataset.originalText;
}
function populateSubjectSelect(gradeSelect, subjectSelect, selected = '') {
  const grade = gradeSelect.value;
  api(`/api/subjects?grade=${encodeURIComponent(grade)}`).then((data) => {
    subjectSelect.innerHTML = data.subjects.map((subject) => `<option value="${escapeHtml(subject)}">${escapeHtml(subject)}</option>`).join('');
    if (selected && data.subjects.includes(selected)) subjectSelect.value = selected;
  }).catch((error) => notify(error.message, 'error'));
}
async function enterApp(user = null) {
  if (user) state.user = user;
  $('authView').classList.add('hidden');
  $('appView').classList.remove('hidden');
  await refreshDashboard();
}
async function refreshDashboard() {
  try {
    const data = await api('/api/dashboard');
    state.dashboard = data;
    state.user = data.user;
    renderDashboard(data);
  } catch (error) {
    if (!$('appView').classList.contains('hidden')) notify(error.message, 'error');
  }
}
function renderDashboard(data) {
  const user = data.user;
  $('userName').textContent = user.name;
  $('userGradeTop').textContent = `${user.grade} · ${user.subject}`;
  $('sideGrade').textContent = user.grade;
  $('sideSubject').textContent = user.subject;
  $('heroGrade').textContent = user.grade;
  $('subjectChip').textContent = user.subject;
  $('gradeChip').textContent = user.grade;
  $('avatar').textContent = (user.name || 'S').trim().charAt(0).toUpperCase();
  $('heroScore').textContent = data.average_score === null ? '—' : `${data.average_score}%`;
  $('heroScoreNote').textContent = data.average_score === null ? 'Your baseline begins here' : 'Small steps add up';
  $('averageStat').innerHTML = data.average_score === null ? '—<small>%</small>' : `${data.average_score}<small>%</small>`;
  $('averageNote').textContent = data.average_score === null ? 'Take a diagnostic to set your baseline' : 'Based on your latest topic results';
  $('assessedStat').innerHTML = `${data.topics_assessed}<small> / ${data.total_topics}</small>`;
  $('attemptsStat').textContent = data.total_attempts;
  state.activeSubject = user.subject;
  renderTopicList(data.topic_scores || []);
  const scored = (data.topic_scores || []).filter((item) => item.score !== null);
  if (scored.length) renderRecommendationCard((data.study_plan || [])[0], 'nextStepContent', true, scored);
  else renderIntroRecommendation();
  renderStudyPlan(data.study_plan || [], 'studyPlan');
}
function renderTopicList(items) {
  const colors = ['','blue','mint','orange'];
  $('topicList').innerHTML = items.map((item, index) => {
    const assessed = item.score !== null && item.score !== undefined;
    const score = assessed ? Number(item.score) : 0;
    const colorClass = colors[index % colors.length];
    return `<div class="topic-row" style="animation-delay:${index * 55}ms"><div class="topic-name">${escapeHtml(item.topic)}</div><div class="mastery-track"><div class="mastery-fill ${colorClass}" style="width:${assessed ? score : 6}%;opacity:${assessed ? 1 : .26}"></div></div><div class="topic-score ${assessed ? '' : 'unassessed'}">${assessed ? `${score}%` : 'Not yet'}</div>${assessed ? '' : `<div class="topic-status">Awaiting diagnostic result</div>`}</div>`;
  }).join('');
}
function renderIntroRecommendation() {
  const first = state.dashboard?.study_plan?.[0];
  $('nextStepContent').innerHTML = `<div class="recommendation-placeholder"><div class="target-art">◎</div><b>Let's find your focus</b><p>${first ? `Start with ${escapeHtml(first.topic)}. Take the diagnostic to replace the starting estimate with your real score.` : 'Take a quick diagnostic to find the topics that need your attention.'}</p><button class="button button-primary" id="startDiagnosticPanel">Find my focus <span>→</span></button></div>`;
  $('startDiagnosticPanel').addEventListener('click', () => startQuiz('diagnostic'));
}
function renderRecommendationCard(item, elementId, withButton = false, scored = []) {
  const host = $(elementId);
  if (!item) { host.innerHTML = '<div class="recommendation-placeholder"><b>Take a quick diagnostic first</b></div>'; return; }
  const unassessed = item.score === null || item.score === undefined;
  const text = unassessed
    ? 'We have not measured this topic yet. A short diagnostic will replace the estimate with your actual performance.'
    : `Your latest score is ${item.score}%. ${item.score < 40 ? 'This topic needs attention first, so start with the core concept and one worked example.' : item.score < 70 ? 'A focused review can help strengthen this concept before moving on.' : 'You are doing well here; use mixed practice to retain the skill.'}`;
  host.innerHTML = `<div class="recommendation-card"><div class="rec-label">${unassessed ? 'FIRST STEP' : 'HIGHEST PRIORITY'}</div><h4 class="rec-title">${escapeHtml(item.topic)}</h4><p class="rec-explanation">${escapeHtml(text)}</p><div class="rec-meta"><span class="rec-score">${unassessed ? 'Baseline needed' : `${item.score}% mastery`}</span><span class="rec-pill">Priority ${Number(item.priority).toFixed(0)}/100</span></div>${withButton ? '<button class="button button-primary button-small" id="recPracticeBtn" style="margin-top:14px">Start focused practice <span>→</span></button>' : ''}</div>`;
  if (withButton) {
    $('recPracticeBtn').addEventListener('click', () => {
      if (unassessed) startQuiz('diagnostic');
      else startQuiz('targeted', item.topic);
    });
  }
}
function renderStudyPlan(plan, targetId) {
  const target = $(targetId);
  if (!plan.length) {
    target.innerHTML = '<div class="plan-empty"><span class="plan-empty-icon">◷</span><b>Your plan will appear here</b><p>Complete a diagnostic to get your personalised steps.</p></div>';
    return;
  }
  target.innerHTML = plan.map((item, i) => `<div class="plan-row" style="animation-delay:${i * 60}ms"><div class="plan-order">${item.order}</div><div class="plan-main"><strong>${escapeHtml(item.topic)} <span style="font-weight:500;color:#9296ab">· ${escapeHtml(item.priority_label)}</span></strong><p>${escapeHtml(item.action)}</p></div><div class="plan-minutes">${item.minutes} min</div></div>`).join('');
}
async function startQuiz(mode = 'diagnostic', topic = null) {
  if (!state.user) return showAuth();
  state.mode = mode; state.focusTopic = topic; state.answers = new Map();
  const subject = state.user.subject;
  setLoading($('quizView'), true);
  try {
    const query = new URLSearchParams({ mode, subject, ...(topic ? { topic } : {}) });
    const data = await api(`/api/questions?${query.toString()}`);
    state.questions = data.questions; state.activeSubject = data.subject;
    $('quizTypeTag').textContent = mode === 'targeted' ? 'FOCUSED PRACTICE' : 'DIAGNOSTIC QUIZ';
    $('quizHeading').textContent = mode === 'targeted' ? `Let's strengthen ${topic}.` : `Let's map what you know in ${subject}.`;
    $('quizIntro').textContent = mode === 'targeted' ? `These questions focus on ${topic}. Your updated score will help us choose the next best step.` : `A short assessment for ${state.user.grade}. Answer honestly; your results will guide your study plan.`;
    $('submitQuiz').innerHTML = mode === 'targeted' ? 'Check my progress <span>→</span>' : 'Reveal my study plan <span>→</span>';
    $('quizGradeSide').textContent = state.user.grade; $('quizSubjectSide').textContent = subject;
    renderQuestions(); setView('quizView', mode === 'targeted' ? 'Focused practice' : 'Quick diagnostic');
  } catch (error) { notify(error.message, 'error'); }
  finally { setLoading($('quizView'), false); }
}
function renderQuestions() {
  $('questionsContainer').innerHTML = state.questions.map((question, index) => `
    <article class="question-card" data-question-id="${question.id}" style="animation-delay:${index * 45}ms">
      <div class="question-meta"><span class="question-number">${String(index + 1).padStart(2, '0')}</span><span>${escapeHtml(question.topic)}</span></div>
      <p class="question-text">${escapeHtml(question.text)}</p>
      <div class="option-list">${question.options.map((option, optionIndex) => `<label class="answer-option"><input type="radio" name="q-${question.id}" value="${optionIndex}"><span>${escapeHtml(option)}</span></label>`).join('')}</div>
    </article>`).join('');
  $('questionsContainer').querySelectorAll('input[type="radio"]').forEach((input) => input.addEventListener('change', (event) => {
    const card = event.target.closest('[data-question-id]');
    state.answers.set(Number(card.dataset.questionId), Number(event.target.value));
    updateQuizProgress();
  }));
  updateQuizProgress();
}
function updateQuizProgress() {
  const total = state.questions.length || 1; const answered = state.answers.size;
  const percent = Math.round(answered * 100 / total);
  $('progressLabel').textContent = `${answered} of ${total} answered`;
  $('progressPercent').textContent = `${percent}% complete`;
  $('quizProgress').style.width = `${percent}%`;
  $('answerHint').textContent = answered === total ? 'Everything answered. Ready to see your next steps.' : `${total - answered} question${total - answered === 1 ? '' : 's'} left to answer.`;
}
async function submitQuiz(event) {
  event.preventDefault();
  if (state.answers.size !== state.questions.length) {
    const first = state.questions.find((q) => !state.answers.has(q.id));
    notify('Answer every question first. We have highlighted the first one to finish.', 'error');
    const card = document.querySelector(`[data-question-id="${first.id}"]`);
    card?.scrollIntoView({ behavior: 'smooth', block: 'center' }); card?.classList.add('highlight-missing');
    setTimeout(() => card?.classList.remove('highlight-missing'), 1200); return;
  }
  const button = $('submitQuiz'); button.disabled = true; button.textContent = 'Building your plan…';
  try {
    const result = await api('/api/submit', { method: 'POST', body: JSON.stringify({ mode: state.mode, topic: state.focusTopic, subject: state.activeSubject, study_minutes: Number($('studyMinutes').value || 30), answers: [...state.answers.entries()].map(([question_id, selected_index]) => ({ question_id, selected_index })) }) });
    state.lastResult = result; renderResults(result); await refreshDashboard(); setView('resultsView', 'Your results');
  } catch (error) { notify(error.message, 'error'); }
  finally { button.disabled = false; button.innerHTML = state.mode === 'targeted' ? 'Check my progress <span>→</span>' : 'Reveal my study plan <span>→</span>'; }
}
function renderResults(result) {
  const focused = result.mode === 'targeted';
  $('resultTitle').textContent = focused ? 'Your practice is moving you forward.' : 'Your learning map is ready.';
  $('resultSubtitle').textContent = `${result.correct} of ${result.total} correct · ${focused ? `Focused practice: ${result.topic}` : 'Diagnostic assessment'} · Your next steps are below.`;
  $('overallScore').textContent = `${result.score}%`;
  $('overallScoreCircle').style.background = `conic-gradient(#b2a7ff ${result.score}%, rgba(255,255,255,.18) ${result.score}% 100%)`;
  $('resultSubjectChip').textContent = `${state.user.grade} · ${result.subject}`;
  $('resultTopicList').innerHTML = (result.topic_results || []).map((item, index) => {
    const change = item.change == null ? 'Baseline set' : `${item.change > 0 ? '+' : ''}${item.change} pts vs previous`;
    const klass = item.change > 0 ? 'positive' : item.change < 0 ? 'negative' : '';
    return `<div class="result-topic-card" style="animation:rise .35s ease ${index * 50}ms both"><div class="result-topic-top"><strong>${escapeHtml(item.topic)}</strong><span>${item.score}%</span></div><div class="mastery-track"><div class="mastery-fill" style="width:${item.score}%"></div></div><div class="result-topic-bottom"><span>${item.correct}/${item.total} correct</span><span class="change-pill ${klass}">${escapeHtml(change)}</span></div></div>`;
  }).join('');
  if (result.recommendation) renderRecommendationCard(result.recommendation, 'resultRecommendation', false);
  else $('resultRecommendation').innerHTML = '<p class="quiz-intro">Complete a diagnostic to get your next step.</p>';
  $('resultPlanPreview').innerHTML = (result.study_plan || []).slice(0, 3).map((item) => `<div class="preview-row"><span class="preview-check">${item.order}</span><div><strong>${escapeHtml(item.topic)} · ${item.minutes} min</strong><p>${escapeHtml(item.action)}</p></div></div>`).join('') || '<p class="quiz-intro">No study tasks yet.</p>';
  const weakest = [...(result.topic_scores || [])].sort((a,b) => a.score - b.score)[0];
  $('startTargeted').disabled = !weakest;
  $('startTargeted').onclick = () => weakest && startQuiz('targeted', weakest.topic);
}
async function showHistory() {
  setView('historyView', 'Progress history');
  try {
    const data = await api('/api/history'); $('historyTotal').textContent = data.attempts.length;
    if (!data.attempts.length) { $('historyList').innerHTML = '<div class="empty-state"><div class="empty-art">◷</div><b>Your first session is waiting</b><p>Your completed quizzes will appear here. They are saved to your account for next time.</p></div>'; return; }
    $('historyList').innerHTML = data.attempts.map((a, i) => {
      let when = a.created_at; try { when = new Date(a.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); } catch {}
      const kind = a.attempt_type === 'diagnostic' ? 'Diagnostic assessment' : `Focused practice · ${a.focus_topic || 'Topic'}`;
      return `<div class="history-row" style="animation:rise .3s ease ${i * 35}ms both"><div><div class="history-title">${escapeHtml(kind)}</div><div class="history-sub">${escapeHtml(a.grade)} · ${escapeHtml(a.subject)} · ${escapeHtml(when)} · ${a.total_score}/${a.total_questions} correct</div></div><div class="history-score">${a.score_percent}%</div><span class="history-badge">${a.attempt_type === 'diagnostic' ? 'DIAGNOSTIC' : 'PRACTICE'}</span></div>`;
    }).join('');
  } catch (error) { notify(error.message, 'error'); }
}
async function updatePlan() {
  try {
    const minutes = Number($('studyMinutes').value || 30);
    const data = await api(`/api/plan?minutes=${minutes}&subject=${encodeURIComponent(state.user.subject)}`);
    renderStudyPlan(data.study_plan, 'studyPlan'); notify(`Your ${minutes}-minute plan is refreshed.`);
  } catch (error) { notify(error.message, 'error'); }
}
function openPathModal() {
  $('pathGrade').value = state.user.grade;
  populateSubjectSelect($('pathGrade'), $('pathSubject'), state.user.subject);
  $('pathModal').classList.remove('hidden');
}
function closePathModal() { $('pathModal').classList.add('hidden'); }
async function savePath(event) {
  event.preventDefault(); const button = $('pathForm').querySelector('button[type="submit"]'); setBusy(button, true, 'Saving your learning path…');
  try {
    const result = await api('/api/profile', { method: 'POST', body: JSON.stringify({ grade: $('pathGrade').value, subject: $('pathSubject').value }) });
    state.user = result.user; closePathModal(); await refreshDashboard(); setView('overviewView', 'Your overview'); notify('Your learning path is saved. The question set now matches your selection.');
  } catch (error) { notify(error.message, 'error'); }
  finally { setBusy(button, false); }
}
async function handleRegister(event) {
  event.preventDefault(); const button = $('registerButton'); setBusy(button, true, 'Creating your workspace…'); clearAuthMessage();
  try {
    const result = await api('/api/register', { method: 'POST', body: JSON.stringify({ name: $('registerName').value, email: $('registerEmail').value, password: $('registerPassword').value, grade: $('registerGrade').value, subject: $('registerSubject').value }) });
    state.user = result.user; await enterApp(result.user); notify(`Welcome, ${result.user.name}! Your profile is saved.`);
  } catch (error) { setAuthMessage(error.message); }
  finally { setBusy(button, false); }
}
async function handleLogin(event) {
  event.preventDefault(); const button = $('loginButton'); setBusy(button, true, 'Signing you in…'); clearAuthMessage();
  try {
    const result = await api('/api/login', { method: 'POST', body: JSON.stringify({ email: $('loginEmail').value, password: $('loginPassword').value }) });
    state.user = result.user; await enterApp(result.user); notify(`Welcome back, ${result.user.name}.`);
  } catch (error) { setAuthMessage(error.message); }
  finally { setBusy(button, false); }
}
async function handleDemoLogin() {
  const button = $('demoLogin'); setBusy(button, true, 'Opening the demo…'); clearAuthMessage();
  try { await api('/api/demo-login', { method: 'POST', body: JSON.stringify({}) }); await enterApp(); notify('Demo workspace opened. Try the Class 8 Science assessment.'); }
  catch (error) { setAuthMessage(error.message); }
  finally { setBusy(button, false); }
}
async function logout() {
  try { await api('/api/logout', { method: 'POST', body: JSON.stringify({}) }); }
  catch { /* a stale session is okay to clear on the client */ }
  state.user = null; state.dashboard = null; state.questions = []; state.answers.clear(); $('userPopover').classList.add('hidden'); showAuth(); notify('You have logged out. Your progress is saved to your account.');
}

$('loginTab').addEventListener('click', () => setAuthTab('login'));
$('registerTab').addEventListener('click', () => setAuthTab('register'));
$('loginForm').addEventListener('submit', handleLogin);
$('registerForm').addEventListener('submit', handleRegister);
$('demoLogin').addEventListener('click', handleDemoLogin);
$('registerGrade').addEventListener('change', () => populateSubjectSelect($('registerGrade'), $('registerSubject')));
$('pathGrade').addEventListener('change', () => populateSubjectSelect($('pathGrade'), $('pathSubject')));
$('pathForm').addEventListener('submit', savePath);
$('closePathModal').addEventListener('click', closePathModal);
$('pathModal').addEventListener('click', (event) => { if (event.target === $('pathModal')) closePathModal(); });
document.querySelectorAll('.password-toggle').forEach((button) => button.addEventListener('click', () => {
  const input = $(button.dataset.target); input.type = input.type === 'password' ? 'text' : 'password'; button.textContent = input.type === 'password' ? '◉' : '◎';
}));
$('startDiagnosticTop').addEventListener('click', () => startQuiz('diagnostic'));
$('startDiagnosticPanel').addEventListener('click', () => startQuiz('diagnostic'));
$('startPlanQuiz').addEventListener('click', () => startQuiz('diagnostic'));
$('submitQuiz').closest('form').addEventListener('submit', submitQuiz);
$('cancelQuiz').addEventListener('click', () => { setView('overviewView', 'Your overview'); refreshDashboard(); });
$('againDiagnostic').addEventListener('click', () => startQuiz('diagnostic'));
$('backOverview').addEventListener('click', () => { setView('overviewView', 'Your overview'); refreshDashboard(); });
$('navOverview').addEventListener('click', () => { setView('overviewView', 'Your overview'); refreshDashboard(); });
$('navPlan').addEventListener('click', () => { setView('overviewView', 'Study planner'); $('navPlan').classList.add('active'); $('studyPlannerPanel').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
$('navHistory').addEventListener('click', showHistory);
$('brandHome').addEventListener('click', (event) => { event.preventDefault(); setView('overviewView', 'Your overview'); refreshDashboard(); });
$('updatePlan').addEventListener('click', updatePlan);
$('editPath').addEventListener('click', openPathModal);
$('profileMenu').addEventListener('click', () => { $('userPopover').classList.add('hidden'); openPathModal(); });
$('logoutButton').addEventListener('click', logout);
$('userMenu').addEventListener('click', (event) => { event.stopPropagation(); $('userPopover').classList.toggle('hidden'); });
document.addEventListener('click', (event) => { if (!$('userPopover').contains(event.target) && event.target !== $('userMenu')) $('userPopover').classList.add('hidden'); });
$('mobileMenu').addEventListener('click', () => $('sidebar').classList.toggle('open'));

async function init() {
  populateSubjectSelect($('registerGrade'), $('registerSubject'), 'Science');
  try {
    const data = await api('/api/me');
    if (data.authenticated) await enterApp(data.user);
    else showAuth();
  } catch (error) { showAuth(); setAuthMessage('The app could not connect to the local server. Restart Flask and refresh this page.'); }
}
init();
