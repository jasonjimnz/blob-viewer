/* Blob Viewer — UI helpers: toasts, modals, formatting, theme */
window.BV = window.BV || {};

BV.ui = (() => {
  const { icons } = BV;

  // ---- formatting ---------------------------------------------------------

  function formatSize(bytes) {
    if (bytes === null || bytes === undefined) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    let n = Number(bytes), u = 0;
    while (n >= 1024 && u < units.length - 1) { n /= 1024; u++; }
    return u === 0 ? `${n} ${units[u]}` : `${n.toFixed(1)} ${units[u]}`;
  }

  function formatDate(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function basename(key) { return key.replace(/\/+$/, '').split('/').pop() || key; }
  function dirname(key) {
    const parts = key.replace(/\/+$/, '').split('/');
    parts.pop();
    return parts.length ? parts.join('/') + '/' : '';
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---- toasts ---------------------------------------------------------------

  function toast(message, kind = 'info', timeout = 3800) {
    let host = document.getElementById('toasts');
    if (!host) { host = document.createElement('div'); host.id = 'toasts'; document.body.appendChild(host); }
    const node = document.createElement('div');
    node.className = `toast ${kind}`;
    const iconName = { success: 'checkCircle', error: 'x', warn: 'clock', info: 'eye' }[kind] || 'eye';
    node.innerHTML = `<span style="flex:none;margin-top:1px">${icons.el(iconName)}</span><div>${escapeHtml(message)}</div>`;
    host.appendChild(node);
    if (timeout) setTimeout(() => { node.style.opacity = '0'; node.style.transition = 'opacity .3s'; setTimeout(() => node.remove(), 320); }, timeout);
    return node;
  }

  // ---- modals -----------------------------------------------------------------

  function openModal(contentEl, { narrow = false, onClose = null } = {}) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    const modal = document.createElement('div');
    modal.className = `modal${narrow ? ' narrow' : ''}`;
    modal.appendChild(contentEl);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    const close = () => { overlay.remove(); if (onClose) onClose(); };
    overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
    });
    return { close, overlay, modal };
  }

  function modalHead(title, sub) {
    const head = document.createElement('div');
    head.className = 'modal-head';
    head.innerHTML = `<div class="m-title">${title}${sub ? `<span class="m-sub">${escapeHtml(sub)}</span>` : ''}</div>`;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'iconbtn';
    closeBtn.innerHTML = icons.el('x');
    closeBtn.addEventListener('click', () => closeBtn.closest('.modal-overlay')?.remove());
    head.appendChild(closeBtn);
    return head;
  }

  // ---- theme --------------------------------------------------------------------

  function applyTheme(name) {
    document.documentElement.setAttribute('data-theme', name || 'obsidian');
    try { localStorage.setItem('bv-theme', name || 'obsidian'); } catch { /* private mode */ }
  }

  function savedTheme() {
    try { return localStorage.getItem('bv-theme'); } catch { return null; }
  }

  // ---- context menu ----------------------------------------------------------------

  function contextMenu(x, y, items) {
    document.querySelectorAll('.ctx-menu').forEach((m) => m.remove());
    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    for (const item of items) {
      if (item === '-') { const sep = document.createElement('div'); sep.className = 'ctx-sep'; menu.appendChild(sep); continue; }
      const btn = document.createElement('button');
      if (item.danger) btn.className = 'danger';
      btn.innerHTML = `${icons.el(item.icon || 'more')}<span>${escapeHtml(item.label)}</span>`;
      btn.addEventListener('click', () => { menu.remove(); item.action(); });
      menu.appendChild(btn);
    }
    document.body.appendChild(menu);
    const rect = menu.getBoundingClientRect();
    menu.style.left = `${Math.min(x, window.innerWidth - rect.width - 8)}px`;
    menu.style.top = `${Math.min(y, window.innerHeight - rect.height - 8)}px`;
    setTimeout(() => document.addEventListener('mousedown', function handler(e) {
      if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('mousedown', handler); }
    }), 0);
  }

  // ---- misc ---------------------------------------------------------------------------

  function copyText(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text).then(() => toast('Copied to clipboard', 'success'));
    return Promise.reject();
  }

  return { formatSize, formatDate, basename, dirname, escapeHtml, toast, openModal, modalHead, applyTheme, savedTheme, contextMenu, copyText };
})();
