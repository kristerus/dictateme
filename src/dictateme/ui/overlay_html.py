"""HTML/CSS/JS template for the premium webview overlay.

This generates the HTML content for the overlay window.
The overlay uses a webview for full CSS animation, blur,
and modern typography support.
"""

from __future__ import annotations

OVERLAY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: rgba(14, 14, 18, 0.92);
    --surface: rgba(28, 28, 35, 0.8);
    --border: rgba(255, 255, 255, 0.06);
    --border-active: rgba(255, 186, 8, 0.2);
    --text: #F2F0ED;
    --text-secondary: #9A9AA6;
    --text-muted: #5A5A68;
    --accent: #FFBA08;
    --accent-glow: rgba(255, 186, 8, 0.12);
    --red: #FF5F57;
    --red-glow: rgba(255, 95, 87, 0.15);
    --green: #2DD4BF;
    --green-glow: rgba(45, 212, 191, 0.12);
    --orange: #FF9F43;
    --radius: 16px;
  }

  html, body {
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: transparent;
    font-family: 'Outfit', 'Segoe UI Variable', system-ui, sans-serif;
    user-select: none;
    -webkit-user-select: none;
  }

  body {
    padding: 8px;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }

  /* ── Main container ───────────────────────────── */
  .overlay {
    width: 100%;
    max-width: 420px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    backdrop-filter: blur(40px) saturate(1.6);
    -webkit-backdrop-filter: blur(40px) saturate(1.6);
    box-shadow:
      0 24px 80px rgba(0,0,0,0.45),
      0 0 0 1px rgba(255,255,255,0.02) inset,
      0 1px 0 rgba(255,255,255,0.04) inset;
    opacity: 0;
    transform: translateY(8px) scale(0.98);
    transition: opacity 0.35s cubic-bezier(0.16, 1, 0.3, 1),
                transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    overflow: hidden;
  }
  .overlay.visible {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  .overlay.hiding {
    opacity: 0;
    transform: translateY(-4px) scale(0.98);
    transition-duration: 0.2s;
  }

  /* ── Header bar ───────────────────────────────── */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px 12px;
    border-bottom: 1px solid var(--border);
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
    transition: background 0.3s, box-shadow 0.3s;
  }
  .status-dot.recording {
    background: var(--red);
    box-shadow: 0 0 8px var(--red-glow), 0 0 2px var(--red);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }
  .status-dot.processing {
    background: var(--orange);
    box-shadow: 0 0 8px rgba(255, 159, 67, 0.2);
    animation: pulse-dot 1s ease-in-out infinite;
  }
  .status-dot.ready {
    background: var(--green);
    box-shadow: 0 0 8px var(--green-glow);
  }
  @keyframes pulse-dot {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.3); opacity: 0.7; }
  }
  .status-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: -0.01em;
    transition: color 0.3s;
  }
  .status-text.recording { color: var(--red); }
  .status-text.processing { color: var(--orange); }
  .status-text.ready { color: var(--green); }

  .header-right {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
  }
  .timer { font-variant-numeric: tabular-nums; }

  /* ── Waveform ─────────────────────────────────── */
  .waveform {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    height: 48px;
    padding: 10px 18px;
    overflow: hidden;
    opacity: 0;
    transition: opacity 0.3s;
  }
  .waveform.active { opacity: 1; }
  .waveform .bar {
    width: 3px;
    border-radius: 2px;
    background: var(--accent);
    height: 4px;
    transition: height 0.08s ease-out;
    opacity: 0.65;
  }

  /* ── Text area ────────────────────────────────── */
  .text-area {
    padding: 16px 18px;
    min-height: 40px;
    max-height: 200px;
    overflow-y: auto;
  }
  .text-area::-webkit-scrollbar { width: 4px; }
  .text-area::-webkit-scrollbar-track { background: transparent; }
  .text-area::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  .text-content {
    font-size: 14px;
    line-height: 1.65;
    color: var(--text);
    font-weight: 400;
    letter-spacing: -0.005em;
    opacity: 0;
    transform: translateY(6px);
    transition: opacity 0.4s, transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .text-content.visible {
    opacity: 1;
    transform: translateY(0);
  }
  .text-placeholder {
    color: var(--text-muted);
    font-style: italic;
    font-weight: 300;
  }
  .text-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: var(--accent);
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: blink 1s step-end infinite;
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  /* ── Format bar ───────────────────────────────── */
  .format-bar {
    display: flex;
    gap: 5px;
    padding: 10px 18px 14px;
    flex-wrap: wrap;
    border-top: 1px solid var(--border);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.3s 0.1s, transform 0.3s 0.1s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .format-bar.visible {
    opacity: 1;
    transform: translateY(0);
  }
  .format-pill {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.02);
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: default;
    transition: border-color 0.15s, background 0.15s, color 0.15s;
  }
  .format-pill .key {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    color: var(--accent);
    min-width: 12px;
    text-align: center;
  }
  .format-pill.active,
  .format-pill:hover {
    border-color: var(--border-active);
    background: var(--accent-glow);
    color: var(--text);
  }

  /* ── Progress bar (auto-insert timer) ─────────── */
  .progress-track {
    height: 2px;
    background: rgba(255, 255, 255, 0.03);
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--accent), var(--green));
    transition: width linear;
    border-radius: 0 1px 1px 0;
  }

  /* ── Hidden state ─────────────────────────────── */
  .hidden { display: none !important; }
</style>
</head>
<body>

