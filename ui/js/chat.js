/**
 * chat.js — Chat log + input bar
 *
 * Exposes:
 *   Chat.appendUser(text)
 *   Chat.appendAlice()           → returns bubble el, streaming mode
 *   Chat.appendSystem(text)
 *   Chat.streamToken(el, token)
 *   Chat.doneStreaming(el)
 */

const Chat = (() => {
  const log     = document.getElementById('chat-log');
  const input   = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');

  // ── Helpers ─────────────────────────────────────────────────────────
  function scrollToBottom() {
    requestAnimationFrame(() => {
      log.scrollTop = log.scrollHeight;
    });
  }

  function createBubble(role, text = '') {
    const bubble = document.createElement('div');
    bubble.className = `msg msg-${role}`;
    if (text) bubble.textContent = text;

    // System messages: centered, no label/timestamp wrapper
    if (role === 'system') {
      log.appendChild(bubble);
      scrollToBottom();
      return bubble;
    }

    // Alice + user messages: wrap with sender label + timestamp
    const wrap = document.createElement('div');
    wrap.className = `msg-wrap msg-wrap-${role}`;

    const sender = document.createElement('span');
    sender.className = 'msg-sender';
    sender.textContent = role === 'alice' ? 'Alice' : 'You';
    wrap.appendChild(sender);

    const row = document.createElement('div');
    row.className = 'msg-row';
    row.appendChild(bubble);

    const timeEl = document.createElement('span');
    timeEl.className = 'msg-time';
    const d = new Date();
    timeEl.textContent = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    row.appendChild(timeEl);

    wrap.appendChild(row);
    log.appendChild(wrap);
    scrollToBottom();
    return bubble;   // callers receive inner .msg — no other changes needed
  }

  // ── Public API ───────────────────────────────────────────────────────
  function appendUser(text) {
    createBubble('user', text);
  }

  function appendAlice() {
    const el = createBubble('alice');
    el.classList.add('streaming');
    return el;
  }

  function appendSystem(text) {
    createBubble('system', text);
  }

  function streamToken(el, token) {
    el.textContent += token;
    scrollToBottom();
  }

  function doneStreaming(el) {
    el.classList.remove('streaming');
    _parseSubtitle(el);
  }

  /**
   * Split JA response from [EN: ...] subtitle and render inline.
   * Input format:  "日本語テキスト\n\n[EN: English translation]"
   * Output:        Japanese text + styled subtitle block
   */
  function _parseSubtitle(el) {
    const text = el.textContent || '';
    const match = text.match(/^([\s\S]*?)\s*\[EN:\s*([\s\S]+?)\]\s*$/);
    if (!match) return;

    const jaText  = match[1].trim();
    const enText  = match[2].trim();

    el.textContent = '';

    const mainSpan = document.createElement('span');
    mainSpan.textContent = jaText;
    el.appendChild(mainSpan);

    const sub = document.createElement('span');
    sub.className = 'msg-subtitle';
    sub.textContent = enText;
    el.appendChild(sub);
  }

  // ── Send logic ───────────────────────────────────────────────────────
  function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendBtn.disabled = true;
    appendUser(text);

    // Delegate to WebSocket layer
    if (typeof WS !== 'undefined') {
      WS.sendMessage(text);
    } else {
      appendSystem('Not connected.');
      sendBtn.disabled = false;
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  function enableInput() {
    sendBtn.disabled = false;
    input.focus();
  }

  function disableInput() {
    sendBtn.disabled = true;
  }

  return { appendUser, appendAlice, appendSystem, streamToken, doneStreaming, enableInput, disableInput };
})();
