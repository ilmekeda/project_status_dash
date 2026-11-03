const list = document.querySelector('#projects-section');
const rules = document.querySelector('#sort-rules');
const status = document.querySelector('#sort-status');
const priorityRank = { low: 1, medium: 2, high: 3 };
const labels = { priority: 'priority', weight: 'weight', last_updated: 'last updated', start_date: 'started', end_date: 'ended', active: 'active' };
const dataNames = { last_updated: 'lastUpdated', start_date: 'startDate', end_date: 'endDate' };
const timezoneSelect = document.querySelector('#timezone-select');
const timezoneCurrent = document.querySelector('#timezone-current');
const projectsStatus = document.querySelector('#projects-status');
const summaryGrid = document.querySelector('#summary-grid');
const dataUrl = document.documentElement.dataset.projectsUrl || '../generated/projects.json';

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function completedCount(tasks) { return tasks.filter((task) => task.completed).length; }
function percentage(metric) { return metric.percentage === null ? null : Math.round(metric.percentage); }
function dateOr(value, fallback) { return value || fallback; }

function anvilIcon() {
  const wrapper = document.createElement('span');
  wrapper.innerHTML = '<svg class="anvil-icon" viewBox="0 0 28 24" role="img" aria-label="Anvil"><title>Anvil</title><g><path d="M1.5 6.5 15.5 2.8 21 5.5 10 9.2 1.5 7.6Z"/><path d="M1.5 7.6v1.6L10 11V9.2"/><path d="M10 9.2V11l11-3.7V5.5"/><path d="M20.8 5.5c2.3-1.1 5.3-.9 6.6-.2-1.4 2.1-4.4 4.1-7.2 5.6-1.1-1.7-.8-3.8.6-5.4Z"/><path d="M4 10.2c.8 3.4-.3 6.1-2.5 8l3.7 1.1c2.7-2.1 4.6-4.2 5-8.3"/><path d="M19.4 10.5c-.8 2.7-.1 4.4 1.8 5.8l3-.5v2l-3.3.5c-2.8-1.2-5.6-1.2-8.1 1.7l-3.1.6 3.7 1 2.6-1.2c2.3-1.4 4.2-1.3 6.8-.4"/></g></svg>';
  return wrapper.firstElementChild;
}

function renderSummary(projects) {
  const tasks = projects.reduce((total, project) => total + project.metrics.tasks.total, 0);
  const completedTasks = projects.reduce((total, project) => total + project.metrics.tasks.completed, 0);
  const milestones = projects.reduce((total, project) => total + project.metrics.milestones.total, 0);
  const completedMilestones = projects.reduce((total, project) => total + project.metrics.milestones.completed, 0);
  summaryGrid.replaceChildren(
    element('div', undefined, 'summary'),
    element('div', undefined, 'summary'),
    element('div', undefined, 'summary'),
  );
  const values = [[`${completedTasks} / ${tasks}`, '✅ tasks complete'], [`${completedMilestones} / ${milestones}`, '🏁 milestones complete'], [`${projects.length}`, '🗂️ projects']];
  [...summaryGrid.children].forEach((card, index) => { card.append(element('strong', values[index][0]), element('span', values[index][1])); });
}

function renderProject(project) {
  const taskMetric = project.metrics.tasks;
  const milestones = project.milestones || [];
  const weight = project.weight.milestones_total;
  const card = element('article', undefined, 'project-card');
  card.dataset.name = project.name;
  card.dataset.priority = project.priority;
  card.dataset.weight = weight;
  card.dataset.lastUpdated = project.last_updated;
  card.dataset.startDate = dateOr(project.start_date, '');
  card.dataset.endDate = dateOr(project.end_date, '');
  card.dataset.active = project.status === 'active' ? '1' : '0';

  const heading = element('div', undefined, 'project-heading');
  const headingText = element('div');
  const lifecycle = project.status === 'active' ? '🟢 Active' : project.status === 'planning' ? '📝 Planning' : `⚪ ${project.status}`;
  headingText.append(element('p', `${lifecycle} · 🚩 ${project.priority[0].toUpperCase()}${project.priority.slice(1)} priority`, 'eyebrow'), element('h3', project.name));
  heading.append(headingText, element('span', `${taskMetric.completed} / ${taskMetric.total} tasks`, 'metric'));
  card.append(heading);

  const meta = element('p', undefined, 'project-meta');
  const role = project.role === 'founder' ? '👤 Founder' : '🤝 Contributor';
  const visibility = project.visibility === 'public' ? '🌐 Public' : '🔒 Private';
  meta.textContent = `${role} · ${visibility} · 🕒 Updated: ${project.last_updated} · 🚀 Started: ${dateOr(project.start_date, 'not recorded')} · 🏁 Ended: ${dateOr(project.end_date, 'ongoing')} · ⚖️ Weight: ${weight} milestones`;
  card.append(meta);

  const weightLine = element('div', undefined, 'weight-line');
  const weightLabel = element('span');
  if (project.weight.classification === 'heaviest') weightLabel.append(anvilIcon(), ' Heaviest');
  else if (project.weight.classification === 'lightest') weightLabel.textContent = '🪶 Lightest';
  else weightLabel.textContent = '⚖️ Middle weight';
  weightLine.append(weightLabel, element('span', '●'.repeat(weight), 'weight-dots'));
  weightLine.lastChild.setAttribute('aria-label', `Weight ${weight} milestones`);
  card.append(weightLine);

  const progress = element('div', undefined, 'progress');
  progress.setAttribute('role', 'progressbar');
  progress.setAttribute('aria-label', `${project.name} task completion`);
  progress.setAttribute('aria-valuemin', '0');
  progress.setAttribute('aria-valuemax', '100');
  const taskPercentage = percentage(taskMetric);
  if (taskPercentage === null) progress.setAttribute('aria-valuetext', 'Not applicable');
  else { progress.setAttribute('aria-valuenow', taskPercentage); progress.append(element('span')); progress.firstElementChild.style.width = `${taskPercentage}%`; }
  card.append(progress);

  const milestoneList = element('ul', undefined, 'milestones');
  const outstanding = [];
  milestones.forEach((milestone) => {
    const complete = completedCount(milestone.tasks);
    const item = element('li');
    item.append(element('strong', `${milestone.id}: ${milestone.name}`));
    const detail = element('span', `${complete} / ${milestone.tasks.length} tasks${milestone.completed ? ' · ✅ complete' : ''}`, milestone.completed ? 'complete' : '');
    if (milestone.completed_at) { detail.append(' · '); const time = element('time', milestone.completed_at, 'utc-timestamp'); time.dateTime = milestone.completed_at; detail.append(time); }
    item.append(detail);
    milestoneList.append(item);
    milestone.tasks.filter((task) => !task.completed).forEach((task) => outstanding.push(task.text));
  });
  card.append(milestoneList);

  const details = element('details');
  details.append(element('summary', 'Outstanding tasks'));
  const outstandingList = element('ul');
  if (!outstanding.length) outstandingList.append(element('li', 'No outstanding tasks.'));
  else outstanding.forEach((task) => outstandingList.append(element('li', task)));
  details.append(outstandingList);
  card.append(details);
  return card;
}

