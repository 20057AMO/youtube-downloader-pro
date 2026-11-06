/* ─────────────────────────────────────────────
   YouTube Downloader Pro - Frontend Logic
   Visual Identity: Web Builders Team
   ───────────────────────────────────────────── */

const API = '';

const DEFAULT_QUALITIES = ['2160', '1440', '1080', '720', '480', '360'];
const QUALITY_LABELS = {
  '2160': '4K (2160p)',
  '1440': '2K (1440p)',
  '1080': 'Full HD (1080p)',
  '720': 'HD (720p)',
  '480': 'SD (480p)',
  '360': '360p'
};
const POLL_INTERVAL_MS = 1000;
const POLL_MAX_ATTEMPTS = 60;

let currentInfo = null;
let currentUrl = '';
let currentMode = 'video';
let activeTaskId = null;
let sseSource = null;
let streamingTaskId = null;
let pollTimer = null;
let pollTaskId = null;
let currentFolder = '';
let isStarting = false;

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
  checkSystemHealth();
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
  currentInfo = null;
  currentUrl = '';
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
    const data = await res.json().catch(() => ({}));

    if (res.status === 429) throw new Error(t('toastRateLimited'));
    if (!res.ok || data.error) throw new Error(data.error || t('toastLinkError'));
    if (!data.info) throw new Error(t('toastLinkError'));

    currentInfo = data.info;
    currentUrl = url;

    if (currentInfo.type === 'playlist') {
      populateQualities(DEFAULT_QUALITIES);
    } else {
      populateQualities(Array.isArray(currentInfo.available_qualities)
        ? currentInfo.available_qualities
        : DEFAULT_QUALITIES);
    }

    renderInfoCard(currentInfo);
    toast(t('toastLinkSuccess'), 'success');

  } catch (err) {
    const message = err instanceof TypeError ? t('toastNetworkError') : (err.message || t('toastNetworkError'));
    toast(message, 'error');
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
    const items = Array.isArray(info.items) ? info.items : [];
    const count = info.count != null ? Number(info.count) || items.length : items.length;

    content.innerHTML = `
      <div class="video-detail-grid">
        <div class="thumb-container">
          ${info.thumbnail ? `<img src="${escAttr(info.thumbnail)}" alt="thumb" onerror="this.style.display='none'"/>` : ''}
        </div>
        <div class="video-meta-info">
          <div class="video-title">${escHtml(info.title)}</div>
          <div class="video-author">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            ${escHtml(info.uploader || t('unknown'))}
          </div>
          <div class="badges-row">
            <span class="modern-badge primary">${t('badgePlaylist')}</span>
            <span class="modern-badge success">${count} ${t('badgeCount')}</span>
          </div>
        </div>
      </div>
      <div class="playlist-preview-box">
        ${items.slice(0, 50).map((v, i) => `
          <div class="pl-row">
            <span class="pl-idx">${String(i + 1).padStart(2, '0')}</span>
            <span class="pl-name">${escHtml(v.title)}</span>
            ${Number(v.duration) > 0 ? `<span class="pl-dur">${fmtDuration(Number(v.duration))}</span>` : ''}
          </div>
        `).join('')}
        ${count > 50 ? `<div class="pl-row" style="justify-content:center;color:var(--secondary-text)">${t('extraItems', count - 50)}</div>` : ''}
      </div>
    `;

    actions.innerHTML = `
      <button class="btn-download-main" onclick="startDownload('playlist')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        ${t('downloadPlaylist')}
      </button>
    `;

  } else {
    const views = Number(info.view_count) > 0 ? formatNumber(Number(info.view_count)) + ' ' + t('badgeViews') : '';
    const duration = Number(info.duration) > 0 ? fmtDuration(Number(info.duration)) : '';

    content.innerHTML = `
      <div class="video-detail-grid">
        <div class="thumb-container">
          ${info.thumbnail ? `<img src="${escAttr(info.thumbnail)}" alt="thumb" onerror="this.style.display='none'"/>
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
  if (isStarting) return;
  isStarting = true;

  const startBtn = document.querySelector('#downloadActions .btn-download-main');
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.setAttribute('aria-busy', 'true');
  }

  const url = (currentUrl || urlInput.value).trim();
  const quality = document.getElementById('qualitySelect').value;
  const audioOnly = currentMode === 'audio';

  try {
    const res = await fetch(`${API}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, type, quality, audio_only: audioOnly })
    });
    const data = await res.json().catch(() => ({}));

    if (res.status === 429) {
      showSystemNotice(data.error || t('toastTooManyTasks'), 'error');
      toast(t('toastTooManyTasks'), 'error');
      return;
    }
    if (!res.ok || data.error) throw new Error(data.error || t('toastLinkError'));

    activeTaskId = data.task_id;
    showProgressCard(type);
    startStreaming(activeTaskId);
    toast(t('toastDownloadStart'), 'success');

  } catch (err) {
    const message = err instanceof TypeError ? t('toastNetworkError') : (err.message || t('toastNetworkError'));
    toast(message, 'error');
  } finally {
    isStarting = false;
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.removeAttribute('aria-busy');
    }
  }
}

// ─────────────────────
//  Progress Card
// ─────────────────────
function showProgressCard(type) {
  const card = document.getElementById('progressCard');
  const badge = document.getElementById('progressBadge');
  const bar = document.getElementById('progressBar');
  const errorList = document.getElementById('errorList');

  document.getElementById('progressTitle').textContent = type === 'playlist' ? t('progressPlaylistTitle') : t('progressSingleTitle');
  badge.textContent = '0%';
  badge.style.color = '';
  bar.style.width = '0%';
  bar.style.background = 'var(--accent-color)';
  document.getElementById('progressMessage').textContent = t('preparing');
  document.getElementById('playlistItems').innerHTML = '';
  errorList.innerHTML = '';
  errorList.style.display = 'none';
  document.getElementById('successActions').style.display = 'none';

  card.style.display = 'block';
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ─────────────────────
//  SSE Streaming
// ─────────────────────
function startStreaming(taskId) {
  if (sseSource && streamingTaskId === taskId) return;

  stopStreaming();
  stopPolling();
  streamingTaskId = taskId;

  let isFinished = false;
  const source = new EventSource(`${API}/api/stream/${taskId}`);
  sseSource = source;

  source.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      updateProgress(data);

      if (data.status === 'completed' || data.status === 'error') {
        isFinished = true;
        stopStreaming();
      }
    } catch (err) {
      // A malformed frame should not kill the stream; the next frame carries full state.
    }
  };

  source.onerror = () => {
    if (isFinished) return;
    isFinished = true;
    stopStreaming();
    pollProgress(taskId);
  };
}

function stopStreaming() {
  if (sseSource) {
    sseSource.close();
    sseSource = null;
  }
  streamingTaskId = null;
}

function pollProgress(taskId) {
  if (pollTaskId === taskId) return;

  stopPolling();
  pollTaskId = taskId;
  let attempts = 0;

  const tick = async () => {
    if (pollTaskId !== taskId) return;
    attempts += 1;

    let isFinished = false;
    try {
      const res = await fetch(`${API}/api/progress/${taskId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (pollTaskId !== taskId) return;

      updateProgress(data);
      isFinished = data.status === 'completed' || data.status === 'error';
    } catch (err) {
      // Transient network failure: retry until the attempt budget runs out.
    }

    if (pollTaskId !== taskId) return;
    if (isFinished) {
      stopPolling();
      return;
    }
    if (attempts >= POLL_MAX_ATTEMPTS) {
      stopPolling();
      toast(t('toastNetworkError'), 'error');
      return;
    }

    pollTimer = setTimeout(tick, POLL_INTERVAL_MS);
  };

  tick();
}

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
  pollTaskId = null;
}

