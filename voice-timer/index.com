<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="mobile-web-app-capable" content="yes">
<title>Hold Timer</title>
<style>
  :root {
    --bg: #14171a;
    --ink: #f2ede4;
    --muted: #8b9299;
    --accent: #e8a33d;
    --stop: #d1574a;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    height: 100%;
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    overscroll-behavior: none;
  }
  body {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 24px;
    padding-bottom: env(safe-area-inset-bottom, 24px);
  }
  .label {
    color: var(--muted);
    font-size: 0.85rem;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .time {
    font-variant-numeric: tabular-nums;
    font-size: clamp(3rem, 16vw, 5.5rem);
    font-weight: 600;
    line-height: 1;
    margin-bottom: 4px;
  }
  .time .ms { font-size: 0.4em; color: var(--muted); }
  .status {
    color: var(--muted);
    font-size: 0.95rem;
    margin-bottom: 36px;
    min-height: 1.2em;
  }
  .status.running { color: var(--accent); }
  .controls { display: flex; gap: 16px; }
  button {
    border: none;
    border-radius: 999px;
    padding: 18px 30px;
    font-size: 1.05rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.08s ease;
  }
  button:active { transform: scale(0.96); }
  #toggleBtn { background: var(--accent); color: #201802; min-width: 140px; }
  #toggleBtn.running { background: var(--stop); color: #2a0e0a; }
  #resetBtn { background: transparent; color: var(--muted); border: 1px solid #33383d; }
  #resetBtn:disabled { opacity: 0.3; }

  .settings {
    margin-top: 32px;
    width: 100%;
    max-width: 320px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .settings-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .settings-row span { font-size: 0.85rem; color: var(--muted); }
  input[type="range"] { width: 140px; accent-color: var(--accent); }

  .diag {
    margin-top: 18px;
    color: var(--muted);
    font-size: 0.78rem;
    text-align: center;
    max-width: 320px;
    min-height: 1.2em;
  }
  .hint {
    margin-top: 28px;
    color: #565c62;
    font-size: 0.72rem;
    text-align: center;
    max-width: 300px;
    line-height: 1.4;
  }
</style>
</head>
<body>

  <div class="label">Hold time</div>
  <div class="time" id="display">00:00<span class="ms">.00</span></div>
  <div class="status" id="status">Ready</div>

  <div class="controls">
    <button id="toggleBtn">Start</button>
    <button id="resetBtn" disabled>Reset</button>
  </div>

  <div class="settings">
    <div class="settings-row">
      <span>Voice volume</span>
      <input type="range" id="volSlider" min="0" max="1" step="0.05" value="0.45">
    </div>
    <div class="settings-row">
      <span>Earbud button stops timer</span>
      <input type="checkbox" id="earbudToggle" checked>
    </div>
  </div>

  <div class="diag" id="diag"></div>

  <div class="hint">Add this page to your Home Screen for the most reliable background counting. Tap the earbud remote's center button once to stop — it won't pause your music if it works as intended.</div>

  <audio id="keepAlive" loop playsinline style="display:none"
    src="data:audio/wav;base64,UklGRsQPAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YaAPAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICA">
  </audio>

<script>
  let startTime = 0;
  let elapsed = 0;
  let running = false;
  let intervalId = null;
  let voiceOn = true;
  let lastSpokenSecond = -1;

  const display = document.getElementById('display');
  const status = document.getElementById('status');
  const toggleBtn = document.getElementById('toggleBtn');
  const resetBtn = document.getElementById('resetBtn');
  const volSlider = document.getElementById('volSlider');
  const earbudToggle = document.getElementById('earbudToggle');
  const diag = document.getElementById('diag');
  const keepAlive = document.getElementById('keepAlive');

  function showDiag(msg) { diag.textContent = msg; }

  function format(ms) {
    const totalCentis = Math.floor(ms / 10);
    const centis = totalCentis % 100;
    const totalSeconds = Math.floor(ms / 1000);
    const seconds = totalSeconds % 60;
    const minutes = Math.floor(totalSeconds / 60);
    const pad = (n) => String(n).padStart(2, '0');
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return { main: `${pad(hours)}:${pad(mins)}:${pad(seconds)}`, ms: pad(centis) };
    }
    return { main: `${pad(minutes)}:${pad(seconds)}`, ms: pad(centis) };
  }

  function render() {
    const now = running ? elapsed + (Date.now() - startTime) : elapsed;
    const { main, ms } = format(now);
    display.innerHTML = `${main}<span class="ms">.${ms}</span>`;
    if (running) speakCount(now);
  }

  function speak(text) {
    if (!voiceOn) return;
    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.rate = 1.05;
      utter.volume = parseFloat(volSlider.value);
      window.speechSynthesis.speak(utter);
    } catch (e) { /* ignore */ }
  }

  function speakCount(totalMs) {
    const wholeSecond = Math.floor(totalMs / 1000);
    if (wholeSecond === lastSpokenSecond || wholeSecond === 0) return;
    lastSpokenSecond = wholeSecond;
    if (wholeSecond < 60) {
      speak(String(wholeSecond));
    } else {
      const mins = Math.floor(wholeSecond / 60);
      const secs = wholeSecond % 60;
      speak(secs === 0 ? `${mins} minute${mins === 1 ? '' : 's'}` : String(secs));
    }
  }

  function beep(freq, duration) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      osc.type = 'sine';
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration / 1000);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration / 1000);
    } catch (e) { /* ignore */ }
  }

  function setupMediaSession() {
    if (!('mediaSession' in navigator)) {
      showDiag('This browser has no MediaSession support — the earbud button won\u2019t reach the timer here, but the on-screen Stop button always works.');
      return;
    }
    navigator.mediaSession.metadata = new MediaMetadata({
      title: 'Hold Timer',
      artist: 'Tap earbud button to stop',
    });
    try {
      navigator.mediaSession.setActionHandler('pause', () => {
        if (earbudToggle.checked && running) stop();
        navigator.mediaSession.playbackState = running ? 'playing' : 'paused';
      });
      navigator.mediaSession.setActionHandler('stop', () => {
        if (earbudToggle.checked && running) stop();
      });
      navigator.mediaSession.setActionHandler('play', () => {
        if (earbudToggle.checked && !running) start();
      });
    } catch (e) {
      showDiag('MediaSession action handlers not supported here.');
    }
  }

  function start() {
    running = true;
    startTime = Date.now();
    lastSpokenSecond = Math.floor(elapsed / 1000) - 1;
    toggleBtn.textContent = 'Stop';
    toggleBtn.classList.add('running');
    status.textContent = 'Running';
    status.classList.add('running');
    resetBtn.disabled = true;
    beep(880, 90);

    keepAlive.play().catch(() => {
      showDiag('Background audio didn\u2019t start (tap Start again) \u2014 needed for the timer to keep counting with the screen locked.');
    });
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';

    intervalId = setInterval(render, 100);
    render();
  }

  function stop() {
    running = false;
    elapsed += Date.now() - startTime;
    clearInterval(intervalId);
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    keepAlive.pause();
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    toggleBtn.textContent = 'Start';
    toggleBtn.classList.remove('running');
    status.textContent = 'Stopped';
    status.classList.remove('running');
    resetBtn.disabled = false;
    beep(440, 140);
    render();
  }

  function reset() {
    elapsed = 0;
    lastSpokenSecond = -1;
    status.textContent = 'Ready';
    resetBtn.disabled = true;
    render();
  }

  toggleBtn.addEventListener('click', () => { running ? stop() : start(); });
  resetBtn.addEventListener('click', reset);

  setupMediaSession();
  render();
</script>
</body>
</html>
