/* ─────────────────────────────────────────────
   YouTube Downloader Pro - Frontend Logic
   Visual Identity: Web Builders Team
   ───────────────────────────────────────────── */

const API = '';

let currentInfo = null;
let currentMode = 'video';
let activeTaskId = null;
let sseSource = null;

// ─────────────────────
//  Preloader
// ─────────────────────
window.addEventListener('load', () => {
  const preloader = document.getElementById('preloader');
  if (preloader) {
    setTimeout(() => {
      preloader.classList.add('fade-out');
      setTimeout(() => preloader.remove(), 800);
    }, 1200);
  }

  setLanguage(getCurrentLang());
});

// ─────────────────────
//  Navigation
// ─────────────────────
function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const sectionId = `section${name.charAt(0).toUpperCase() + name.slice(1)}`;
  const navId = `nav${name.charAt(0).toUpperCase() + name.slice(1)}`;

  document.getElementById(sectionId).classList.add('active');
  document.getElementById(navId).classList.add('active');

  if (name === 'history') loadHistory();
}

// ─────────────────────
//  Input Handling
// ─────────────────────
const urlInput = document.getElementById('urlInput');
const clearBtn = document.getElementById('clearBtn');

urlInput.addEventListener('input', () => {
  clearBtn.style.display = urlInput.value ? 'flex' : 'none';
});

urlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchInfo();
});

function clearInput() {
  urlInput.value = '';
  clearBtn.style.display = 'none';
  hideInfoCard();
  urlInput.focus();
}

function setMode(mode) {
  currentMode = mode;
  document.getElementById('btnVideo').classList.toggle('active', mode === 'video');
  document.getElementById('btnAudio').classList.toggle('active', mode === 'audio');
  document.getElementById('qualitySelect').disabled = (mode === 'audio');
}