function updateProgress(data) {
  const pct = Math.min(100, Math.max(0, Number(data.progress) || 0));
  const taskType = data.type || (currentInfo && currentInfo.type) || 'video';

  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressBadge').textContent = pct + '%';
  document.getElementById('progressMessage').textContent = data.message || '';

  const statusMap = {
    pending: t('progressPreparing'),
    fetching: t('progressFetching'),
    downloading: taskType === 'playlist'
      ? t('progressItemOf', data.current_item || 0, data.total || 0)
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
      renderMessages('errorList', t('errorCount', data.errors.length), data.errors.slice(0, 5));
    }
  }

  if (data.status === 'error') {
    document.getElementById('progressBar').style.background = 'var(--danger)';
    document.getElementById('progressBadge').style.color = 'var(--danger)';
    document.getElementById('successActions').style.display = 'flex';
    if (data.errors && data.errors.length > 0) {
      renderMessages('errorList', t('errorDetails'), data.errors);
    }
  }
}

function renderMessages(containerId, heading, messages) {
  const container = document.getElementById(containerId);
  const safeMessages = (Array.isArray(messages) ? messages : [])
    .map(message => escHtml(message))
    .join('<br>');

  container.innerHTML = `<strong>${escHtml(heading)}</strong><br>${safeMessages}`;
  container.style.display = 'block';
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

    const itemPct = Math.min(100, Math.max(0, Number(item.progress) || 0));

    return `
      <div class="progress-item-box ${cls}">
        <span>${icon}</span>
        <span class="item-prog-title">${escHtml(item.title || `${i+1}`)}</span>
        ${itemPct > 0 ? `<span class="item-prog-pct">${itemPct}%</span>` : ''}
      </div>
    `;
  }).join('');

  const active = container.querySelector('.progress-item-box.active');
  if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// ─────────────────────
