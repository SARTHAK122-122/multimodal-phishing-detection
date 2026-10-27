/**
 * PhishGuard content script.
 *
 * Shows a full-screen interstitial when the backend classifies the page as
 * PHISHING (HIGH/CRITICAL). It is an *overlay*, not a hard block: the user can
 * go back or consciously continue, and the decision is recorded by the service
 * worker so it does not nag on every navigation.
 *
 * The script never reads form values, passwords or page content - it only
 * paints an overlay driven by the verdict pushed from background.js.
 */

const OVERLAY_ID = 'phishguard-overlay';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function showWarning(verdict) {
  removeWarning();

  const overlay = el('div', '', '');
  overlay.id = OVERLAY_ID;
  overlay.setAttribute('role', 'alertdialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Phishing warning');

  const card = el('div', 'pg-card');

  const icon = el('div', 'pg-icon', '!');
  card.appendChild(icon);

  const title = el('h1', 'pg-title', 'This site looks like a phishing page');
  card.appendChild(title);

  const host = el('p', 'pg-host', verdict.host || '');
  card.appendChild(host);

  const reason = el(
    'p',
    'pg-reason',
    verdict.explanation ||
      'The multimodal analysis engine classified this page as phishing.'
  );
  card.appendChild(reason);

  if (verdict.riskLevel) {
    const badge = el(
      'span',
      `pg-badge pg-${String(verdict.classification || '').toLowerCase()} `,
      `${verdict.classification} · risk ${verdict.riskLevel}` +
        (verdict.riskScore != null
          ? ` · score ${Number(verdict.riskScore).toFixed(2)}`
          : '')
    );
    card.appendChild(badge);
  }

  if (verdict.evidence?.length) {
    const list = el('ul', 'pg-evidence');
    for (const item of verdict.evidence) {
      const li = el('li', `pg-sev-${String(item.severity || 'info').toLowerCase()}`);
      li.appendChild(el('span', 'pg-sev', item.severity));
      li.appendChild(document.createTextNode(' ' + item.description));
      list.appendChild(li);
    }
    card.appendChild(list);
  }

  if (verdict.missing?.length) {
    card.appendChild(
      el(
        'p',
        'pg-caveat',
        `Incomplete scan: ${verdict.missing.join(', ')} module(s) unavailable. ` +
          'A partial scan is not the same as a clean scan.'
      )
    );
  }

  const actions = el('div', 'pg-actions');

  const back = el('button', 'pg-btn pg-primary', 'Go back');
  back.addEventListener('click', () => {
    removeWarning();
    if (history.length > 1) history.back();
    else location.href = 'about:blank';
  });

  const continueBtn = el('button', 'pg-btn pg-ghost', 'Continue anyway');
  continueBtn.addEventListener('click', () => {
    removeWarning();
    // The service worker resolves this tab from the message sender and records
    // the dismissal for the rest of the browser session.
    chrome.runtime.sendMessage({ type: 'dismissWarning', host: verdict.host });
  });

  const report = el('button', 'pg-btn pg-ghost', 'View full report');
  report.addEventListener('click', () => {
    if (verdict.id) {
      chrome.runtime.sendMessage({ type: 'openReport', id: verdict.id });
    }
  });

  actions.appendChild(back);
  actions.appendChild(continueBtn);
  if (verdict.id) actions.appendChild(report);
  card.appendChild(actions);

  overlay.appendChild(card);
  (document.body || document.documentElement).appendChild(overlay);

  // Focus the safe action first.
  back.focus();
}

function removeWarning() {
  const existing = document.getElementById(OVERLAY_ID);
  if (existing) existing.remove();
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === 'PHISH_WARNING' && message.verdict) {
    showWarning(message.verdict);
  } else if (message?.type === 'REMOVE_WARNING') {
    removeWarning();
  }
});
