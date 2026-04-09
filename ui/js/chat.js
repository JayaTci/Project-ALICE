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
    const el = document.createElement('div');
    el.className = `msg msg-${role}`;
    if (text) el.textContent = text;
    log.appendChild(el);
    scrollToBottom();
    return el;
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