//  History
// ─────────────────────
async function loadHistory(folder = '') {
  currentFolder = folder;
  const list = document.getElementById('historyList');
  list.innerHTML = '<div style="text-align:center;padding:40px;"><div class="spinner-css" style="margin:0 auto;"></div></div>';

  try {
    const url = folder
      ? `${API}/api/downloads?folder=${encodeURIComponent(folder)}`
      : `${API}/api/downloads`;
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) throw new Error(data.error || t('toastServer_error'));

    // Build header with breadcrumb
    let headerHtml = '';
    if (folder) {
      headerHtml = `
        <div class="history-breadcrumb">
          <button class="breadcrumb-back" onclick="loadHistory('')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            ${t('historyTitle')}
          </button>
          <span class="breadcrumb-separator">/</span>
          <span class="breadcrumb-current">${escHtml(folder)}</span>
        </div>
      `;
    }

    if (!data.files || data.files.length === 0) {
      list.innerHTML = headerHtml + `<div class="empty-state"><div class="empty-icon">&#128194;</div><p>${t('historyEmpty')}</p></div>`;
      return;
    }

    list.innerHTML = headerHtml + data.files.map(f => {
      const isFolder = f.type === 'folder';
      const icon = isFolder ? '\uD83D\uDCC1' : getFileIcon(f.name);
      const sizeStr = isFolder ? `${Number(f.count) || 0} ${t('historyItems')}` : formatBytes(Number(f.size) || 0);

      if (isFolder) {
        return `
          <button type="button" class="history-card-item" data-folder="${escAttr(f.name)}" onclick="loadHistory(this.dataset.folder)">
            <span class="hist-icon-box">${icon}</span>
            <span class="hist-details">
              <span class="hist-title">${escHtml(f.name)}</span>
              <span class="hist-meta">${sizeStr}</span>
            </span>
            <svg class="hist-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        `;
      } else {
        const downloadUrl = folder
          ? `${API}/api/download-file?name=${encodeURIComponent(f.name)}&folder=${encodeURIComponent(folder)}`
          : `${API}/api/download-file?name=${encodeURIComponent(f.name)}`;

        return `
          <div class="history-card-item">
            <div class="hist-icon-box">${icon}</div>
            <div class="hist-details">
              <div class="hist-title">${escHtml(f.name)}</div>
              <div class="hist-meta">${sizeStr}</div>
            </div>
            <a href="${downloadUrl}" class="hist-download-btn" title="${t('downloadFile')}" download>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            </a>
          </div>
        `;
      }
    }).join('');

  } catch (err) {
    const message = err instanceof TypeError ? t('toastNetworkError') : (err.message || t('toastNetworkError'));
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">&#9888;</div><p>${escHtml(message)}</p></div>`;
  }
}

