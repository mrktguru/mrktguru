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


// --- Discovered Channels / Subscriptions Logic ---

let selectedChannels = [];

// Search Channels
async function searchChannels() {
    const query = document.getElementById('channel-search-query').value;

    // if (!query) {
    //    alert('Enter a search query');
    //    return;
    // }

    const btn = document.querySelector('button[onclick="searchChannels()"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Searching...';

    try {
        const response = await fetch(`/accounts/${accountId}/warmup/search-channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        const result = await response.json();

        if (result.success) {
            displaySearchResults(result.results);
        } else {
            alert('❌ Error: ' + result.error);
        }
    } catch (e) {
        alert('❌ Connection Error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

function loadAllChannels() {
    document.getElementById('channel-search-query').value = '';
    searchChannels();
}



// Display Search Results
function displaySearchResults(results) {
    const container = document.getElementById('results-list');
    container.innerHTML = '';

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="list-group-item text-muted">No channels found</div>';
        document.getElementById('search-results').style.display = 'block';
        return;
    }

    results.forEach(channel => {
        const item = document.createElement('div');
        item.className = 'list-group-item d-flex justify-content-between align-items-center';
        // Check if already selected to disable button
        const isSelected = selectedChannels.some(sc => sc.username === channel.username);

        item.innerHTML = `
        <div>
            <strong>@${channel.username}</strong>
            <br><small>${channel.title} • ${channel.participants_count.toLocaleString()} members</small>
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary" 
                onclick='addChannel(${JSON.stringify(channel)}, "view_only")' ${isSelected ? 'disabled' : ''}>
                Visit
            </button>
            <button class="btn btn-sm btn-primary" 
                onclick='addChannel(${JSON.stringify(channel)}, "subscribe")' ${isSelected ? 'disabled' : ''}>
                Subscribe
            </button>
        </div>
    `;
        container.appendChild(item);
    });

    document.getElementById('search-results').style.display = 'block';
}

// Add Channel
function addChannel(channel, action = 'view_only') {
    channel.initialAction = action;
    // Avoid duplicates
    if (!selectedChannels.some(sc => sc.username === channel.username)) {
        selectedChannels.push(channel);
        updateChannelsList();

        // Disable buttons in search results immediately
        const buttons = document.querySelectorAll(`button[onclick*='${channel.username}']`);
        buttons.forEach(b => b.disabled = true);
    }
}

// Update Channels List
function updateChannelsList() {
    const container = document.getElementById('channels-list');
    const executeBtn = document.getElementById('execute-channels-btn');
    container.innerHTML = '';

    if (selectedChannels.length === 0) {
        container.innerHTML = '<div class="text-muted small">No channels selected</div>';
        executeBtn.disabled = true;
        document.getElementById('channel-count').textContent = '0';
        return;
    }

    selectedChannels.forEach((channel, index) => {
        const item = document.createElement('div');
        item.className = 'card mb-2 bg-light border';
        item.innerHTML = `
        <div class="card-body p-2">
            <div class="d-flex justify-content-between align-items-center">
                <div class="overflow-hidden me-2">
                    <div class="fw-bold text-truncate">@${channel.username}</div>
                    <small class="text-muted text-truncate d-block">${channel.title}</small>
                </div>
                <div class="d-flex flex-column align-items-end" style="min-width: 140px;">
                    <select class="form-select form-select-sm mb-1" id="action-${index}">
                        <option value="view_only" ${channel.initialAction === 'view_only' ? 'selected' : ''}>Visit (View Only)</option>
                        <option value="subscribe" ${channel.initialAction === 'subscribe' ? 'selected' : ''}>Subscribe</option>
                    </select>
                    <div class="input-group input-group-sm mb-1">
                        <span class="input-group-text">Reads</span>
                        <input type="number" class="form-control" id="read-count-${index}" value="5" min="1" max="20" style="max-width: 60px;">
                    </div>
                    <button class="btn btn-sm btn-outline-danger w-100" onclick="removeChannel(${index})">Remove</button>
                </div>
            </div>
        </div>
    `;
        container.appendChild(item);
    });

    document.getElementById('channel-count').textContent = selectedChannels.length;
    executeBtn.disabled = false;
}

// Remove Channel
function removeChannel(index) {
    selectedChannels.splice(index, 1);
    updateChannelsList();
}

// Execute Channels
async function executeChannels() {
    const executeBtn = document.getElementById('execute-channels-btn');
    const originalText = executeBtn.innerHTML;
    executeBtn.disabled = true;
    executeBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';

    const progressDiv = document.getElementById('progress-channels');
    progressDiv.style.display = 'block';

    // 1. Add channels to backend
    for (let i = 0; i < selectedChannels.length; i++) {
        const channel = selectedChannels[i];
        const action = document.getElementById(`action-${i}`).value;
        const readCount = document.getElementById(`read-count-${i}`).value;

        console.log(`Adding channel: ${channel.username}, action: ${action}, read_count: ${readCount}`);

        try {
            const response = await fetch(`/accounts/${accountId}/warmup/add-channel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_id: channel.id,
                    username: channel.username,
                    title: channel.title,
                    action: action,
                    read_count: parseInt(readCount)
                })
            });

            const result = await response.json();
            if (!result.success) {
                console.error(`Failed to add channel ${channel.username}:`, result.error);
                alert(`Error adding channel ${channel.username}: ${result.error}`);
                executeBtn.disabled = false;
                executeBtn.innerHTML = originalText;
                return;
            }
        } catch (error) {
            console.error(`Exception adding channel ${channel.username}:`, error);
            alert(`Failed to add channel ${channel.username}: ${error.message}`);
            executeBtn.disabled = false;
            executeBtn.innerHTML = originalText;
            return;
        }
    }

    // 2. Execute Batch
    try {
        const response = await fetch(`/accounts/${accountId}/warmup/execute-channels`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ Batch execution started! Check Activity Logs for progress.');
            selectedChannels = [];
            updateChannelsList();
            document.getElementById('search-results').style.display = 'none';
            document.getElementById('channel-search-query').value = '';
        } else {
            alert('❌ Failed to start: ' + result.error);
        }
    } catch (e) {
        alert('❌ Connection Error: ' + e.message);
    } finally {
        executeBtn.disabled = false;
        executeBtn.innerHTML = originalText;
        progressDiv.style.display = 'none';
        // Reload logs if possible, or reload page
        if (typeof loadLogs === 'function') {
            // If we had the logs loader on this page, but we probably don't have the full poller here.
            // Just reload to be safe and simple for the user to see new state
            setTimeout(() => location.reload(), 2000);
        } else {
            setTimeout(() => location.reload(), 2000);
        }
    }
}

