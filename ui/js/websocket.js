/**
 * websocket.js — WebSocket client
 *
 * Connects to ws://localhost:8765/ws
 * Handles messages:
 *   { type: "status",    state, label }
 *   { type: "wake_word" }
 *   { type: "transcript", text }
 *   { type: "token",     text }
 *   { type: "done" }
 *   { type: "double_clap" }
 *   { type: "error",     message }
 *   { type: "pong" }
 *
 * Exposes:
 *   WS.sendMessage(text)
 */

const WS = (() => {
  const WS_URL  = 'ws://localhost:8765/ws';
  const RECONNECT_DELAY_MS = 3000;

  const statusDot   = document.getElementById('status-dot');
  const statusLabel = document.getElementById('status-label');
  const orbLabel    = document.getElementById('orb-label');
  const langToggle  = document.getElementById('lang-toggle');

  // ── Language toggle button ────────────────────────────────────────────
  langToggle.addEventListener('click', () => {
    const current = langToggle.getAttribute('data-lang') || 'en';
    const next = current === 'en' ? 'ja' : 'en';
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'set_language', lang: next }));
    }
  });

  function _applyLanguage(lang) {
    langToggle.textContent = lang === 'ja' ? 'JA' : 'EN';
    langToggle.setAttribute('data-lang', lang);
    langToggle.title = lang === 'ja' ? 'Switch to English' : 'Switch to Japanese';
  }

  let socket = null;
  let currentAliceBubble = null;   // active streaming bubble
  let reconnectTimer = null;

  // ── Status helpers ────────────────────────────────────────────────────
  const STATE_LABELS = {
    connecting: 'Connecting…',
    idle:       'Ready',
    listening:  'Listening…',
    thinking:   'Thinking…',
    speaking:   'Speaking…',
    error:      'Error',
  };

  function setStatus(state, label = '') {
    statusDot.setAttribute('data-state', state);
    statusLabel.textContent = label || STATE_LABELS[state] || state;
    orbLabel.textContent    = label || STATE_LABELS[state] || '';
    VoiceOrb.setState(state);
  }

  // ── Connection management ─────────────────────────────────────────────
  function connect() {
    clearTimeout(reconnectTimer);
    setStatus('connecting');

    socket = new WebSocket(WS_URL);

    socket.addEventListener('open', () => {
      setStatus('idle');
      Chat.appendSystem('Alice online.');
      Chat.enableInput();
    });

    socket.addEventListener('message', e => {
      let msg;
      try { msg = JSON.parse(e.data); } catch (_) { return; }
      handleMessage(msg);
    });

    socket.addEventListener('close', () => {
      setStatus('connecting', 'Reconnecting…');
      Chat.disableInput();
      reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
    });

    socket.addEventListener('error', () => {
      // Will trigger 'close' after
    });
  }

  // ── Message handler ───────────────────────────────────────────────────
  function handleMessage(msg) {
    switch (msg.type) {

      case 'status':
        setStatus(msg.state, msg.label || '');
        if (msg.state === 'idle') {
          Chat.enableInput();
        } else {
          Chat.disableInput();
        }
        break;

      case 'wake_word':
        setStatus('listening');
        Chat.appendSystem('Listening…');
        Chat.disableInput();
        break;

      case 'double_clap':
        Chat.appendSystem('Double clap!');
        break;

      case 'transcript':
        // Voice input received — show as user message
        Chat.appendUser(msg.text);
        currentAliceBubble = Chat.appendAlice();
        break;

      case 'token':
        // Streaming response token
        if (!currentAliceBubble) {
          currentAliceBubble = Chat.appendAlice();
        }
        Chat.streamToken(currentAliceBubble, msg.text);
        break;

      case 'done':
        if (currentAliceBubble) {
          Chat.doneStreaming(currentAliceBubble);
          currentAliceBubble = null;
        }
        break;

      case 'error':
        setStatus('error', 'Error');
        Chat.appendSystem(`Error: ${msg.message}`);
        // Auto-recover to idle after 2s
        setTimeout(() => setStatus('idle'), 2000);
        Chat.enableInput();
        break;

      case 'language_changed':
        _applyLanguage(msg.lang);
        Chat.appendSystem(msg.lang === 'ja' ? '言語: 日本語' : 'Language: English');
        break;

      case 'pong':
        // heartbeat ack — no action
        break;
    }
  }

  // ── Send message ──────────────────────────────────────────────────────
  function sendMessage(text) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      Chat.appendSystem('Not connected.');
      Chat.enableInput();
      return;
    }
    currentAliceBubble = Chat.appendAlice();
    socket.send(JSON.stringify({ type: 'message', text }));
  }

  // ── Heartbeat (keep connection alive) ─────────────────────────────────
  setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'ping' }));
    }
  }, 30_000);

  // ── Boot ──────────────────────────────────────────────────────────────
  Chat.disableInput();
  connect();

  return { sendMessage };
})();