// ─────────────────────
//  Actions
// ─────────────────────
async function openFolder() {
  try {
    const res = await fetch(`${API}/api/open-folder`, { method: 'POST' });
    const data = await res.json();

    if (data.opened) {
      toast(t('toastFolderOpen'), 'success');
    } else {
      // Folder couldn't be opened (e.g. mobile/remote access), redirect to history
      toast(t('toastFolderRedirect'), 'success');
      showSection('history');
    }
  } catch (err) {
    toast(t('toastServer_error'), 'error');
  }
}

function resetUI() {
  document.getElementById('progressCard').style.display = 'none';
  document.getElementById('infoCard').style.display = 'none';
  document.getElementById('progressBadge').style.color = '';
  urlInput.value = '';
  clearBtn.style.display = 'none';
  currentInfo = null;
  currentUrl = '';
  activeTaskId = null;
  stopStreaming();
  stopPolling();
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
  const iconEl = document.createElement('span');
  iconEl.setAttribute('aria-hidden', 'true');
  iconEl.textContent = icon;

  const messageEl = document.createElement('span');
  messageEl.textContent = String(msg ?? '');

  el.append(iconEl, messageEl);
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    setTimeout(() => el.remove(), 400);
  }, 4000);
}

// ─────────────────────
//  System health / notices
// ─────────────────────
async function checkSystemHealth() {
  try {
    const res = await fetch(`${API}/api/health`);
    if (!res.ok) return;

    const data = await res.json();
    if (data.ffmpeg === false) {
      showSystemNotice(t('ffmpegMissing'), 'warning', 'ffmpegMissing');
    }
  } catch (err) {
    // Health is advisory: if it cannot be read, stay quiet rather than blocking the UI.
  }
}

function showSystemNotice(message, variant = 'warning', messageKey = '') {
  const notice = document.getElementById('systemNotice');
  if (!notice) return;

  const text = document.createElement('span');
  text.className = 'system-notice-text';
  text.textContent = String(message);

  const dismissBtn = document.createElement('button');
  dismissBtn.type = 'button';
  dismissBtn.className = 'system-notice-dismiss';
  dismissBtn.setAttribute('aria-label', t('dismiss'));
  dismissBtn.textContent = '\u00D7';
  dismissBtn.addEventListener('click', hideSystemNotice);

  notice.className = `system-notice ${variant}`;
  notice.dataset.variant = variant;
  notice.dataset.messageKey = messageKey;
  notice.replaceChildren(text, dismissBtn);
  notice.style.display = 'flex';
}

function hideSystemNotice() {
  const notice = document.getElementById('systemNotice');
  if (!notice) return;
  notice.style.display = 'none';
  notice.replaceChildren();
}

document.addEventListener('languageChanged', () => {
  const notice = document.getElementById('systemNotice');
  const messageKey = notice && notice.dataset.messageKey;
  if (!messageKey || notice.style.display === 'none') return;
  showSystemNotice(t(messageKey), notice.dataset.variant || 'warning', messageKey);
});

// ─────────────────────
//  Helpers
// ─────────────────────
function populateQualities(list) {
  const select = document.getElementById('qualitySelect');
  const previous = select.value;

  const values = Array.from(new Set(
    (Array.isArray(list) ? list : [])
      .filter(value => value !== null && value !== undefined && value !== '' && String(value) !== 'best')
      .map(value => String(value))
  )).sort((a, b) => Number(b) - Number(a));

  const best = document.createElement('option');
  best.value = 'best';
  best.textContent = t('qualityBest');
  best.setAttribute('data-i18n', 'qualityBest');

  const options = [best, ...values.map(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = QUALITY_LABELS[value] || `${value}p`;
    return option;
  })];

  select.replaceChildren(...options);
  select.value = options.some(option => option.value === previous) ? previous : 'best';
  select.disabled = currentMode === 'audio';
}

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
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
