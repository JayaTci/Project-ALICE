/**
 * settings.js — Settings panel
 *
 * Reads current config via GET /api/config,
 * renders read-only info rows + toggles.
 */

const Settings = (() => {
  const panel   = document.getElementById('settings-panel');
  const overlay = document.getElementById('settings-overlay');
  const openBtn = document.getElementById('settings-btn');
  const closeBtn = document.getElementById('settings-close');
  const body    = document.getElementById('settings-body');

  // ── Toggle panel ─────────────────────────────────────────────────────
  function open() {
    panel.classList.add('open');
    overlay.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    render();
  }

  function close() {
    panel.classList.remove('open');
    overlay.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
  }

  openBtn.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  // ── Render settings ───────────────────────────────────────────────────
  async function render() {
    body.innerHTML = '';

    let config = {};
    try {
      const res = await fetch('/api/config');
      if (res.ok) config = await res.json();
    } catch (_) { /* server not ready or no endpoint */ }

    body.appendChild(section('System', [
      row('Model', config.llm_provider === 'groq'
          ? `Groq / ${config.groq_model || 'llama-3.3-70b-versatile'}`
          : config.llm_provider || '—'),
      row('Wake word', config.wake_word_model || '—'),
      row('STT model', config.stt_model_size || '—'),
      row('City', config.weather_city || '—'),
    ]));

    body.appendChild(section('Voice', [
      toggleRow('Speaker verify', config.speaker_verify_enabled),
    ]));

    body.appendChild(section('About', [
      row('Alice version', 'Phase 6'),
      row('Stack', 'Python 3.14 + aiohttp'),
    ]));
  }

  // ── DOM helpers ───────────────────────────────────────────────────────
  function section(title, rows) {
    const sec = document.createElement('div');
    sec.className = 'settings-section';

    const heading = document.createElement('div');
    heading.className = 'settings-section-title';
    heading.textContent = title;
    sec.appendChild(heading);

    rows.forEach(r => sec.appendChild(r));
    return sec;
  }

  function row(label, value) {
    const el = document.createElement('div');
    el.className = 'settings-row';
    el.innerHTML = `
      <span class="settings-label">${label}</span>
      <span class="settings-value">${value}</span>
    `;
    return el;
  }

  function toggleRow(label, checked = false) {
    const el = document.createElement('div');
    el.className = 'settings-row';
    el.innerHTML = `
      <span class="settings-label">${label}</span>
      <label class="toggle">
        <input type="checkbox" ${checked ? 'checked' : ''} disabled />
        <span class="toggle-track"></span>
      </label>
    `;
    return el;
  }

  return { open, close };
})();