function value(card, key) {
  if (key === 'priority') return priorityRank[card.dataset.priority] || 0;
  if (key === 'weight' || key === 'active') return Number(card.dataset[key] || 0);
  return card.dataset[dataNames[key]] || '';
}

function compare(a, b, key, direction) {
  const left = value(a, key); const right = value(b, key);
  const leftMissing = left === ''; const rightMissing = right === '';
  if (leftMissing || rightMissing) return leftMissing === rightMissing ? 0 : (leftMissing ? 1 : -1);
  const result = ['last_updated', 'start_date', 'end_date'].includes(key) ? left.localeCompare(right) : left - right;
  return direction === 'asc' ? result : -result;
}

function currentRules() { return [...rules.querySelectorAll('.sort-rule')].map((row) => ({ key: row.querySelector('.sort-key').value, direction: row.querySelector('.sort-direction').value })); }
function applySort() {
  const selected = currentRules(); const cards = [...list.querySelectorAll('.project-card')];
  cards.sort((a, b) => { for (const rule of selected) { const result = compare(a, b, rule.key, rule.direction); if (result) return result; } return a.dataset.name.localeCompare(b.dataset.name); });
  cards.forEach((card) => list.append(card));
  status.textContent = selected.length ? `Sorted by ${selected.map((rule) => labels[rule.key]).join(', then ')}.` : 'Original source order.';
}

function addSortRule() {
  const row = document.createElement('div'); row.className = 'sort-rule';
  row.innerHTML = `<label>Sort ${rules.children.length + 1} <select class="sort-key"><option value="priority">🚩 Priority</option><option value="weight">⚖️ Weight (milestones)</option><option value="last_updated">🕒 Last updated</option><option value="start_date">🚀 Started</option><option value="end_date">🏁 Ended</option><option value="active">🟢 Active</option></select></label><label>Direction <select class="sort-direction"><option value="desc">Highest / newest first</option><option value="asc">Lowest / oldest first</option></select></label><button class="remove-sort" type="button" aria-label="Remove sort">×</button>`;
  rules.append(row); applySort();
}

function setupTimezones() {
  const detected = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; const zones = new Set(['UTC', detected]);
  if (typeof Intl.supportedValuesOf === 'function') Intl.supportedValuesOf('timeZone').forEach((zone) => zones.add(zone));
  [...zones].sort((a, b) => a === 'UTC' ? -1 : b === 'UTC' ? 1 : a.localeCompare(b)).forEach((zone) => { const option = element('option', zone); option.value = zone; timezoneSelect.append(option); });
  timezoneSelect.value = zones.has(detected) ? detected : 'UTC';
}

function refreshTimestamps() {
  const zone = timezoneSelect.value || 'UTC'; const formatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: zone });
  timezoneCurrent.textContent = zone;
  document.querySelectorAll('.utc-timestamp').forEach((timestamp) => { timestamp.textContent = formatter.format(new Date(timestamp.dateTime)); timestamp.title = `${timestamp.dateTime} UTC`; });
}

async function loadProjects() {
  try {
    const response = await fetch(dataUrl, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data.projects)) throw new Error('JSON does not contain a projects list');
    renderSummary(data.projects);
    data.projects.forEach((project) => list.append(renderProject(project)));
    projectsStatus.textContent = `Showing ${data.projects.length} projects from generated JSON.`;
    setupTimezones(); refreshTimestamps(); applySort();
  } catch (error) {
    projectsStatus.textContent = `Unable to load project data: ${error.message}`;
    projectsStatus.className = 'load-error';
  }
}

rules.addEventListener('change', applySort);
rules.addEventListener('click', (event) => { if (event.target.matches('.remove-sort')) { event.target.closest('.sort-rule').remove(); applySort(); } });
document.querySelector('#add-sort').addEventListener('click', addSortRule);
document.querySelector('#reset-sort').addEventListener('click', () => { rules.innerHTML = ''; addSortRule(); rules.querySelector('.sort-key').value = 'weight'; rules.querySelector('.sort-direction').value = 'desc'; applySort(); });
timezoneSelect.addEventListener('change', refreshTimestamps);
loadProjects();
