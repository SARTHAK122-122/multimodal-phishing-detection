/**
 * PhishGuard popup: shows the stored verdict for the active tab (or scans it
 * on open), plus the backend/mode settings.
 *
 * Every value rendered here comes from the platform's stored scan result -
 * there is no local scoring fallback. When the backend is down the popup says
 * so explicitly.
 */

const $ = (id) => document.getElementById(id);

let activeTab = null;
let busy = false;

/* ------------------------------- helpers -------------------------------- */

function badgeClass(value) {
  const v = String(value || '').toUpperCase();
  if (['PHISHING', 'CRITICAL', 'HIGH', 'FAILED'].includes(v)) return 'danger';
  if (['SUSPICIOUS', 'MEDIUM', 'PARTIAL', 'RUNNING'].includes(v)) return 'warn';
  if (['LEGITIMATE', 'LOW', 'OK', 'COMPLETED'].includes(v)) return 'ok';
  return 'neutral';
}

function severityClass(severity) {
  const v = String(severity || '').toLowerCase();
  if (v === 'critical' || v === 'high') return 'sev-high';
  if (v === 'medium') return 'sev-medium';
  if (v === 'low') return 'sev-low';
  return 'sev-info';
}

function render(verdict) {
  $('idle').hidden = true;
  $('error').hidden = true;
  $('result').hidden = false;

  $('classification').textContent = verdict.classification || 'UNKNOWN';
  $('classification').className = `badge ${badgeClass(verdict.classification)}`;

  $('status-chip').textContent = verdict.status || 'UNKNOWN';
  $('status-chip').className = `badge ${badgeClass(verdict.status)}`;

  $('score').textContent =
    verdict.riskScore != null ? `score ${Number(verdict.riskScore).toFixed(3)}` : '';
  $('explanation').textContent = verdict.explanation || '';

  const list = $('evidence');
  list.textContent = '';
  for (const item of verdict.evidence || []) {
    const li = document.createElement('li');
    li.className = severityClass(item.severity);
    const sev = document.createElement('span');
    sev.className = 'sev';
    sev.textContent = item.severity;
    li.appendChild(sev);
    li.appendChild(document.createTextNode(item.description));
    list.appendChild(li);
  }

  const caveat = $('caveat');
  if (verdict.missing?.length) {
    caveat.hidden = false;
    caveat.textContent = `Incomplete scan: ${verdict.missing.join(', ')} unavailable. A partial scan is not a clean scan.`;
  } else {
    caveat.hidden = true;
  }

  $('report').hidden = !verdict.id;
}

function showError(message) {
  $('idle').hidden = true;
  $('result').hidden = true;
  $('error').hidden = false;
  $('error').textContent = message;
  $('status-chip').textContent = 'error';
  $('status-chip').className = 'badge danger';
}

async function requestVerdict({ force = false } = {}) {
  if (!activeTab?.url || busy) return;
  busy = true;
  $('rescan').disabled = true;
  $('idle').hidden = false;
  $('result').hidden = true;
  $('error').hidden = true;

  try {
    const { verdict } = await chrome.runtime.sendMessage({
      type: 'scan',
      url: activeTab.url,
      force,
      tabId: activeTab.id,
    });
    if (verdict?.error) showError(verdict.error);
    else if (verdict) render(verdict);
    else showError('No verdict was returned.');
  } catch (err) {
    showError(`Background worker error: ${err.message}`);
  } finally {
    busy = false;
    $('rescan').disabled = false;
  }
}

/* --------------------------------- init --------------------------------- */

async function init() {
  const settings = await chrome.storage.sync.get({
    backend: 'http://localhost:8088',
    enabled: true,
    mode: 'fast',
  });
  $('backend').value = settings.backend;
  $('mode').value = settings.mode;
  $('enabled').checked = settings.enabled;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTab = tab;

  if (!tab?.url || !/^https?:/.test(tab.url)) {
    $('host').textContent = 'not a web page';
    $('idle').hidden = true;
    $('status-chip').textContent = '-';
    $('status-chip').className = 'badge neutral';
    $('error').hidden = false;
    $('error').textContent =
      'PhishGuard only analyzes http/https pages. Use the dashboard for email, SMS and QR scans.';
    return;
  }

  $('host').textContent = new URL(tab.url).hostname;

  // Fast path: show the cached verdict if one exists, otherwise scan now.
  const { verdict } = await chrome.runtime.sendMessage({ type: 'getVerdict', url: tab.url });
  if (verdict) render(verdict);
  else await requestVerdict();
}

/* ------------------------------- listeners ------------------------------ */

$('rescan').addEventListener('click', () => requestVerdict({ force: true }));

$('deep').addEventListener('click', async () => {
  // One thorough scan (render + screenshot) for this site, then the previous
  // mode is restored so routine navigation scanning stays fast.
  const previousMode = $('mode').value;
  await chrome.storage.sync.set({ mode: 'thorough' });
  $('mode').value = 'thorough';
  try {
    await requestVerdict({ force: true });
  } finally {
    await chrome.storage.sync.set({ mode: previousMode });
    $('mode').value = previousMode;
  }
});

$('report').addEventListener('click', async () => {
  const { verdict } = await chrome.runtime.sendMessage({ type: 'getVerdict', url: activeTab.url });
  if (verdict?.id) {
    chrome.runtime.sendMessage({
      type: 'openReport',
      id: verdict.id,
      backend: $('backend').value.trim(),
    });
  }
});

$('enabled').addEventListener('change', async (e) => {
  await chrome.storage.sync.set({ enabled: e.target.checked });
});

$('backend').addEventListener('change', async (e) => {
  const value = e.target.value.trim().replace(/\/+$/, '');
  await chrome.storage.sync.set({ backend: value });
});

$('mode').addEventListener('change', async (e) => {
  await chrome.storage.sync.set({ mode: e.target.value });
});

void init;
document.addEventListener('DOMContentLoaded', () => void init());