<div class="overlay" id="overlay">
  <div class="header">
    <div class="header-left">
      <div class="status-dot" id="statusDot"></div>
      <span class="status-text" id="statusText">Ready</span>
    </div>
    <div class="header-right">
      <span class="timer" id="timer"></span>
    </div>
  </div>

  <div class="waveform" id="waveform"></div>

  <div class="text-area">
    <div class="text-content" id="textContent">
      <span class="text-placeholder">Speak now...</span>
    </div>
  </div>

  <div class="progress-track" id="progressTrack">
    <div class="progress-fill" id="progressFill"></div>
  </div>

  <div class="format-bar" id="formatBar">
    <div class="format-pill active" data-index="0"><span class="key">1</span>As-is</div>
    <div class="format-pill" data-index="1"><span class="key">2</span>Formal</div>
    <div class="format-pill" data-index="2"><span class="key">3</span>Casual</div>
    <div class="format-pill" data-index="3"><span class="key">4</span>Email</div>
    <div class="format-pill" data-index="4"><span class="key">5</span>Bullets</div>
    <div class="format-pill" data-index="5"><span class="key">6</span>Code</div>
    <div class="format-pill" data-index="6"><span class="key">7</span>AI</div>
    <div class="format-pill" data-index="7"><span class="key">8</span>Slack</div>
  </div>
</div>

<script>
const overlay = document.getElementById('overlay');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const timer = document.getElementById('timer');
const waveform = document.getElementById('waveform');
const textContent = document.getElementById('textContent');
const formatBar = document.getElementById('formatBar');
const progressFill = document.getElementById('progressFill');
const progressTrack = document.getElementById('progressTrack');

// ── Initialize waveform bars ───────────────────────
const BAR_COUNT = 50;
const bars = [];
for (let i = 0; i < BAR_COUNT; i++) {
  const bar = document.createElement('div');
  bar.className = 'bar';
  waveform.appendChild(bar);
  bars.push(bar);
}

// ── Waveform animation ─────────────────────────────
let waveformAnimId = null;
let waveformActive = false;

function animateWaveform() {
  if (!waveformActive) return;
  const t = performance.now() / 1000;
  for (let i = 0; i < BAR_COUNT; i++) {
    const center = Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2);
    const wave1 = Math.sin(t * 3 + i * 0.25) * 0.5 + 0.5;
    const wave2 = Math.sin(t * 5.3 + i * 0.18) * 0.3 + 0.5;
    const wave3 = Math.sin(t * 1.7 + i * 0.4) * 0.2 + 0.5;
    const amplitude = (1 - center * 0.6) * (wave1 * 0.5 + wave2 * 0.3 + wave3 * 0.2);
    const h = 3 + amplitude * 32;
    bars[i].style.height = h + 'px';
    bars[i].style.opacity = 0.35 + amplitude * 0.5;
  }
  waveformAnimId = requestAnimationFrame(animateWaveform);
}

function startWaveform() {
  waveformActive = true;
  waveform.classList.add('active');
  animateWaveform();
}

function stopWaveform() {
  waveformActive = false;
  waveform.classList.remove('active');
  if (waveformAnimId) cancelAnimationFrame(waveformAnimId);
  bars.forEach(b => { b.style.height = '4px'; b.style.opacity = '0.3'; });
}

// ── Timer ──────────────────────────────────────────
let timerStart = 0;
let timerInterval = null;

function startTimer() {
  timerStart = Date.now();
  timerInterval = setInterval(() => {
    const elapsed = (Date.now() - timerStart) / 1000;
    const m = Math.floor(elapsed / 60);
    const s = Math.floor(elapsed % 60);
    timer.textContent = m + ':' + s.toString().padStart(2, '0');
  }, 200);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
}

// ── Auto-insert progress ───────────────────────────
function startProgress(durationMs) {
  progressFill.style.transition = 'none';
  progressFill.style.width = '0%';
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      progressFill.style.transition = 'width ' + durationMs + 'ms linear';
      progressFill.style.width = '100%';
    });
  });
}

function resetProgress() {
  progressFill.style.transition = 'none';
  progressFill.style.width = '0%';
}

// ── State management (called from Python) ──────────
window.overlayAPI = {
  show: function() {
    overlay.classList.remove('hiding');
    overlay.classList.add('visible');
  },

  hide: function() {
    overlay.classList.add('hiding');
    overlay.classList.remove('visible');
    stopWaveform();
    stopTimer();
    resetProgress();
    setTimeout(() => {
      // Python will actually hide the window
      if (window.pywebview) window.pywebview.api.on_hidden();
    }, 250);
  },

  setRecording: function() {
    statusDot.className = 'status-dot recording';
    statusText.className = 'status-text recording';
    statusText.textContent = 'Recording';
    textContent.innerHTML = '<span class="text-placeholder">Speak now...</span>';
    textContent.classList.add('visible');
    formatBar.classList.remove('visible');
    resetProgress();
    startWaveform();
    startTimer();
  },

  setProcessing: function() {
    statusDot.className = 'status-dot processing';
    statusText.className = 'status-text processing';
    statusText.textContent = 'Processing';
    stopWaveform();
    stopTimer();
    textContent.innerHTML = '<span class="text-placeholder">Transcribing...</span>';
  },

  setText: function(text, showFormats, autoInsertMs) {
    statusDot.className = 'status-dot ready';
    statusText.className = 'status-text ready';
    statusText.textContent = 'Ready';
    stopWaveform();
    stopTimer();

    textContent.textContent = text;
    textContent.classList.add('visible');

    if (showFormats) {
      formatBar.classList.add('visible');
    }
    if (autoInsertMs > 0) {
      startProgress(autoInsertMs);
    }
  },

  setFormatActive: function(index) {
    document.querySelectorAll('.format-pill').forEach((pill, i) => {
      pill.classList.toggle('active', i === index);
    });
  }
};
</script>
</body>
</html>
"""