// ─────────────────────
//  Fetch Video Info
// ─────────────────────
async function fetchInfo() {
  const url = urlInput.value.trim();
  if (!url) { toast(t('toastLinkError'), 'error'); urlInput.focus(); return; }

  const btn = document.getElementById('fetchBtn');
  btn.disabled = true;
  btn.innerHTML = '<div class="spinner-css"></div>';
  hideInfoCard();

  try {
    const res = await fetch(`${API}/api/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();

    if (!res.ok || data.error) throw new Error(data.error || t('toastLinkError'));

    currentInfo = data.info;
    renderInfoCard(currentInfo);
    toast(t('toastLinkSuccess'), 'success');

  } catch (err) {
    toast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span data-i18n="fetchBtn">${t('fetchBtn')}</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>`;
  }
}

// ─────────────────────
//  Render Info Card
// ─────────────────────
function renderInfoCard(info) {
  const card = document.getElementById('infoCard');
  const content = document.getElementById('infoContent');
  const actions = document.getElementById('downloadActions');

  const playSvg = `<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>`;

  if (info.type === 'playlist') {
    content.innerHTML = `
      <div class="video-detail-grid">
        <div class="thumb-container">
          ${info.thumbnail ? `<img src="${info.thumbnail}" alt="thumb" onerror="this.style.display='none'"/>` : ''}
        </div>
        <div class="video-meta-info">
          <div class="video-title">${escHtml(info.title)}</div>
          <div class="video-author">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            ${escHtml(info.uploader || t('unknown'))}
          </div>
          <div class="badges-row">
            <span class="modern-badge primary">${t('badgePlaylist')}</span>
            <span class="modern-badge success">${info.count} ${t('badgeCount')}</span>
          </div>
        </div>
      </div>
      <div class="playlist-preview-box">
        ${info.items.slice(0, 50).map((v, i) => `
          <div class="pl-row">
            <span class="pl-idx">${String(i + 1).padStart(2, '0')}</span>
            <span class="pl-name">${escHtml(v.title)}</span>
            ${v.duration ? `<span class="pl-dur">${fmtDuration(v.duration)}</span>` : ''}
          </div>
        `).join('')}
        ${info.count > 50 ? `<div class="pl-row" style="justify-content:center;color:var(--secondary-text)">${t('extraItems', info.count - 50)}</div>` : ''}
      </div>
    `;

    actions.innerHTML = `
      <button class="btn-download-main" onclick="startDownload('playlist')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        ${t('downloadPlaylist')}
      </button>
    `;

  } else {
    const views = info.view_count ? formatNumber(info.view_count) + ' ' + t('badgeViews') : '';
    const duration = info.duration ? fmtDuration(info.duration) : '';

    content.innerHTML = `
      <div class="video-detail-grid">
        <div class="thumb-container">
          ${info.thumbnail ? `<img src="${info.thumbnail}" alt="thumb" onerror="this.style.display='none'"/>
            <div class="play-icon-overlay">${playSvg}</div>` : ''}
        </div>
        <div class="video-meta-info">
          <div class="video-title">${escHtml(info.title)}</div>
          <div class="video-author">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            ${escHtml(info.uploader || t('unknown'))}
          </div>
          <div class="badges-row">
            <span class="modern-badge primary">${t('badgeVideo')}</span>
            ${duration ? `<span class="modern-badge">${duration}</span>` : ''}
            ${views ? `<span class="modern-badge">${views}</span>` : ''}
          </div>
        </div>
      </div>
    `;

    actions.innerHTML = `
      <button class="btn-download-main" onclick="startDownload('video')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        ${t('downloadStart')}
      </button>
    `;
  }

  card.style.display = 'block';
}

function hideInfoCard() {
  document.getElementById('infoCard').style.display = 'none';
}

// ─────────────────────
//  Start Download
// ─────────────────────
async function startDownload(type) {
  const url = urlInput.value.trim();
  const quality = document.getElementById('qualitySelect').value;
  const audioOnly = currentMode === 'audio';

  try {
    const res = await fetch(`${API}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, type, quality, audio_only: audioOnly })
    });
    const data = await res.json();

    if (!res.ok || data.error) throw new Error(data.error || t('toastLinkError'));

    activeTaskId = data.task_id;
    showProgressCard(type);
    startStreaming(activeTaskId);
    toast(t('toastDownloadStart'), 'success');

  } catch (err) {
    toast(err.message, 'error');
  }
}

// ─────────────────────
//  Progress Card
// ─────────────────────
function showProgressCard(type) {
  const card = document.getElementById('progressCard');

  document.getElementById('progressTitle').textContent = type === 'playlist' ? t('progressPlaylistTitle') : t('progressSingleTitle');
  document.getElementById('progressBadge').textContent = '0%';
  document.getElementById('progressBar').style.width = '0%';
  document.getElementById('progressBar').style.background = 'var(--accent-color)';
  document.getElementById('progressMessage').textContent = t('preparing');
  document.getElementById('playlistItems').innerHTML = '';
  document.getElementById('errorList').style.display = 'none';
  document.getElementById('successActions').style.display = 'none';

  card.style.display = 'block';
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ─────────────────────
//  SSE Streaming
// ─────────────────────
function startStreaming(taskId) {
  if (sseSource) { sseSource.close(); sseSource = null; }

  sseSource = new EventSource(`${API}/api/stream/${taskId}`);

  sseSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgress(data);

      if (data.status === 'completed' || data.status === 'error') {
        sseSource.close();
        sseSource = null;
      }
    } catch(err) { /* ignore */ }
  };

  sseSource.onerror = () => {
    sseSource.close();
    sseSource = null;
    pollProgress(taskId);
  };
}

async function pollProgress(taskId) {
  while (true) {
    try {
      const res = await fetch(`${API}/api/progress/${taskId}`);
      const data = await res.json();
      updateProgress(data);
      if (data.status === 'completed' || data.status === 'error') break;
    } catch {}
    await new Promise(r => setTimeout(r, 1000));
  }
}

function updateProgress(data) {
  const pct = data.progress || 0;

  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressBadge').textContent = pct + '%';
  document.getElementById('progressMessage').textContent = data.message || '';

  const statusMap = {
    pending: t('progressPreparing'),
    fetching: t('progressFetching'),
    downloading: data.type === 'playlist'
      ? t('progressItemOf', data.current_item, data.total)
      : t('progressDownloading'),
    completed: t('progressCompleted'),
    error: t('progressError')
  };
  document.getElementById('progressTitle').textContent = statusMap[data.status] || t('progressDownloading');

  if (data.items && data.items.length > 0) {
    renderProgressItems(data.items);
  }

  if (data.status === 'completed') {
    document.getElementById('progressBadge').textContent = '100%';
    document.getElementById('progressBar').style.background = 'var(--success)';
    document.getElementById('progressBadge').style.color = 'var(--success)';
    document.getElementById('successActions').style.display = 'flex';

    if (data.errors && data.errors.length > 0) {
      const errList = document.getElementById('errorList');
      errList.innerHTML = `<strong>${t('errorCount', data.errors.length)}</strong><br>` + data.errors.slice(0, 5).join('<br>');
      errList.style.display = 'block';
    }
  }

  if (data.status === 'error') {
    document.getElementById('progressBar').style.background = 'var(--danger)';
    document.getElementById('progressBadge').style.color = 'var(--danger)';
    document.getElementById('successActions').style.display = 'flex';
    if (data.errors && data.errors.length > 0) {
      const errList = document.getElementById('errorList');
      errList.innerHTML = `<strong>${t('errorDetails')}</strong><br>` + data.errors.join('<br>');
      errList.style.display = 'block';
    }
  }
}

function renderProgressItems(items) {
  const container = document.getElementById('playlistItems');
  if (!container || items.length === 0) return;

  container.innerHTML = items.map((item, i) => {
    const icon = {
      pending: '\u23F3', downloading: '\u2B07\uFE0F', completed: '\u2705', error: '\u274C'
    }[item.status] || '\u23F3';

    const cls = {
      pending: '', downloading: 'active', completed: 'done', error: 'error'
    }[item.status] || '';

    return `
      <div class="progress-item-box ${cls}">
        <span>${icon}</span>
        <span class="item-prog-title">${escHtml(item.title || `${i+1}`)}</span>
        ${item.progress ? `<span class="item-prog-pct">${item.progress}%</span>` : ''}
      </div>
    `;
  }).join('');

  const active = container.querySelector('.progress-item-box.active');
  if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// ─────────────────────
//  History
// ─────────────────────
async function loadHistory() {
  const list = document.getElementById('historyList');
  list.innerHTML = '<div style="text-align:center;padding:40px;"><div class="spinner-css" style="margin:0 auto;"></div></div>';

  try {
    const res = await fetch(`${API}/api/downloads`);
    const data = await res.json();

    if (!data.files || data.files.length === 0) {
      list.innerHTML = `<div class="empty-state"><div class="empty-icon">&#128194;</div><p>${t('historyEmpty')}</p></div>`;
      return;
    }

    list.innerHTML = data.files.map(f => {
      const isFolder = f.type === 'folder';
      const icon = isFolder ? '\uD83D\uDCC1' : getFileIcon(f.name);
      const sizeStr = isFolder ? `${f.count} ${t('historyItems')}` : formatBytes(f.size);

      return `
        <div class="history-card-item">
          <div class="hist-icon-box">${icon}</div>
          <div class="hist-details">
            <div class="hist-title">${escHtml(f.name)}</div>
            <div class="hist-meta">${sizeStr}</div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">&#9888;</div><p>${err.message}</p></div>`;
  }
}

// ─────────────────────
//  Actions
// ─────────────────────
async function openFolder() {
  try {
    const res = await fetch(`${API}/api/open-folder`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      toast(t('toastFolderOpen'), 'success');
    } else {
      toast(t('toastFolderError'), 'error');
    }
  } catch (err) {
    toast(t('toastServer_error'), 'error');
  }
}

function resetUI() {
  document.getElementById('progressCard').style.display = 'none';
  document.getElementById('infoCard').style.display = 'none';
  urlInput.value = '';
  clearBtn.style.display = 'none';
  currentInfo = null;
  activeTaskId = null;
  if (sseSource) { sseSource.close(); sseSource = null; }
  urlInput.focus();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ─────────────────────
//  Toast
// ─────────────────────
function toast(msg, type = '') {
  const container = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = `toast-msg ${type}`;

  const icon = type === 'success' ? '\u2705' : type === 'error' ? '\u274C' : '\u2139\uFE0F';
  el.innerHTML = `<span>${icon}</span> <span>${msg}</span>`;

  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    setTimeout(() => el.remove(), 400);
  }, 4000);
}

// ─────────────────────
//  Helpers
// ─────────────────────
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtDuration(secs) {
  if (!secs) return '';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function formatNumber(n) {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function formatBytes(b) {
  if (!b) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (b >= 1024 && i < units.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(1)} ${units[i]}`;
}

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const icons = { mp4: '\uD83C\uDFAC', mkv: '\uD83C\uDFAC', webm: '\uD83C\uDFAC', mp3: '\uD83C\uDFB5', m4a: '\uD83C\uDFB5', wav: '\uD83C\uDFB5', ogg: '\uD83C\uDFB5' };
  return icons[ext] || '\uD83D\uDCC4';
}
