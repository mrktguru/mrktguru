// Account Detail Page JavaScript
// This file contains all interactive functionality for the account detail page

// Initialize account ID from template
let accountId;

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
