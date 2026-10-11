/* ==========================================================================
   Blob Viewer — main application (vanilla JS, no framework)
   ========================================================================== */
'use strict';
window.BV = window.BV || {};

(() => {
  const { api, icons, ui } = BV;

  const state = {
    session: null,
    workspaces: [],
    currentId: null,
    prefix: '',
    view: 'list',
    sortBy: 'name',
    sortDir: 'asc',
    entries: [],          // {key, size, last_modified, is_dir, category}
    versions: {},         // key -> version info
    searching: false,
  };

  const $ = (sel) => document.querySelector(sel);

  // =========================================================================
  // boot
  // =========================================================================

  async function boot() {
    ui.applyTheme(ui.savedTheme() || 'obsidian');
    renderShell();
    try {
      state.session = await api.session();
    } catch (err) {
      ui.toast(`Cannot reach the server: ${err.message}`, 'error');
      return;
    }
    ui.applyTheme(state.session.theme || ui.savedTheme() || 'obsidian');

    document.addEventListener('bv:auth-required', showLogin);

    if (state.session.locked && !state.session.authenticated) {
      showLogin();
      return;
    }
    await start();
  }

  async function start() {
    await loadSettingsAndWorkspaces();
    bindGlobalEvents();
    const first = state.workspaces[0];
    if (first) selectWorkspace(first.id);
    else showEmptyWorkspaces();
  }

  async function loadSettingsAndWorkspaces() {
    try {
      const [settings, wsData] = await Promise.all([api.settings(), api.workspaces()]);
      Object.assign(state, {
        view: settings.settings.view_mode || 'list',
        sortBy: settings.settings.sort_by || 'name',
        sortDir: settings.settings.sort_dir || 'asc',
      });
      state.workspaces = wsData.workspaces;
      ui.applyTheme(settings.settings.theme || ui.savedTheme());
      renderSidebar();
    } catch (err) {
      ui.toast(err.message, 'error');
    }
  }

  // =========================================================================
  // login / locked mode
  // =========================================================================

  function showLogin(needsSetup) {
    $('#login')?.remove();
    const setup = needsSetup ?? state.session?.needs_setup;
    const wrap = document.createElement('div');
    wrap.className = 'login-wrap';
    wrap.id = 'login';
    wrap.innerHTML = `
      <div class="login-card">
        <div class="brand"><span class="logo">${icons.el('logo')}</span> Blob Viewer</div>
        <div class="login-sub">${setup
          ? 'Welcome! Create the master admin account.<br>This account unlocks Blob Viewer.'
          : 'This instance is locked. Sign in to continue.'}</div>
        <div class="login-error" id="login-error"></div>
        <div class="form-grid">
          <div class="form-row"><label>Username</label>
            <input type="text" id="login-user" autocomplete="username" value="${setup ? 'admin' : ''}"></div>
          <div class="form-row"><label>Password</label>
            <input type="password" id="login-pass" autocomplete="${setup ? 'new-password' : 'current-password'}"></div>
          ${setup ? `
          <div class="form-row"><label>Confirm password</label>
            <input type="password" id="login-pass2" autocomplete="new-password"></div>
          <div class="form-note">Minimum 8 characters. These credentials are stored only on this machine
          (PBKDF2-hashed) and are required to unlock the app.</div>` : ''}
          <button class="btn primary" id="login-btn" style="justify-content:center">${setup ? 'Create account & sign in' : 'Sign in'}</button>
        </div>
      </div>`;
    document.body.appendChild(wrap);
    const submit = async () => {
      const err = wrap.querySelector('#login-error');
      err.textContent = '';
      try {
        await api.login(
          wrap.querySelector('#login-user').value.trim(),
          wrap.querySelector('#login-pass').value,
          setup ? wrap.querySelector('#login-pass2').value : undefined,
        );
        state.session = await api.session();
        wrap.remove();
        await start();
      } catch (e) { err.textContent = e.message; }
    };
    wrap.querySelector('#login-btn').addEventListener('click', submit);
    wrap.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
    setTimeout(() => (setup ? wrap.querySelector('#login-pass') : wrap.querySelector('#login-user')).focus(), 60);
  }

  async function logout() {
    try { await api.logout(); } catch { /* ignore */ }
    location.reload();
  }

  // =========================================================================
  // shell
  // =========================================================================

  function renderShell() {
    document.getElementById('app').innerHTML = `
      <header class="topbar">
        <button class="iconbtn" id="btn-rail" title="Toggle sidebar">${icons.el('sidebar')}</button>
        <div class="brand"><span class="logo">${icons.el('logo')}</span> Blob Viewer <span class="version"></span></div>
        <div class="searchbox">${icons.el('search')}
          <input type="text" id="search-input" placeholder="Search in this workspace…">
        </div>
        <div class="topbar-actions">
          <button class="iconbtn" id="btn-view" title="Toggle list/grid view">${icons.el('grid')}</button>
          <button class="iconbtn" id="btn-refresh" title="Refresh">${icons.el('refresh')}</button>
          <button class="iconbtn" id="btn-newfolder" title="New folder (writable workspaces)">${icons.el('folderPlus')}</button>
          <button class="iconbtn" id="btn-cache" title="Cache & settings">${icons.el('settings')}</button>
          <button class="iconbtn hidden" id="btn-logout" title="Sign out">${icons.el('logout')}</button>
        </div>
      </header>
      <nav class="sidebar">
        <div class="sidebar-section">
          <h3>Workspaces</h3>
          <button class="iconbtn" id="btn-add-ws" title="Add workspace" style="width:28px;height:28px">${icons.el('plus')}</button>
        </div>
        <ul class="ws-list" id="ws-list"></ul>
        <div class="sidebar-footer" id="cache-footer"></div>
      </nav>
      <main class="main">
        <div class="crumbbar" id="crumbbar"></div>
        <div class="file-area" id="file-area"></div>
      </main>`;
  }

  function bindGlobalEvents() {
    $('#btn-rail').addEventListener('click', () => {
      document.getElementById('app').classList.toggle('rail-collapsed');
    });
    $('#btn-view').addEventListener('click', async () => {
      state.view = state.view === 'list' ? 'grid' : 'list';
      $('#btn-view').innerHTML = icons.el(state.view === 'list' ? 'grid' : 'list');
      await api.saveSettings({ view_mode: state.view });
      renderEntries();
    });
    $('#btn-refresh').addEventListener('click', () => loadObjects(state.prefix, { force: true }));
    $('#btn-add-ws').addEventListener('click', () => showWorkspaceModal());
    $('#btn-cache').addEventListener('click', () => showSettings());
    $('#btn-newfolder').addEventListener('click', () => newFolder());
    $('#btn-logout').addEventListener('click', logout);
    if (state.session?.locked) $('#btn-logout').classList.remove('hidden');

    const searchInput = $('#search-input');
    let searchTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        const q = searchInput.value.trim();
        if (q) runSearch(q); else loadObjects(state.prefix);
      }, 280);
    });
    searchInput.addEventListener('keydown', (e) => { if (e.key === 'Escape') { searchInput.value = ''; loadObjects(state.prefix); } });

    document.querySelector('.version').textContent = `v${state.session.version}`;
  }

  // =========================================================================
  // sidebar
  // =========================================================================

  const WS_COLORS = ['#4cc2ff', '#a78bfa', '#4ade80', '#fbbf24', '#f87171', '#f472b6', '#2dd4bf', '#fb923c'];

  function renderSidebar() {
    const list = $('#ws-list');
    list.innerHTML = '';
    for (const ws of state.workspaces) {
      const li = document.createElement('li');
      li.className = `ws-item${ws.id === state.currentId ? ' active' : ''}`;
      const color = ws.color || WS_COLORS[state.workspaces.indexOf(ws) % WS_COLORS.length];
      li.innerHTML = `
        <span class="ws-dot" style="background:${color}"></span>
        <span class="ws-name">${ui.escapeHtml(ws.name)}</span>
        ${ws.sync_pending ? '<span class="ws-badge sync-dot" title="Updates available"></span>' : ''}
        <span class="ws-kind">${ws.kind === 's3' ? 'S3' : 'local'}</span>`;
      li.addEventListener('click', () => selectWorkspace(ws.id));
      li.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        ui.contextMenu(e.clientX, e.clientY, [
          { label: 'Open workspace', icon: 'folder', action: () => selectWorkspace(ws.id) },
          { label: 'Settings…', icon: 'edit', action: () => showWorkspaceModal(ws) },
          '-',
          { label: 'Clear cache', icon: 'trash', action: async () => {
            const r = await api.clearCache(ws.id);
            ui.toast(`Removed ${r.removed} cached files`, 'success');
            refreshCacheFooter();
          } },
          { label: 'Delete workspace…', icon: 'trash', danger: true, action: () => confirmDeleteWorkspace(ws) },
        ]);
      });
      list.appendChild(li);
    }
  }

  async function selectWorkspace(id) {
    state.currentId = id;
    state.prefix = '';
    $('#search-input').value = '';
    renderSidebar();
    await loadObjects('');
  }

  function showEmptyWorkspaces() {
    $('#crumbbar').innerHTML = '<span class="crumb current">No workspaces</span>';
    $('#file-area').innerHTML = `
      <div class="empty-state">
        ${icons.el('cloud')}
        <h3>Add your first workspace</h3>
        <p>Connect an S3-compatible bucket (AWS, MinIO, R2, B2…) or a local folder.</p>
        <button class="btn primary" id="empty-add">${icons.el('plus')} Add workspace</button>
      </div>`;
    $('#empty-add').addEventListener('click', () => showWorkspaceModal());
  }

  async function refreshCacheFooter() {
    try {
      const stats = await api.cache();
      const gb = stats.bytes / 1e9;
      const pct = Math.min(gb / 5 * 100, 100); // visual scale: 5 GB
      $('#cache-footer').innerHTML = `
        <div>Cache: <b>${stats.files}</b> files · ${ui.formatSize(stats.bytes)}</div>
        <div class="meter"><div style="width:${pct}%"></div></div>`;
    } catch { /* ignore */ }
  }

  // =========================================================================
  // browser
  // =========================================================================

  async function loadObjects(prefix, { force = false } = {}) {
    if (!state.currentId) return;
    state.prefix = prefix;
    state.searching = false;
    $('#search-input').value = '';
    const area = $('#file-area');
    area.innerHTML = '<div class="empty-state">Loading…</div>';
    try {
      const data = await api.objects(state.currentId, prefix);
      state.entries = [...data.dirs.map((d) => ({ key: d, is_dir: true, size: 0, last_modified: null })),
                       ...data.files];
      renderCrumbs();
      renderEntries();
      refreshCacheFooter();
      decorateVersions();
    } catch (err) {
      area.innerHTML = `<div class="empty-state">${icons.el('x')}<h3>Could not list this folder</h3><p>${ui.escapeHtml(err.message)}</p></div>`;
    }
  }

  async function decorateVersions() {
    const files = state.entries.filter((e) => !e.is_dir).map((e) => e.key);
    if (!files.length) { renderEntries(); return; }
    try {
      const res = await api.checkVersions(state.currentId, files.slice(0, 300));
      state.versions = res.versions;
    } catch { state.versions = {}; }
    renderEntries();
  }

  async function runSearch(q) {
    state.searching = true;
    const area = $('#file-area');
    area.innerHTML = '<div class="empty-state">Searching…</div>';
    try {
      const res = await api.search(state.currentId, q);
      if (!state.searching) return;
      state.entries = res.results;
      state.versions = {};
      renderCrumbs(null, `Search: “${q}”`);
      renderEntries(true);
      if (res.truncated) ui.toast('Search results truncated (200 shown)', 'warn');
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  function sortedEntries() {
    const dirs = state.entries.filter((e) => e.is_dir);
    const files = state.entries.filter((e) => !e.is_dir);
    const cmp = {
      name: (a, b) => ui.basename(a.key).localeCompare(ui.basename(b.key), undefined, { sensitivity: 'base', numeric: true }),
      size: (a, b) => a.size - b.size,
      modified: (a, b) => (a.last_modified || 0) - (b.last_modified || 0),
    }[state.sortBy] || ((a, b) => 0);
    const sign = state.sortDir === 'desc' ? -1 : 1;
    dirs.sort((a, b) => sign * ui.basename(a.key).localeCompare(ui.basename(b.key)));
    files.sort((a, b) => sign * cmp(a, b));
    return [...dirs, ...files];
  }

  function versionBadge(key) {
    const v = state.versions[key];
    if (!v) return '';
    if (v.sync_available) return `<span class="badge sync" data-sync="${ui.escapeHtml(key)}" title="A newer version exists upstream — click to sync">${icons.el('sync')} update</span>`;
    if (v.cached) return `<span class="badge cached" title="Cached locally — up to date">${icons.el('check')} cached</span>`;
    return '<span class="badge remote" title="Not downloaded yet — will be fetched on open">remote</span>';
  }

  function renderEntries(searchMode = false) {
    const area = $('#file-area');
    const entries = sortedEntries();
    if (!entries.length) {
      area.innerHTML = `<div class="empty-state">${icons.el('folder')}<h3>${searchMode ? 'No matches' : 'Empty folder'}</h3>
        ${searchMode ? '' : '<p>Drop files here (local workspaces) or upload from your S3 client.</p>'}</div>`;
      return;
    }

    const renderBadge = (e) => (e.is_dir ? '' : versionBadge(e.key));

    if (state.view === 'grid') {
      area.innerHTML = `<div class="file-grid">${entries.map((e) => `
        <div class="file-card" data-key="${ui.escapeHtml(e.key)}" data-dir="${e.is_dir ? 1 : 0}">
          <div class="card-icon">${icons.categoryIcon(e.category, e.is_dir)}</div>
          <div class="card-name" title="${ui.escapeHtml(e.key)}">${ui.escapeHtml(ui.basename(e.key))}</div>
          <div class="card-meta">${e.is_dir ? 'folder' : `${ui.formatSize(e.size)} · ${ui.formatDate(e.last_modified)}`}</div>
          <div class="card-badges">${renderBadge(e)}</div>
        </div>`).join('')}</div>`;
    } else {
      const arrow = (col) => (state.sortBy === col ? `<span class="arrow">${state.sortDir === 'asc' ? '▲' : '▼'}</span>` : '');
      area.innerHTML = `
        <table class="file-table">
          <thead><tr>
            <th data-sort="name">Name ${arrow('name')}</th>
            <th data-sort="size" style="width:110px">Size ${arrow('size')}</th>
            <th data-sort="modified" style="width:150px">Modified ${arrow('modified')}</th>
            <th style="width:150px">Status</th>
            <th style="width:44px"></th>
          </tr></thead>
          <tbody>
            ${entries.map((e) => `
            <tr class="row" data-key="${ui.escapeHtml(e.key)}" data-dir="${e.is_dir ? 1 : 0}">
              <td><div class="file-name"><span class="file-icon cat-${e.category || ''}">${icons.categoryIcon(e.category, e.is_dir)}</span>
                <span class="fname" title="${ui.escapeHtml(e.key)}">${ui.escapeHtml(ui.basename(e.key))}</span></div></td>
              <td class="file-meta">${e.is_dir ? '' : ui.formatSize(e.size)}</td>
              <td class="file-meta">${ui.formatDate(e.last_modified)}</td>
              <td>${renderBadge(e)}</td>
              <td><button class="iconbtn row-menu" data-menu="${ui.escapeHtml(e.key)}" title="More">${icons.el('more')}</button></td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    }

    bindRowEvents(area, searchMode);
  }

  function bindRowEvents(area, searchMode) {
    area.querySelectorAll('.row, .file-card').forEach((row) => {
      const key = row.dataset.key;
      const isDir = row.dataset.dir === '1';
      row.addEventListener('click', (e) => {
        if (e.target.closest('.row-menu, .badge.sync')) return;
        if (isDir) loadObjects(searchMode ? key : joinPath(state.prefix, key));
        else openPreview(key);
      });
      row.addEventListener('dblclick', () => { if (!isDir) openPreview(key); });
      const menuBtn = row.querySelector('.row-menu');
      (menuBtn || row).addEventListener('click', (e) => {
        if (e.target !== menuBtn && menuBtn) return;
        e.stopPropagation();
        showFileMenu(e.clientX || 0, e.clientY || 0, key, isDir);
      });
      row.addEventListener('contextmenu', (e) => { e.preventDefault(); showFileMenu(e.clientX, e.clientY, key, isDir); });
    });
    area.querySelectorAll('th[data-sort]').forEach((th) => {
      th.addEventListener('click', async () => {
        const col = th.dataset.sort;
        state.sortDir = state.sortBy === col && state.sortDir === 'asc' ? 'desc' : 'asc';
        state.sortBy = col;
        await api.saveSettings({ sort_by: col, sort_dir: state.sortDir });
        renderEntries();
      });
    });
    area.querySelectorAll('.badge.sync').forEach((badge) => {
      badge.addEventListener('click', async (e) => {
        e.stopPropagation();
        await syncFile(badge.dataset.sync);
      });
    });
  }

  function joinPath(prefix, key) {
    const full = (prefix || '') + key;
    return full;
  }

  function renderCrumbs(prefixOverride, label) {
    const bar = $('#crumbbar');
    const ws = state.workspaces.find((w) => w.id === state.currentId);
    if (label) {
      bar.innerHTML = `<span class="crumb" id="crumb-ws">${ui.escapeHtml(ws?.name || '')}</span>
        <span class="crumb-sep">/</span><span class="crumb current">${ui.escapeHtml(label)}</span>`;
      bar.querySelector('#crumb-ws').addEventListener('click', () => selectWorkspace(state.currentId));
      return;
    }
    const prefix = prefixOverride ?? state.prefix;
    let html = `<span class="crumb ${prefix ? '' : 'current'}" data-prefix="">${ui.escapeHtml(ws?.name || '')}</span>`;
    let acc = '';
    const parts = prefix.split('/').filter(Boolean);
    parts.forEach((part, i) => {
      acc += part + '/';
      const isLast = i === parts.length - 1;
      html += `<span class="crumb-sep">/</span>
        <span class="crumb ${isLast ? 'current' : ''}" data-prefix="${ui.escapeHtml(acc)}">${ui.escapeHtml(part)}</span>`;
    });
    bar.innerHTML = html;
    bar.querySelectorAll('.crumb[data-prefix]').forEach((c) => {
      c.addEventListener('click', () => loadObjects(c.dataset.prefix));
    });
  }

  // =========================================================================
  // file actions
  // =========================================================================

  function showFileMenu(x, y, key, isDir) {
    const ws = state.workspaces.find((w) => w.id === state.currentId);
    const v = state.versions[key] || {};
    const items = [];
    if (!isDir) {
      items.push({ label: 'Preview', icon: 'eye', action: () => openPreview(key) });
      items.push({ label: 'Download', icon: 'download', action: () => window.open(api.downloadUrl(state.currentId, key), '_blank') });
      if (v.sync_available) items.push({ label: 'Sync new version', icon: 'sync', action: () => syncFile(key) });
      if (v.cached) items.push({ label: 'Remove from cache', icon: 'trash', action: () => evictFile(key) });
    } else {
      items.push({ label: 'Open folder', icon: 'folder', action: () => loadObjects(joinPath(state.prefix, key)) });
    }
    items.push('-');
    items.push({ label: 'Copy path', icon: 'copy', action: () => ui.copyText(key).catch(() => {}) });
    if (ws?.writable) {
      items.push('-');
      items.push({ label: 'Rename…', icon: 'edit', action: () => renameFile(key, isDir) });
      items.push({ label: 'Delete…', icon: 'trash', danger: true, action: () => deleteFile(key, isDir) });
    }
    ui.contextMenu(x, y, items);
  }

  async function syncFile(key) {
    const t = ui.toast(`Syncing ${ui.basename(key)}…`, 'info', 0);
    try {
      await api.sync(state.currentId, key);
      t.remove();
      ui.toast(`Synced to latest version`, 'success');
      await loadObjects(state.prefix, { force: true });
      if (currentPreview?.key === key) openPreview(key);
    } catch (err) { t.remove(); ui.toast(err.message, 'error'); }
  }

  async function evictFile(key) {
    try {
      await api.evict(state.currentId, key);
      ui.toast(`Removed ${ui.basename(key)} from cache`, 'success');
      refreshCacheFooter();
      decorateVersions();
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  async function renameFile(key, isDir) {
    const newName = prompt('New name', ui.basename(key));
    if (!newName || newName === ui.basename(key)) return;
    const target = ui.dirname(key) + newName + (isDir && !newName.endsWith('/') ? '/' : '');
    try {
      await api.rename(state.currentId, key, target);
      ui.toast('Renamed', 'success');
      loadObjects(state.prefix);
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  async function deleteFile(key, isDir) {
    if (state.session && !await confirmModal(`Delete ${isDir ? 'folder' : 'file'}`, `This will permanently delete <b>${ui.escapeHtml(ui.basename(key))}</b> from the workspace.`)) return;
    try {
      await api.deleteFile(state.currentId, key);
      ui.toast('Deleted', 'success');
      loadObjects(state.prefix);
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  async function newFolder() {
    const ws = state.workspaces.find((w) => w.id === state.currentId);
    if (!ws?.writable) { ui.toast('Only writable local workspaces can create folders', 'warn'); return; }
    const name = prompt('Folder name');
    if (!name) return;
    try {
      await api.createFolder(state.currentId, state.prefix + name + '/');
      ui.toast('Folder created', 'success');
      loadObjects(state.prefix);
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  async function confirmDeleteWorkspace(ws) {
    if (!await confirmModal('Delete workspace', `Remove workspace <b>${ui.escapeHtml(ws.name)}</b> and its cached files?<br>Remote data is not touched.`)) return;
    try {
      await api.deleteWorkspace(ws.id);
      state.workspaces = state.workspaces.filter((w) => w.id !== ws.id);
      state.currentId = null;
      renderSidebar();
      showEmptyWorkspaces();
      ui.toast(`Workspace '${ws.name}' deleted`, 'success');
    } catch (err) { ui.toast(err.message, 'error'); }
  }

  function confirmModal(title, html) {
    return new Promise((resolve) => {
      const content = document.createElement('div');
      content.innerHTML = `${ui.modalHead(title)}
        <div class="modal-body">${html}</div>
        <div class="modal-foot">
          <button class="btn" data-a="no">Cancel</button>
          <button class="btn danger" data-a="yes">Delete</button>
        </div>`;
      const m = ui.openModal(content, { narrow: true, onClose: () => resolve(false) });
      content.querySelector('[data-a="no"]').addEventListener('click', () => { resolve(false); m.close(); });
      content.querySelector('[data-a="yes"]').addEventListener('click', () => { resolve(true); m.close(); });
    });
  }

  // =========================================================================
  // preview
  // =========================================================================

  let currentPreview = null;

  async function openPreview(key) {
    const t = ui.toast(`Opening ${ui.basename(key)}…`, 'info', 1500);
    let data;
    try {
      data = await api.open(state.currentId, key);
    } catch (err) { t.remove(); ui.toast(err.message, 'error'); return; }
    t.remove();
    currentPreview = { key };
    renderPreviewModal(key, data);
    if (state.versions[key]) state.versions[key].cached = true;
    refreshCacheFooter();
  }

  function renderPreviewModal(key, data) {
    const v = state.versions[key] || {};
    const ws = state.workspaces.find((w) => w.id === state.currentId);
    const content = document.createElement('div');
    content.innerHTML = `
      ${ui.modalHead(
        `<span class="file-icon cat-${data.category}">${icons.categoryIcon(data.category, false)}</span> ${ui.escapeHtml(ui.basename(key))}`,
        `${ui.formatSize(data.entry?.size)} · ${ui.formatDate(data.entry?.last_modified)}${ws ? ' · ' + ui.escapeHtml(ws.name) : ''}`,
      )}
      <div class="modal-body preview-body" id="preview-body"></div>
      <div class="modal-foot">
        ${v.sync_available ? `<button class="btn small" id="pv-sync" style="margin-right:auto">${icons.el('sync')} New version — sync</button>` : ''}
        <span class="badge ${data.downloaded ? 'cached' : 'cached'}" title="${data.downloaded ? 'Downloaded just now' : 'Served from local cache'}">${icons.el('check')} ${data.downloaded ? 'downloaded' : 'from cache'}</span>
        <a class="btn" href="${api.downloadUrl(state.currentId, key)}">${icons.el('download')} Download</a>
      </div>`;

    const body = content.querySelector('#preview-body');
    renderPreviewBody(body, key, data);

    const modal = ui.openModal(content, { onClose: () => { currentPreview = null; } });
    content.querySelector('#pv-sync')?.addEventListener('click', async () => {
      await syncFile(key);
      modal.close();
    });
  }

  function renderPreviewBody(body, key, data) {
    const url = data.raw_url;
    switch (data.category) {
      case 'markdown': return renderMarkdown(body, url);
      case 'code': return renderCode(body, url, data.language);
      case 'pdf': return renderPdf(body, url);
      case 'image': return renderImage(body, url);
      case 'csv': return renderCsv(body, url);
      case 'audio': case 'video': return renderMedia(body, url, data.category);
      case 'text': return renderText(body, url);
      default: return renderBinary(body, key);
    }
  }

  async function fetchText(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.text();
  }

  async function renderMarkdown(body, url) {
    body.className = 'preview-markdown';
    body.innerHTML = '<div class="empty-state">Rendering…</div>';
    try {
      const md = await fetchText(url);
      body.innerHTML = DOMPurify.sanitize(marked.parse(md), {
        ADD_ATTR: ['target'],
        FORBID_TAGS: ['style'],
      });
      body.querySelectorAll('a').forEach((a) => { a.target = '_blank'; a.rel = 'noopener'; });
      body.querySelectorAll('pre code').forEach((block) => window.hljs?.highlightElement(block));
    } catch (err) {
      body.innerHTML = `<div class="empty-state">Could not load file: ${ui.escapeHtml(err.message)}</div>`;
    }
  }

  async function renderCode(body, url, language) {
    body.className = 'preview-code';
    body.innerHTML = '<pre><code class="hljs">Loading…</code></pre>';
    try {
      const text = await fetchText(url);
      const codeEl = body.querySelector('code');
      if (window.hljs && language && hljs.getLanguage(language)) {
        codeEl.innerHTML = hljs.highlight(text, { language }).value;
      } else if (window.hljs) {
        codeEl.innerHTML = hljs.highlightAuto(text).value;
      } else {
        codeEl.textContent = text;
      }
    } catch (err) {
      body.innerHTML = `<div class="empty-state">Could not load file: ${ui.escapeHtml(err.message)}</div>`;
    }
  }

  async function renderText(body, url) {
    body.className = 'preview-text';
    body.innerHTML = 'Loading…';
    try { body.innerHTML = `<pre>${ui.escapeHtml(await fetchText(url))}</pre>`; }
    catch (err) { body.innerHTML = `<div class="empty-state">Could not load file: ${ui.escapeHtml(err.message)}</div>`; }
  }

  async function renderCsv(body, url) {
    body.className = 'preview-csv';
    body.innerHTML = '<div class="empty-state">Loading…</div>';
    try {
      const text = await fetchText(url);
      const lines = text.split(/\r?\n/).filter((l) => l.length).slice(0, 2000);
      const sep = (lines[0].match(/\t/g) || []).length > (lines[0].match(/,/g) || []).length ? '\t' : ',';
      const rows = lines.map((l) => parseCsvLine(l, sep));
      const head = rows.shift() || [];
      body.innerHTML = `<table><thead><tr>${head.map((h) => `<th>${ui.escapeHtml(h)}</th>`).join('')}</tr></thead>
        <tbody>${rows.map((r) => `<tr>${head.map((_, i) => {
          const cell = r[i] ?? '';
          const num = cell !== '' && !isNaN(Number(cell));
          return `<td class="${num ? 'num' : ''}">${ui.escapeHtml(cell)}</td>`;
        }).join('')}</tr>`).join('')}</tbody></table>`;
    } catch (err) {
      body.innerHTML = `<div class="empty-state">Could not load file: ${ui.escapeHtml(err.message)}</div>`;
    }
  }

  function parseCsvLine(line, sep) {
    const out = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') inQ = false;
        else cur += ch;
      } else if (ch === '"') inQ = true;
      else if (ch === sep) { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur);
    return out;
  }

  function renderImage(body, url) {
    body.className = 'preview-image';
    body.innerHTML = `<img src="${url}" alt="${ui.escapeHtml(url)}" loading="lazy">`;
  }

  function renderMedia(body, url, category) {
    body.className = 'preview-media';
    body.innerHTML = category === 'audio'
      ? `<audio controls src="${url}"></audio>`
      : `<video controls src="${url}"></video>`;
  }

  function renderBinary(body, key) {
    body.className = 'preview-binary';
    body.innerHTML = `
      ${icons.el('fileBin')}
      <div><b>${ui.escapeHtml(ui.basename(key))}</b><br>
      <span style="color:var(--text-faint)">This file type has no inline preview.</span></div>
      <a class="btn primary" href="${api.downloadUrl(state.currentId, key)}">${icons.el('download')} Download file</a>`;
  }

  function renderPdf(body, url) {
    body.className = 'preview-pdf';
    body.innerHTML = `
      <div class="pdf-controls">
        <button class="btn small" id="pdf-prev">◀</button>
        <span id="pdf-page">1 / ?</span>
        <button class="btn small" id="pdf-next">▶</button>
        <button class="btn small" id="pdf-zoom">Zoom ±</button>
      </div>
      <div id="pdf-canvas-host"></div>`;
    const host = body.querySelector('#pdf-canvas-host');
    const pageLabel = body.querySelector('#pdf-page');
    import('/static/vendor/pdfjs/pdf.min.mjs').then(async (pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = '/static/vendor/pdfjs/pdf.worker.min.mjs';
      const doc = await pdfjs.getDocument({ url }).promise;
      let page = 1;
      const draw = async () => {
        const p = await doc.getPage(page);
        const scale = 1.4;
        const viewport = p.getViewport({ scale });
        const canvas = document.createElement('canvas');
        canvas.width = viewport.width; canvas.height = viewport.height;
        await p.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
        host.replaceChildren(canvas);
        pageLabel.textContent = `${page} / ${doc.numPages}`;
      };
      body.querySelector('#pdf-prev').addEventListener('click', () => { if (page > 1) { page--; draw(); } });
      body.querySelector('#pdf-next').addEventListener('click', () => { if (page < doc.numPages) { page++; draw(); } });
      draw();
    }).catch((err) => {
      body.innerHTML = `<div class="empty-state">PDF viewer failed: ${ui.escapeHtml(err.message)}</div>`;
    });
  }

  // =========================================================================
  // workspace modal (add / edit)
  // =========================================================================

  function showWorkspaceModal(ws = null) {
    const editing = Boolean(ws);
    const content = document.createElement('div');
    content.innerHTML = `
      ${ui.modalHead(editing ? `Edit workspace — ${ui.escapeHtml(ws.name)}` : 'Add workspace')}
      <div class="modal-body">
        <div class="form-grid">
          <div class="form-row">
            <label>Workspace kind</label>
            <div class="seg" id="ws-kind">
              <button type="button" data-kind="s3" class="${(ws?.kind || 's3') === 's3' ? 'active' : ''}">S3 bucket</button>
              <button type="button" data-kind="local" class="${ws?.kind === 'local' ? 'active' : ''}">Local folder</button>
            </div>
            <span class="hint">S3 workspaces are read-only: files are cached locally for viewing but never modified.
            Local folders are private and writable.</span>
          </div>
          <div class="form-row"><label>Name <span class="req">*</span></label>
            <input type="text" id="ws-name" value="${ui.escapeHtml(ws?.name || '')}" placeholder="my-bucket"></div>

          <div id="ws-s3-fields" class="form-grid">
            <div class="form-row"><label>Endpoint URL <span class="req">*</span></label>
              <input type="text" id="ws-endpoint" value="${ui.escapeHtml(ws?.endpoint || '')}" placeholder="https://s3.amazonaws.com or http://localhost:9000">
              <span class="hint">AWS S3: https://s3.<i>region</i>.amazonaws.com — MinIO/RustFS: http://host:9000</span></div>
            <div class="form-row"><label>Bucket <span class="req">*</span></label>
              <input type="text" id="ws-bucket" value="${ui.escapeHtml(ws?.bucket || '')}" placeholder="my-bucket"></div>
            <div class="form-grid" style="flex-direction:row; gap:12px">
              <div class="form-row" style="flex:1"><label>Region</label>
                <input type="text" id="ws-region" value="${ui.escapeHtml(ws?.region || '')}" placeholder="us-east-1"></div>
              <div class="form-row" style="flex:1"><label>Root prefix</label>
                <input type="text" id="ws-prefix" value="${ui.escapeHtml(ws?.prefix || '')}" placeholder="optional/path/"></div>
            </div>
            <div class="form-row"><label>Access key</label>
              <input type="text" id="ws-ak" value="${ws ? ui.escapeHtml(ws.secrets?.access_key || '') : ''}" placeholder="${editing ? 'unchanged' : 'leave empty for anonymous access'}"></div>
            <div class="form-row"><label>Secret key</label>
              <input type="password" id="ws-sk" value="" placeholder="${editing && ws.secrets?.secret_key ? 'unchanged (••••)' : ''}">
              <span class="hint">Credentials are encrypted at rest and never sent back to the UI — only a masked hint is shown.</span></div>
            <div class="form-row inline">
              <label style="margin:0"><input type="checkbox" id="ws-pathstyle" ${ws ? (ws.path_style ? 'checked' : '') : 'checked'}> Path-style addressing (recommended for MinIO, RustFS, R2, B2)</label>
            </div>
          </div>

          <div id="ws-local-fields" class="form-grid hidden">
            <div class="form-row"><label>Folder path <span class="req">*</span></label>
              <input type="text" id="ws-localpath" value="${ui.escapeHtml(ws?.local_path || '')}" placeholder="C:\\Users\\me\\notes or /home/me/notes"></div>
            <div class="form-row inline">
              <label style="margin:0"><input type="checkbox" id="ws-readonly" ${ws?.read_only ? 'checked' : ''}> Read-only</label>
            </div>
          </div>
        </div>
      </div>
      <div class="modal-foot">
        <button class="btn" id="ws-cancel">Cancel</button>
        ${editing ? '' : '<button class="btn" id="ws-test">Test connection</button>'}
        <button class="btn primary" id="ws-save">${editing ? 'Save changes' : 'Add workspace'}</button>
      </div>`;

    const kindBtns = content.querySelectorAll('#ws-kind button');
    const setKind = (kind) => {
      kindBtns.forEach((b) => b.classList.toggle('active', b.dataset.kind === kind));
      content.querySelector('#ws-s3-fields').classList.toggle('hidden', kind !== 's3');
      content.querySelector('#ws-local-fields').classList.toggle('hidden', kind !== 'local');
      content.dataset.kind = kind;
    };
    kindBtns.forEach((b) => b.addEventListener('click', () => setKind(b.dataset.kind)));
    setKind(ws?.kind || 's3');

    const collect = () => {
      const kind = content.dataset.kind;
      const data = {
        name: content.querySelector('#ws-name').value.trim(),
        kind,
      };
      if (kind === 's3') {
        data.endpoint = content.querySelector('#ws-endpoint').value.trim();
        data.bucket = content.querySelector('#ws-bucket').value.trim();
        data.region = content.querySelector('#ws-region').value.trim() || null;
        data.prefix = content.querySelector('#ws-prefix').value.trim() || null;
        data.path_style = content.querySelector('#ws-pathstyle').checked;
        const ak = content.querySelector('#ws-ak').value.trim();
        const sk = content.querySelector('#ws-sk').value;
        data.secrets = {};
        if (ak && ak !== 'unchanged') data.secrets.access_key = ak;
        if (sk) data.secrets.secret_key = sk;
      } else {
        data.local_path = content.querySelector('#ws-localpath').value.trim();
        data.read_only = content.querySelector('#ws-readonly').checked;
      }
      return data;
    };

    const modal = ui.openModal(content);
    content.querySelector('#ws-cancel').addEventListener('click', () => modal.close());
    content.querySelector('#ws-test')?.addEventListener('click', async () => {
      const data = collect();
      if (!data.name) { ui.toast('Name is required', 'warn'); return; }
      const btn = content.querySelector('#ws-test');
      btn.disabled = true; btn.textContent = 'Testing…';
      try {
        // create hidden then test, or test directly on the not-yet-created workspace
        if (!editing) {
          const created = await api.createWorkspace(data);
          await api.testWorkspace(created.workspace.id);
          ui.toast('Connection OK — workspace added', 'success');
          modal.close();
          state.workspaces = (await api.workspaces()).workspaces;
          renderSidebar();
          selectWorkspace(created.workspace.id);
        } else {
          await api.testWorkspace(ws.id, data.secrets);
          ui.toast('Connection OK', 'success');
        }
      } catch (err) {
        ui.toast(err.message, 'error', 6000);
      } finally {
        btn.disabled = false; btn.textContent = 'Test connection';
      }
    });
    content.querySelector('#ws-save').addEventListener('click', async () => {
      const data = collect();
      try {
        if (editing) {
          const r = await api.updateWorkspace(ws.id, data);
          Object.assign(ws, r.workspace);
          ui.toast('Workspace updated', 'success');
        } else {
          const r = await api.createWorkspace(data);
          await api.testWorkspace(r.workspace.id).catch((e) => ui.toast(`Workspace added, but connection failed: ${e.message}`, 'warn', 7000));
          ui.toast(`Workspace '${data.name}' added`, 'success');
        }
        modal.close();
        state.workspaces = (await api.workspaces()).workspaces;
        renderSidebar();
        if (!editing) selectWorkspace(state.workspaces.find((w) => w.name === data.name)?.id);
        else loadObjects(state.prefix);
      } catch (err) { ui.toast(err.message, 'error', 6000); }
    });
  }

  // =========================================================================
  // settings modal
  // =========================================================================

  async function showSettings(tab = 'appearance') {
    const [settingsData, cacheData] = await Promise.all([api.settings(), api.cache()]);
    const themes = {
      obsidian: ['dark', '#0f1115', '#4cc2ff'], midnight: ['dark', '#060a18', '#6d8dff'],
      nord: ['dark', '#2e3440', '#88c0d0'], forest: ['dark', '#0e1512', '#5eead4'],
      aurora: ['dark', '#120b1e', '#c084fc'], paper: ['light', '#f7f8fa', '#2563eb'],
      sepia: ['light', '#f5efe3', '#b45309'], porcelain: ['light', '#f2f5f6', '#0d9488'],
    };
    const content = document.createElement('div');
    content.innerHTML = `
      ${ui.modalHead('Settings')}
      <div class="settings-tabs">
        <button data-tab="appearance" class="${tab === 'appearance' ? 'active' : ''}">Appearance</button>
        <button data-tab="cache" class="${tab === 'cache' ? 'active' : ''}">Cache</button>
        <button data-tab="workspaces" class="${tab === 'workspaces' ? 'active' : ''}">Workspaces</button>
        <button data-tab="security" class="${tab === 'security' ? 'active' : ''}">Security</button>
      </div>
      <div class="modal-body" id="settings-body"></div>
      <div class="modal-foot"><button class="btn primary" id="settings-close">Done</button></div>`;

    const body = content.querySelector('#settings-body');
    const currentTheme = settingsData.settings.theme;

    const renderAppearance = () => {
      body.innerHTML = `
        <h3 style="margin-bottom:10px">Theme</h3>
        <div class="theme-grid">
          ${Object.entries(themes).map(([name, [mode, bg, accent]]) => `
            <div class="theme-card ${name === currentTheme ? 'active' : ''}" data-theme-name="${name}">
              <div class="theme-swatch" style="background:${bg}">
                <div style="background:${accent};opacity:.85"></div>
                <div style="background:${bg};box-shadow:inset 0 0 0 1px ${accent}22"></div>
              </div>
              <div class="t-name">${name} <span style="opacity:.5;font-weight:400">· ${mode}</span></div>
            </div>`).join('')}
        </div>
        <p class="hint" style="margin-top:10px">The theme also applies to new windows. Changing it saves automatically.</p>`;
      body.querySelectorAll('.theme-card').forEach((card) => {
        card.addEventListener('click', async () => {
          const name = card.dataset.themeName;
          ui.applyTheme(name);
          await api.saveSettings({ theme: name });
          body.querySelectorAll('.theme-card').forEach((c) => c.classList.toggle('active', c.dataset.themeName === name));
        });
      });
    };

    const renderCache = () => {
      body.innerHTML = `
        <div class="kv-list">
          <div class="kv"><span class="k">Cached files</span><span class="v">${cacheData.files}</span></div>
          <div class="kv"><span class="k">Cache size</span><span class="v">${ui.formatSize(cacheData.bytes)}</span></div>
          <div class="kv"><span class="k">Storage folder</span><span class="v">${ui.escapeHtml(cacheData.home)}</span></div>
        </div>
        <p class="hint" style="margin:14px 0 10px">Blob Viewer downloads each file once and reuses the local copy.
        When a file changes upstream you'll see an "update" badge and can sync it.</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${state.workspaces.map((ws) => `<button class="btn small" data-clear="${ws.id}">${icons.el('trash')} Clear '${ui.escapeHtml(ws.name)}'</button>`).join('')}
          <button class="btn small danger" id="cache-clear-all">${icons.el('trash')} Clear everything</button>
        </div>`;
      body.querySelectorAll('[data-clear]').forEach((btn) => btn.addEventListener('click', async () => {
        const r = await api.clearCache(btn.dataset.clear);
        ui.toast(`Removed ${r.removed} files`, 'success');
        refreshCacheFooter();
      }));
      body.querySelector('#cache-clear-all').addEventListener('click', async () => {
        if (!await confirmModal('Clear cache', 'Delete <b>all</b> cached files? Files stay in the remote workspace.')) return;
        const r = await api.clearCache();
        ui.toast(`Removed ${r.removed} files`, 'success');
        refreshCacheFooter();
        Object.assign(cacheData, r); renderCache();
      });
    };

    const renderWorkspaces = () => {
      body.innerHTML = `
        <div class="kv-list">
          ${state.workspaces.map((ws) => `
            <div class="kv"><span class="k">
              <b>${ui.escapeHtml(ws.name)}</b> <span style="opacity:.5">· ${ws.kind === 's3' ? 'S3 · ' + ui.escapeHtml(ws.bucket || '') : 'local'}</span><br>
              <span style="font-size:11.5px">${ws.kind === 's3' ? ui.escapeHtml(ws.endpoint || '') : ui.escapeHtml(ws.local_path || '')}</span></span>
              <span class="v" style="display:flex;gap:6px">
                <button class="btn small" data-edit="${ws.id}">${icons.el('edit')}</button>
                <button class="btn small danger" data-del="${ws.id}">${icons.el('trash')}</button>
              </span></div>`).join('') || '<p class="hint">No workspaces configured.</p>'}
        </div>
        <div style="margin-top:14px"><button class="btn primary" id="ws-add2">${icons.el('plus')} Add workspace</button></div>`;
      body.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => {
        showWorkspaceModal(state.workspaces.find((w) => w.id === b.dataset.edit));
      }));
      body.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => {
        confirmDeleteWorkspace(state.workspaces.find((w) => w.id === b.dataset.del));
      }));
      body.querySelector('#ws-add2').addEventListener('click', () => showWorkspaceModal());
    };

    const renderSecurity = () => {
      const s = state.session;
      body.innerHTML = `
        <div class="kv-list">
          <div class="kv"><span class="k">Locked mode</span><span class="v">${s.locked ? 'ON — login required' : 'off'}</span></div>
          ${s.locked ? `<div class="kv"><span class="k">Signed in as</span><span class="v">${ui.escapeHtml(s.username || '')}</span></div>` : ''}
          <div class="kv"><span class="k">Credentials at rest</span><span class="v">Fernet-encrypted in ${ui.escapeHtml(cacheData.home)}</span></div>
          <div class="kv"><span class="k">API secrets</span><span class="v">always redacted (••••last4)</span></div>
          <div class="kv"><span class="k">Remote workspaces</span><span class="v">read-only by design</span></div>
        </div>
        ${s.locked ? `<div style="margin-top:14px"><button class="btn" id="btn-signout2">${icons.el('logout')} Sign out</button></div>`
          : `<p class="hint" style="margin-top:14px">To protect the app with a login, start it with <code>blob-viewer run --locked</code>
             or <code>blob-viewer serve --locked</code>.</p>`}`;
      body.querySelector('#btn-signout2')?.addEventListener('click', logout);
    };

    const renderTab = (name) => {
      ({ appearance: renderAppearance, cache: renderCache, workspaces: renderWorkspaces, security: renderSecurity }[name] || renderAppearance)();
    };
    content.querySelectorAll('.settings-tabs button').forEach((b) => {
      b.addEventListener('click', () => {
        content.querySelectorAll('.settings-tabs button').forEach((x) => x.classList.remove('active'));
        b.classList.add('active');
        renderTab(b.dataset.tab);
      });
    });
    renderTab(tab);

    const modal = ui.openModal(content);
    content.querySelector('#settings-close').addEventListener('click', () => modal.close());
  }

  // =========================================================================
  // go
  // =========================================================================

  document.addEventListener('DOMContentLoaded', boot);
})();
