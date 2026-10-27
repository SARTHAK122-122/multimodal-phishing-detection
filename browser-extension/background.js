/**
 * PhishGuard service worker (Manifest V3).
 *
 * Responsibilities
 *  - On every completed http(s) navigation, POST the URL to the platform's
 *    Spring Boot API (POST /api/scans/website) and paint an honest badge.
 *  - Cache verdicts per hostname (session storage, 10 min TTL) so ordinary
 *    browsing does not rescan the same site on every navigation.
 *  - Push a PHISHING verdict to the content script so it can show the
 *    interstitial warning overlay.
 *
 * The extension never grades a URL locally: all verdicts come from the
 * backend/Python fusion engine. If the backend is unreachable the badge shows
 * "err" - it never invents a result.
 *
 * host_permissions for the backend exempt these fetches from CORS; visiting
 * sites are only ever *sent to the backend*, never read by this worker.
 */

const DEFAULTS = {
  backend: 'http://localhost:8088',
  enabled: true,
  mode: 'fast', // 'fast' = fetch HTML only (default), 'thorough' = also render + screenshot
};
const TTL_MS = 10 * 60 * 1000;

/** In-flight scans keyed by URL, so double events never double-scan. */
const inflight = new Map();

/* ------------------------------- settings ------------------------------- */

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

/* ------------------------------ verdict cache --------------------------- */

function hostKey(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

async function loadVerdicts() {
  const { verdicts } = await chrome.storage.session.get({ verdicts: {} });
  return verdicts || {};
}

async function saveVerdict(host, verdict) {
  const verdicts = await loadVerdicts();
  const now = Date.now();
  for (const [key, value] of Object.entries(verdicts)) {
    if (!value || now - value.at > TTL_MS) delete verdicts[key];
  }
  verdicts[host] = verdict;
  await chrome.storage.session.set({ verdicts });
}

/* -------------------------------- scanning ------------------------------ */

async function scanUrl(url, { force = false } = {}) {
  const host = hostKey(url);
  if (!host) throw new Error('Not a web URL.');

  if (!force) {
    const cached = (await loadVerdicts())[host];
    if (cached && Date.now() - cached.at < TTL_MS) return cached;
  }

  const pending = inflight.get(url);
  if (pending) return pending;

  const promise = doScan(url, host)
    .catch(async (err) => {
      // A backend failure is surfaced as a distinct "error" verdict - never
      // silently treated as safe.
      return {
        url,
        host,
        id: null,
        classification: 'UNKNOWN',
        riskLevel: 'UNKNOWN',
        riskScore: null,
        status: 'FAILED',
        explanation: `Backend unreachable: ${err.message}`,
        evidence: [],
        missing: [],
        error: err.message,
        at: Date.now(),
      };
    })
    .finally(() => inflight.delete(url));

  inflight.set(url, promise);
  return promise;
}

async function doScan(url, host) {
  const { backend, mode } = await getSettings();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), mode === 'thorough' ? 150000 : 60000);

  try {
    const res = await fetch(`${backend}/api/scans/website`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, fetch: true, render: mode === 'thorough' }),
      signal: controller.signal,
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        detail = err.message || err.error || detail;
      } catch {
        /* keep the status line */
      }
      throw new Error(detail);
    }

    const data = await res.json();
    const verdict = {
      url,
      host,
      id: data.id ?? null,
      classification: data.classification,
      riskLevel: data.riskLevel,
      riskScore: data.riskScore,
      status: data.status,
      explanation: data.explanation,
      // Risk-raising evidence first; safety items are kept in the full report.
      evidence: (data.evidence || [])
        .slice()
        .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
        .slice(0, 4)
        .map((e) => ({
          severity: e.severity,
          modality: e.modality,
          description: e.description,
        })),
      missing: data.missingModalities || [],
      at: Date.now(),
    };
    await saveVerdict(host, verdict);
    return verdict;
  } finally {
    clearTimeout(timer);
  }
}

function severityRank(s) {
  return { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 }[s] || 0;
}

/* --------------------------------- badges ------------------------------- */

function paintBadge(tabId, verdict) {
  let text = '';
  let color = '#64748b';
  if (!verdict) {
    text = '';
  } else if (verdict.error || verdict.classification === 'UNKNOWN') {
    text = 'err';
    color = '#64748b';
  } else if (verdict.classification === 'PHISHING') {
    text = '!';
    color = '#dc2626';
  } else if (verdict.classification === 'SUSPICIOUS') {
    text = '?';
    color = '#f59e0b';
  } else if (verdict.classification === 'LEGITIMATE') {
    text = '✓';
    color = '#22c55e';
  }
  chrome.action.setBadgeBackgroundColor({ tabId, color });
  chrome.action.setBadgeText({ tabId, text });
}

function paintScanning(tabId) {
  chrome.action.setBadgeBackgroundColor({ tabId, color: '#3b82f6' });
  chrome.action.setBadgeText({ tabId, text: '...' });
}

/* ----------------------------- navigation hook -------------------------- */

async function handleNavigation(tab) {
  if (!tab.id || !tab.url || !/^https?:/.test(tab.url)) return;
  const { enabled } = await getSettings();
  if (!enabled) {
    paintBadge(tab.id, null);
    return;
  }

  paintScanning(tab.id);
  const verdict = await scanUrl(tab.url);
  paintBadge(tab.id, verdict);

  const dismissKey = `dismissed:${verdict.host}`;
  const { [dismissKey]: dismissed } = await chrome.storage.session.get(dismissKey);

  if (
    verdict.classification === 'PHISHING' &&
    (verdict.riskLevel === 'CRITICAL' || verdict.riskLevel === 'HIGH') &&
    !dismissed
  ) {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'PHISH_WARNING', verdict });
    } catch {
      /* content script not ready (e.g. chrome:// pages) - badge still shows */
    }
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') void handleNavigation(tab);
});

// Repaint (and scan) when the user switches tabs so every tab shows a verdict.
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab && tab.status === 'complete') await handleNavigation(tab);
  } catch {
    /* tab may be gone */
  }
});

/* ------------------------------ popup messages -------------------------- */

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'getVerdict') {
    (async () => {
      const host = hostKey(message.url);
      const cached = host ? (await loadVerdicts())[host] : null;
      sendResponse({ verdict: cached || null });
    })();
    return true; // async response
  }

  if (message?.type === 'scan') {
    (async () => {
      const verdict = await scanUrl(message.url, { force: Boolean(message.force) });
      const tabId = message.tabId;
      if (tabId) paintBadge(tabId, verdict);
      sendResponse({ verdict });
    })();
    return true;
  }

  if (message?.type === 'openReport') {
    const backend = message.backend || DEFAULTS.backend;
    chrome.tabs.create({ url: `${backend}/scans/${message.id}` });
    sendResponse({ ok: true });
    return false;
  }

  if (message?.type === 'openDashboard') {
    const backend = message.backend || DEFAULTS.backend;
    chrome.tabs.create({ url: message.path ? `${backend}${message.path}` : backend });
    sendResponse({ ok: true });
    return false;
  }

  if (message?.type === 'dismissWarning') {
    // Remembered for this browser session so the overlay does not reappear on
    // every navigation of a site the user consciously continued past.
    chrome.storage.session.set({ [`dismissed:${message.host}`]: Date.now() });
    const tabId = sender.tab?.id ?? message.tabId;
    (async () => {
      if (tabId) {
        try {
          await chrome.tabs.sendMessage(tabId, { type: 'REMOVE_WARNING' });
        } catch {
          /* already gone */
        }
      }
      sendResponse({ ok: true });
    })();
    return true;
  }

  return false;
});
