/**
 * voice-viz.js — Canvas orb visualization
 *
 * States:
 *   connecting  → dim grey, slow pulse
 *   idle        → purple orb, breathing glow
 *   listening   → green expanding rings
 *   thinking    → purple spinning arc
 *   speaking    → amber ripple waves
 *   error       → red flash → back to idle
 */

const VoiceOrb = (() => {
  const canvas = document.getElementById('orb-canvas');
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const CX = W / 2;
  const CY = H / 2;
  const BASE_R = 48;

  let state = 'connecting';
  let startTime = Date.now();
  let ripples = [];   // for listening/speaking rings
  let arcAngle = 0;   // for thinking spin
  let errorTimer = 0; // flash countdown

  // ── Color palettes per state ──────────────────────────────────────────
  const COLORS = {
    connecting: { core: '#334155', glow: 'rgba(51,65,85,0.25)',  ring: '#475569' },
    idle:       { core: '#7c3aed', glow: 'rgba(124,58,237,0.30)', ring: '#a855f7' },
    listening:  { core: '#10b981', glow: 'rgba(16,185,129,0.30)', ring: '#34d399' },
    thinking:   { core: '#a855f7', glow: 'rgba(168,85,247,0.35)', ring: '#c084fc' },
    speaking:   { core: '#f59e0b', glow: 'rgba(245,158,11,0.30)', ring: '#fbbf24' },
    error:      { core: '#ef4444', glow: 'rgba(239,68,68,0.35)',  ring: '#f87171' },
  };

  // ── Ripple factory ────────────────────────────────────────────────────
  function spawnRipple(color) {
    ripples.push({ r: BASE_R, maxR: BASE_R + 60, alpha: 0.7, color });
  }

  // ── Main draw ─────────────────────────────────────────────────────────
  function draw() {
    const now = Date.now();
    const t = (now - startTime) / 1000;

    ctx.clearRect(0, 0, W, H);

    const col = COLORS[state] || COLORS.idle;

    switch (state) {
      case 'connecting': drawIdle(t, col, 0.4); break;
      case 'idle':       drawIdle(t, col, 1.0); break;
      case 'listening':  drawListening(t, col); break;
      case 'thinking':   drawThinking(t, col); break;
      case 'speaking':   drawSpeaking(t, col); break;
      case 'error':      drawError(now, col); break;
    }

    requestAnimationFrame(draw);
  }

  // ── Idle: breathing glow + static orb ────────────────────────────────
  function drawIdle(t, col, opacity) {
    const breath = 0.95 + 0.05 * Math.sin(t * 1.2);         // 0.95–1.00 scale
    const glowR = BASE_R * breath * 1.6;
    const glowAlpha = (0.18 + 0.10 * Math.sin(t * 1.2)) * opacity;

    // Outer glow
    const grad = ctx.createRadialGradient(CX, CY, BASE_R * 0.5, CX, CY, glowR);
    grad.addColorStop(0, col.glow.replace('0.30', String(glowAlpha * 2)));
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(CX, CY, glowR, 0, Math.PI * 2);
    ctx.fill();

    // Core orb
    const r = BASE_R * breath;
    const coreGrad = ctx.createRadialGradient(CX - 10, CY - 10, 4, CX, CY, r);
    coreGrad.addColorStop(0, lighten(col.core, 0.4));
    coreGrad.addColorStop(0.5, col.core);
    coreGrad.addColorStop(1, darken(col.core, 0.4));

    ctx.globalAlpha = opacity;
    ctx.beginPath();
    ctx.arc(CX, CY, r, 0, Math.PI * 2);
    ctx.fillStyle = coreGrad;
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  // ── Listening: green rings expanding ─────────────────────────────────
  function drawListening(t, col) {
    // Small pulsing core
    drawIdle(t * 2, col, 0.85);

    // Spawn new ring every 0.8s
    if (ripples.length === 0 || ripples[ripples.length - 1].r > BASE_R + 25) {
      spawnRipple(col.ring);
    }

    // Draw and advance ripples
    ripples = ripples.filter(rp => {
      rp.r += 1.0;
      rp.alpha -= 0.012;
      if (rp.alpha <= 0) return false;

      ctx.beginPath();
      ctx.arc(CX, CY, rp.r, 0, Math.PI * 2);
      ctx.strokeStyle = rp.color;
      ctx.globalAlpha = rp.alpha;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.globalAlpha = 1;
      return true;
    });
  }

  // ── Thinking: spinning arc ────────────────────────────────────────────
  function drawThinking(t, col) {
    arcAngle += 0.06;
    const arc = Math.PI * 1.3;

    // Dim core
    drawIdle(t * 0.5, col, 0.6);

    // Spinning arc (thick stroke)
    ctx.beginPath();
    ctx.arc(CX, CY, BASE_R + 16, arcAngle, arcAngle + arc);
    ctx.strokeStyle = col.ring;
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.globalAlpha = 0.9;
    ctx.stroke();

    // Counter arc (thin, opposite)
    ctx.beginPath();
    ctx.arc(CX, CY, BASE_R + 24, arcAngle + Math.PI, arcAngle + Math.PI + arc * 0.5);
    ctx.strokeStyle = col.core;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.45;
    ctx.stroke();

    ctx.globalAlpha = 1;
  }

  // ── Speaking: amber ripple waves ──────────────────────────────────────
  function drawSpeaking(t, col) {
    // Pulsing core (faster breathing)
    const fastT = t * 3.5;
    drawIdle(fastT, col, 1.0);

    // Spawn ripple more frequently
    if (ripples.length === 0 || ripples[ripples.length - 1].r > BASE_R + 15) {
      spawnRipple(col.ring);
    }

    ripples = ripples.filter(rp => {
      rp.r += 1.4;
      rp.alpha -= 0.016;
      if (rp.alpha <= 0) return false;

      ctx.beginPath();
      ctx.arc(CX, CY, rp.r, 0, Math.PI * 2);
      ctx.strokeStyle = rp.color;
      ctx.globalAlpha = rp.alpha * 0.8;
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.globalAlpha = 1;
      return true;
    });
  }

  // ── Error: red flash ──────────────────────────────────────────────────
  function drawError(now, col) {
    const elapsed = now - errorTimer;
    const alpha = Math.max(0, 1 - elapsed / 800);

    if (alpha > 0) {
      ctx.beginPath();
      ctx.arc(CX, CY, BASE_R, 0, Math.PI * 2);
      ctx.fillStyle = col.core;
      ctx.globalAlpha = alpha;
      ctx.fill();
      ctx.globalAlpha = 1;
    } else {
      setState('idle');
    }
  }

  // ── Color helpers ─────────────────────────────────────────────────────
  function lighten(hex, amount) {
    return adjustColor(hex, amount);
  }

  function darken(hex, amount) {
    return adjustColor(hex, -amount);
  }

  function adjustColor(hex, amount) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const clamp = v => Math.max(0, Math.min(255, Math.round(v)));
    return `rgb(${clamp(r + amount * 255)},${clamp(g + amount * 255)},${clamp(b + amount * 255)})`;
  }

  // ── Public API ────────────────────────────────────────────────────────
  function setState(newState) {
    if (newState === state) return;
    state = newState;
    ripples = [];
    if (newState === 'error') errorTimer = Date.now();
  }

  // Start animation loop
  requestAnimationFrame(draw);

  return { setState };
})();
