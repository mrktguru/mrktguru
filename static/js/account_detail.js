// Account Detail Page JavaScript
// This file contains all interactive functionality for the account detail page

// accountId is initialized in the template inline script

// Proxy IP refresh functionality
function refreshProxyIP(proxyId) {
    const btn = document.getElementById('refresh-ip-btn');
    const ipSpan = document.getElementById('proxy-ip');
    const originalText = btn.innerHTML;

    // Disable button and show loading
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i> Checking...';

    // Call test endpoint
    fetch(`/proxies/${proxyId}/test`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update IP display
                ipSpan.textContent = data.ip;
                ipSpan.classList.add('text-success', 'fw-bold');
                setTimeout(() => {
                    ipSpan.classList.remove('text-success', 'fw-bold');
                }, 2000);

                // Show success message
                const alert = document.createElement('div');
                alert.className = 'alert alert-success alert-dismissible fade show mt-2';
                alert.innerHTML = `
                <strong>IP Updated!</strong> New IP: ${data.ip}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
                ipSpan.parentElement.appendChild(alert);
                setTimeout(() => alert.remove(), 3000);
            } else {
                throw new Error(data.error || 'Failed to check IP');
            }
        })
        .catch(error => {
            // Show error
            const alert = document.createElement('div');
            alert.className = 'alert alert-danger alert-dismissible fade show mt-2';
            alert.innerHTML = `
            <strong>Error!</strong> ${error.message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
            ipSpan.parentElement.appendChild(alert);
            setTimeout(() => alert.remove(), 5000);
        })
        .finally(() => {
            // Re-enable button
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
}

// Sync Profile Logic
function syncProfile() {
    if (!confirm('Start full profile sync? This behaves like a human checking their own profile (opening settings, scrolling). Takes ~5-10s.')) {
        return;
    }

    const btn = document.getElementById('sync-btn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Syncing...';

    fetch(`/accounts/${accountId}/sync-from-telegram`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Reload to show new data
                location.reload();
            } else {
                alert('❌ Sync Error: ' + data.error);
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        })
        .catch(err => {
            alert('❌ Network Error: ' + err.message);
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
}

// Sessions Management Logic
function loadSessions() {
    console.log('loadSessions called, accountId:', accountId);
    const container = document.getElementById('sessions-container');
    const loading = document.getElementById('sessions-loading');
    const listDiv = document.getElementById('sessions-list');
    const btn = container.querySelector('button');

    btn.classList.add('d-none');
    loading.classList.remove('d-none');
    listDiv.classList.add('d-none');

    console.log('Fetching sessions from:', `/accounts/${accountId}/sessions`);
    fetch(`/accounts/${accountId}/sessions`)
        .then(res => {
            console.log('Response status:', res.status);
            return res.json();
        })
        .then(data => {
            console.log('Sessions data received:', data);
            loading.classList.add('d-none');
            btn.classList.remove('d-none'); // Show button again (to reload)
            btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh Sessions';

            if (data.success) {
                console.log('Rendering', data.sessions.length, 'sessions');
                // No more localStorage caching - force fresh data
                // localStorage.setItem(`sessions_${accountId}`, JSON.stringify(data.sessions));
                renderSessions(data.sessions);
                listDiv.classList.remove('d-none');
            } else {
                console.error('Error from server:', data.error);
                alert('Error loading sessions: ' + data.error);
            }
        })
        .catch(err => {
            console.error('Network error:', err);
            loading.classList.add('d-none');
            btn.classList.remove('d-none');
            alert('Network error: ' + err.message);
        });
}

function renderSessions(sessions) {
    const tbody = document.getElementById('sessions-table-body');
    tbody.innerHTML = '';

    sessions.forEach(s => {
        const isCurrent = s.current;
        const row = document.createElement('tr');
        row.className = isCurrent ? 'table-success' : '';

        row.innerHTML = `
            <td>
                <div class="fw-bold">${s.device_model}</div>
                <small class="text-muted">${s.app_name} ${s.app_version}</small>
            </td>
            <td>
                <div>${s.country}</div>
                <small class="text-muted">${s.ip}</small>
            </td>
            <td>
                <small title="Created: ${s.date_created}">${s.date_active.split('T')[0]}</small>
            </td>
            <td>
                ${isCurrent ?
                '<span class="badge bg-success">Current</span>' :
                `<button class="btn btn-xs btn-outline-danger" onclick="terminateSession('${s.hash}')" title="Terminate">
                        <i class="bi bi-x"></i>
                    </button>`
            }
            </td>
        `;
        tbody.appendChild(row);
    });
}

function terminateSession(hash) {
    if (!confirm('Terminate this session? (Human emulation ~2-4s)')) return;
    performTermination(hash, false);
}

function terminateAllSessions() {
    if (!confirm('Terminate ALL other sessions? (Human emulation ~3-6s)')) return;
    performTermination(null, true);
}

function performTermination(hash, isAll) {
    const formData = new FormData();
    if (hash) formData.append('session_hash', hash);
    if (isAll) formData.append('terminate_all', 'true');

    fetch(`/accounts/${accountId}/sessions/terminate`, {
        method: 'POST',
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Session(s) terminated successfully');
                loadSessions(); // Reload list
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(err => alert('Network error: ' + err.message));
}

// Restore sessions from localStorage on page load
document.addEventListener('DOMContentLoaded', function () {
    if (!accountId) return;

    // Do NOT load from cache automatically. User must click "Load Sessions" or we could auto-load.
    // But currently UI flow is "Load Sessions" button.

    // Clear old cache if exists to prevent confusion
    localStorage.removeItem(`sessions_${accountId}`);

    const container = document.getElementById('sessions-container');
    // Ensure button is ready to load fresh data
    const btn = document.getElementById('load-sessions-btn');
    if (btn) {
        btn.innerHTML = '<i class="bi bi-download"></i> Load Active Sessions';
    }
});


// --- Discovered Channels Logic (Simple View) ---

let currentDiscoveredPage = 1;

async function loadDiscoveredChannels(page = 1) {
    const container = document.getElementById('discovered-channels-container');
    const pagination = document.getElementById('discovered-pagination');
    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');
    const pageSpan = document.getElementById('current-page');

    // Only show loader if first load or manual refresh
    if (!container.innerHTML.trim() || page === 1) {
        container.innerHTML = `
            <div class="text-center p-3 text-muted">
                <span class="spinner-border spinner-border-sm"></span> Loading...
            </div>`;
    }

    try {
        const response = await fetch(`/accounts/${accountId}/discovered-channels?page=${page}&per_page=10`);
        const result = await response.json();

        if (result.success) {
            currentDiscoveredPage = page;
            renderDiscoveredChannels(result.channels);

            // Setup Pagination
            if (result.total > 10) {
                pagination.style.display = 'flex';
                pagination.style.setProperty('display', 'flex', 'important'); // Force override
                pageSpan.innerText = page;

                prevBtn.disabled = page <= 1;
                prevBtn.onclick = () => loadDiscoveredChannels(page - 1);

                nextBtn.disabled = !result.has_more;
                nextBtn.onclick = () => loadDiscoveredChannels(page + 1);
            } else {
                pagination.style.display = 'none';
            }
        } else {
            container.innerHTML = `<div class="p-3 text-danger text-center">Failed to load channels</div>`;
        }
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div class="p-3 text-danger text-center">Connection error</div>`;
    }
}

function renderDiscoveredChannels(channels) {
    const container = document.getElementById('discovered-channels-container');
    container.innerHTML = '';

    if (!channels || channels.length === 0) {
        container.innerHTML = '<div class="p-3 text-muted text-center">No channels discovered yet. Run "Search & Filter" node.</div>';
        return;
    }

    channels.forEach(channel => {
        const item = document.createElement('div');
        item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';

        // Correctly handle missing/null titles
        const safeTitle = channel.title ? channel.title : (channel.username ? channel.username : 'Unknown');
        const safeUsername = channel.username ? `@${channel.username}` : `ID: ${channel.peer_id}`;

        let icon = channel.type === 'CHANNEL' ? '📢' : '👥';

        // Date formatting 24h
        let visitTime = 'N/A';
        if (channel.last_visit_ts) {
            const date = new Date(channel.last_visit_ts + 'Z');
            visitTime = date.toLocaleDateString('en-GB') + ' ' +
                date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
        }

        // Link logic
        let linkHTML = '';
        if (channel.username) {
            linkHTML = `<a href="https://t.me/${channel.username}" target="_blank" class="fw-bold text-decoration-none">${safeTitle}</a>`;
        } else {
            linkHTML = `<span class="fw-bold">${safeTitle}</span>`;
        }

        item.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <span class="fs-4 text-secondary">${icon}</span>
                <div>
                    <div>${linkHTML}</div>
                    <div class="small text-muted" style="font-size: 0.8rem">
                        ${safeUsername} | ${channel.participants_count ? channel.participants_count.toLocaleString() + ' subs' : 'N/A'}
                    </div>
                </div>
            </div>
            <div class="text-end d-flex flex-column align-items-end">
                <div class="mb-1">
                     <span class="badge bg-secondary">${channel.origin || 'UNKNOWN'}</span>
                     <button class="btn btn-sm text-danger border-0 p-0 ms-2" onclick="deleteDiscoveredChannel(${channel.id}, '${safeUsername}')" title="Remove from list">
                        <i class="bi bi-trash"></i>
                     </button>
                </div>
                <div class="small text-muted" style="font-size: 0.75rem">
                    <i class="bi bi-clock"></i> ${visitTime}
                </div>
            </div>
        `;
        container.appendChild(item);
    });
}

async function deleteDiscoveredChannel(channelId, name) {
    if (!confirm(`Delete ${name} from discovered list?`)) return;

    try {
        const response = await fetch(`/accounts/${accountId}/discovered-channels/${channelId}`, { method: 'DELETE' });
        const res = await response.json();

        if (res.success) {
            loadDiscoveredChannels(currentDiscoveredPage); // Refresh current page
        } else {
            alert('Failed to delete: ' + res.error);
        }
    } catch (e) {
        alert('Connection error');
    }
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    // Only trigger if the container exists (detail page)
    if (document.getElementById('discovered-channels-container')) {
        loadDiscoveredChannels(1);
    }
});

