/* Blob Viewer — API client */
window.BV = window.BV || {};

BV.api = (() => {
  async function request(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(url, opts);
    if (resp.status === 401 && !url.includes('/auth/login')) {
      document.dispatchEvent(new CustomEvent('bv:auth-required'));
      throw new ApiError('Authentication required', 401);
    }
    let data = null;
    const text = await resp.text();
    if (text) { try { data = JSON.parse(text); } catch { data = { raw: text }; } }
    if (!resp.ok) {
      throw new ApiError((data && data.error) || `HTTP ${resp.status}`, resp.status);
    }
    return data;
  }

  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  const qs = (params) => {
    const u = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, v);
    return u.toString();
  };

  return {
    ApiError,
    session: () => request('GET', '/api/session'),
    login: (username, password, confirmPassword) =>
      request('POST', '/api/auth/login', { username, password, confirm_password: confirmPassword }),
    logout: () => request('POST', '/api/auth/logout'),

    workspaces: () => request('GET', '/api/workspaces'),
    workspace: (id) => request('GET', `/api/workspaces/${id}`),
    createWorkspace: (data) => request('POST', '/api/workspaces', data),
    updateWorkspace: (id, data) => request('PATCH', `/api/workspaces/${id}`, data),
    deleteWorkspace: (id) => request('DELETE', `/api/workspaces/${id}`),
    testWorkspace: (id, secrets) => request('POST', `/api/workspaces/${id}/test`, secrets ? { secrets } : {}),

    objects: (id, prefix) => request('GET', `/api/workspaces/${id}/objects?${qs({ prefix })}`),
    fileInfo: (id, path) => request('GET', `/api/workspaces/${id}/file?${qs({ path })}`),
    open: (id, path) => request('POST', `/api/workspaces/${id}/open`, { path }),
    checkVersions: (id, paths) => request('POST', `/api/workspaces/${id}/check-versions`, { paths }),
    sync: (id, path) => request('POST', `/api/workspaces/${id}/sync`, { path }),
    evict: (id, path) => request('POST', `/api/workspaces/${id}/evict`, { path }),
    search: (id, q, prefix) => request('GET', `/api/workspaces/${id}/search?${qs({ q, prefix })}`),

    writeFile: (id, path, content) => request('PUT', `/api/workspaces/${id}/file`, { path, content }),
    createFolder: (id, path) => request('POST', `/api/workspaces/${id}/folder`, { path }),
    rename: (id, from, to) => request('POST', `/api/workspaces/${id}/rename`, { from, to }),
    deleteFile: (id, path) => request('DELETE', `/api/workspaces/${id}/file?${qs({ path })}`),

    rawUrl: (id, path) => `/api/workspaces/${id}/raw?path=${encodeURIComponent(path)}`,
    downloadUrl: (id, path) => `/api/workspaces/${id}/download?path=${encodeURIComponent(path)}`,

    cache: () => request('GET', '/api/cache'),
    clearCache: (workspaceId) => request('POST', '/api/cache/clear', workspaceId ? { workspace_id: workspaceId } : {}),

    settings: () => request('GET', '/api/settings'),
    saveSettings: (data) => request('PUT', '/api/settings', data),
  };
})();
