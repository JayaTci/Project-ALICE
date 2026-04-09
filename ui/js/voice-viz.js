/**
 * voice-viz.js — 3D wireframe constellation sphere
 *
 * 96 nodes distributed via Fibonacci spiral on a unit sphere.
 * Edges pre-computed at init (dot product threshold).
 * Y-axis rotation per frame with perspective projection.
 * Depth-based opacity/size for 3D feel.
 *
 * Public API: VoiceOrb.setState(state)
 * States: connecting | idle | listening | thinking | speaking | error
 */

const VoiceOrb = (() => {
  const canvas = document.getElementById('orb-canvas');
  const ctx = canvas.getContext('2d');
  const panel = canvas.parentElement;

  // ── Canvas sizing (dynamic — fills sphere panel) ──────────────────────
  function resizeCanvas() {
    const size = Math.min(panel.clientWidth * 0.80, panel.clientHeight * 0.68);
    canvas.width  = size;
    canvas.height = size;
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  // ── State config ──────────────────────────────────────────────────────
  const STATE_CONFIG = {
    connecting: { color: '#475569', speed: 0.002, glow: 0.25 },
    idle:       { color: '#06b6d4', speed: 0.003, glow: 0.50 },
    listening:  { color: '#10b981', speed: 0.007, glow: 0.90 },
    thinking:   { color: '#a855f7', speed: 0.015, glow: 0.80 },
    speaking:   { color: '#f59e0b', speed: 0.010, glow: 1.00 },
    error:      { color: '#ef4444', speed: 0.020, glow: 1.00 },
  };

  let state = 'connecting';
  let errorFlashStart = 0;

  // ── Fibonacci sphere nodes (96 points on unit sphere) ─────────────────
  const N_NODES = 96;
  const PHI = Math.PI * (3 - Math.sqrt(5));  // golden angle ≈ 2.399 rad
  const nodes = [];

  for (let i = 0; i < N_NODES; i++) {
    const y = 1 - (i / (N_NODES - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    nodes.push({
      x: Math.cos(PHI * i) * r,
      y: y,
      z: Math.sin(PHI * i) * r,
    });
  }

  // ── Pre-compute edges (connect nodes within angular threshold) ─────────
  // threshold = 0.93 → ~21.5° max angle → ~220 edges for 96 nodes
  const CONNECT_THRESHOLD = 0.93;
  const edges = [];

  for (let i = 0; i < N_NODES; i++) {
    for (let j = i + 1; j < N_NODES; j++) {
      const dot = nodes[i].x * nodes[j].x
                + nodes[i].y * nodes[j].y
                + nodes[i].z * nodes[j].z;
      if (dot >= CONNECT_THRESHOLD) {
        edges.push([i, j]);
      }
    }
  }

  // ── Rotation state ────────────────────────────────────────────────────
  let rotY  = 0;
  const ROT_X = 0.18;  // constant X tilt for depth
  const cosRX = Math.cos(ROT_X);
  const sinRX = Math.sin(ROT_X);

  // ── Lerp utility ──────────────────────────────────────────────────────
  function lerp(a, b, t) { return a + (b - a) * t; }

  // ── Project a unit-sphere node to 2D screen coords ────────────────────
  function projectNode(nx, ny, nz, cosY, sinY, sphereR, cx, cy) {
    // 1. Rotate around Y axis
    const rx  =  nx * cosY + nz * sinY;
    const ry  =  ny;
    const rz  = -nx * sinY + nz * cosY;

    // 2. Rotate around X axis (constant tilt)
    const ry2 = ry * cosRX - rz * sinRX;
    const rz2 = ry * sinRX + rz * cosRX;

    // 3. Perspective divide (FOCAL = 2.8)
    const depth = (rz2 + 2.8) / 3.8;   // 0 = back, 1 = front

    return {
      sx: cx + rx * sphereR * depth,
      sy: cy + ry2 * sphereR * depth,
      depth,
      rz: rz2,
    };
  }

  // ── Hex color to rgba string ──────────────────────────────────────────
  function hexRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
  }

  // ── Draw radial glow halo ─────────────────────────────────────────────
  function drawGlow(cx, cy, sphereR, color, intensity) {
    const r = sphereR * 1.4;
    const grad = ctx.createRadialGradient(cx, cy, sphereR * 0.15, cx, cy, r);
    grad.addColorStop(0,   hexRgba(color, 0.30 * intensity));
    grad.addColorStop(0.4, hexRgba(color, 0.14 * intensity));
    grad.addColorStop(1,   hexRgba(color, 0));
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  }

  // ── Main draw loop ────────────────────────────────────────────────────
  function draw() {
    const cfg = STATE_CONFIG[state] || STATE_CONFIG.idle;
    rotY += cfg.speed;

    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H / 2;
    const sphereR = W * 0.36;

    ctx.clearRect(0, 0, W, H);

    // 1. Glow halo
    drawGlow(cx, cy, sphereR, cfg.color, cfg.glow);

    // 2. Project all nodes
    const cosY = Math.cos(rotY);
    const sinY = Math.sin(rotY);
    const proj = nodes.map(n => projectNode(n.x, n.y, n.z, cosY, sinY, sphereR, cx, cy));

    // 3. Draw edges (depth-sorted opacity + width)
    ctx.lineCap = 'round';
    for (const [a, b] of edges) {
      const pa = proj[a];
      const pb = proj[b];
      const avgDepth = (pa.depth + pb.depth) * 0.5;
      if (avgDepth < 0.08) continue;   // cull fully-back edges

      ctx.beginPath();
      ctx.moveTo(pa.sx, pa.sy);
      ctx.lineTo(pb.sx, pb.sy);
      ctx.strokeStyle = cfg.color;
      ctx.globalAlpha = lerp(0.03, 0.38, avgDepth) * cfg.glow;
      ctx.lineWidth   = lerp(0.3, 1.1, avgDepth);
      ctx.stroke();
    }

    // 4. Draw nodes back→front
    const sorted = proj
      .map((p, i) => ({ ...p, i }))
      .sort((a, b) => a.rz - b.rz);

    for (const p of sorted) {
      if (p.depth < 0.08) continue;
      const r = lerp(0.7, 3.0, p.depth);
      ctx.beginPath();
      ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2);
      ctx.fillStyle  = cfg.color;
      ctx.globalAlpha = lerp(0.08, 1.0, p.depth);
      ctx.fill();
    }

    // 5. Error flash overlay
    if (state === 'error') {
      const elapsed = Date.now() - errorFlashStart;
      const alpha = Math.max(0, 1 - elapsed / 900);
      if (alpha > 0) {
        ctx.beginPath();
        ctx.arc(cx, cy, sphereR * 0.9, 0, Math.PI * 2);
        ctx.fillStyle   = '#ef4444';
        ctx.globalAlpha = alpha * 0.45;
        ctx.fill();
      } else {
        setState('idle');
      }
    }

    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }

  // ── Public API ────────────────────────────────────────────────────────
  function setState(newState) {
    if (newState === state) return;
    state = newState;
    if (newState === 'error') errorFlashStart = Date.now();
  }

  // Start
  requestAnimationFrame(draw);

  return { setState };
})();
