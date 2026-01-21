/**
 * Warmup Scheduler JavaScript
 * Handles drag-and-drop calendar, node configuration, and execution
 */

(function () {
    'use strict';

    // Get account ID from data attribute set in HTML
    const schedulerContainer = document.getElementById('scheduler-calendar');
    if (!schedulerContainer) {
        console.warn('Scheduler calendar not found on this page');
        return;
    }

    const schedulerAccountId = parseInt(schedulerContainer.dataset.accountId);
    if (!schedulerAccountId) {
        console.error('Account ID not found in scheduler-calendar data attribute');
        return;
    }

    // Account Data for Pre-filling (passed from HTML data attributes)
    const accountData = {
        bio: schedulerContainer.dataset.bio || '',
        username: schedulerContainer.dataset.username || '',
        first_name: schedulerContainer.dataset.firstName || '',
        last_name: schedulerContainer.dataset.lastName || '',
        photo_url: schedulerContainer.dataset.photoUrl || ''
    };

    let scheduleData = {
        schedule_id: null,
        nodes: []
    };

    let currentNode = null; // Track node being edited
    let currentNodeDay = null;
    let configModal = null;

    // Initialize drag and drop
    document.addEventListener('DOMContentLoaded', function () {
        initDragAndDrop();
        loadSchedule();

        configModal = new bootstrap.Modal(document.getElementById('nodeConfigModal'));

        // Modal Save Handler
        document.getElementById('saveNodeConfigBtn').addEventListener('click', saveConfig);

        // Run Now Handler
        document.getElementById('runNodeNowBtn').addEventListener('click', runNodeNow);

        // Random time toggler
        document.getElementById('isRandomTime').addEventListener('change', function (e) {
            document.querySelector('input[name="execution_time"]').disabled = e.target.checked;
        });

        // Button handlers
        document.getElementById('save-schedule-btn').addEventListener('click', saveSchedule);
        document.getElementById('start-schedule-btn').addEventListener('click', startSchedule);
        document.getElementById('clear-schedule-btn').addEventListener('click', clearSchedule);
    });

    function initDragAndDrop() {
        // Make nodes draggable
        const draggables = document.querySelectorAll('.node-item.draggable');

        draggables.forEach(item => {
            item.addEventListener('dragstart', handleDragStart);
            item.addEventListener('dragend', handleDragEnd);
            item.setAttribute('draggable', 'true');
        });

        // Make day cells droppable
        const dropZones = document.querySelectorAll('.day-cell.droppable');

        dropZones.forEach(zone => {
            zone.addEventListener('dragover', handleDragOver);
            zone.addEventListener('dragleave', handleDragLeave);
            zone.addEventListener('drop', handleDrop);
        });
    }

    let draggedNodeType = null;

    function handleDragStart(e) {
        draggedNodeType = this.dataset.nodeType;
        this.style.opacity = '0.4';
    }

    function handleDragEnd(e) {
        this.style.opacity = '1';
    }

    function handleDragOver(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    }

    function handleDragLeave(e) {
        this.classList.remove('drag-over');
    }

    function handleDrop(e) {
        e.preventDefault();
        this.classList.remove('drag-over');

        const dayNumber = parseInt(this.dataset.day);

        if (draggedNodeType) {
            addNodeToDay(draggedNodeType, dayNumber);
            draggedNodeType = null;
        }
    }

    // Helper to get local time string HH:MM
    function getCurrentTime() {
        const now = new Date();
        return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
    }

    function addNodeToDay(nodeType, dayNumber) {
        // Create node object
        const node = {
            node_type: nodeType,
            day_number: dayNumber,
            execution_time: getCurrentTime(),
            is_random_time: false,
            config: {}
        };

        // Add to schedule data
        scheduleData.nodes.push(node);

        // Render node
        renderNode(node, dayNumber);

        console.log('Added node:', node);

        // Automatically open config
        openNodeConfig(node, dayNumber);
    }

    function renderNode(node, dayNumber) {
        const container = document.getElementById(`day-${dayNumber}-nodes`);

        const nodeEl = document.createElement('div');
        nodeEl.className = 'scheduled-node';
        nodeEl._nodeObj = node;

        updateNodeVisuals(nodeEl, node, dayNumber);

        container.appendChild(nodeEl);
    }

    function updateNodeVisuals(el, node, dayNumber) {
        el.innerHTML = `
            <span class="remove-node" onclick="window.removeSchedulerNode(this, ${dayNumber}, '${node.node_type}')">×</span>
            <strong>${getNodeLabel(node.node_type)}</strong>
            <span class="node-time">${node.is_random_time ? '🎲 Random' : node.execution_time}</span>
            ${getConfigSummary(node)}
        `;

        el.onclick = function (e) {
            if (e.target.className === 'remove-node') return;
            openNodeConfig(node, dayNumber, el);
        };
    }

    function getConfigSummary(node) {
        if (!node.config) return '';
        let summary = [];
        if (node.config.count) summary.push(`${node.config.count}x`);
        if (node.config.channels) summary.push(`${node.config.channels.split(',').length} chs`);
        if (node.config.photo_path) summary.push('📷 set');
        if (node.config.keywords || node.config.links) {
            const kwCount = node.config.keywords ? node.config.keywords.split('\n').filter(l => l.trim()).length : 0;
            const linkCount = node.config.links ? node.config.links.split('\n').filter(l => l.trim()).length : 0;
            if (kwCount > 0) summary.push(`🔍 ${kwCount} kw`);
            if (linkCount > 0) summary.push(`🔗 ${linkCount} links`);
        }
        return summary.length ? `<span class="d-block text-muted small" style="font-size:0.65rem">${summary.join(' • ')}</span>` : '';
    }

    function getNodeLabel(nodeType) {
        const labels = {
            'bio': '👤 Bio',
            'username': '@Username',
            'photo': '📷 Photo',
            'import_contacts': '📞 Import',
            'search_filter': '🔍 Search & Filter',
            'send_message': '💬 Message',
            'subscribe': '📺 Subscribe',
            'visit': '👁️ Visit',
            'idle': '💤 Idle',
            'smart_subscribe': '🔔 Smart Subscribe'
        };
        return labels[nodeType] || nodeType;
    }

    window.removeSchedulerNode = function (el, dayNumber, nodeType) {
        if (event) event.stopPropagation();

        const nodeEl = el.parentElement;

        // Track for deletion if has ID
        if (nodeEl._nodeObj && nodeEl._nodeObj.id) {
            deletedNodeIds.push(nodeEl._nodeObj.id);
        }

        nodeEl.remove();

        // Remove from schedule data
        scheduleData.nodes = scheduleData.nodes.filter(n => n !== nodeEl._nodeObj);
    };

    function openNodeConfig(node, dayNumber, nodeEl = null) {
        currentNode = node;
        currentNodeDay = dayNumber;

        if (!nodeEl) {
            const container = document.getElementById(`day-${dayNumber}-nodes`);
            if (container && container.lastChild && container.lastChild._nodeObj === node) {
                currentNode.el = container.lastChild;
            }
        } else {
            currentNode.el = nodeEl;
        }

        // Fill Form
        const form = document.getElementById('nodeConfigForm');
        form.execution_time.value = node.execution_time;
        form.is_random_time.checked = node.is_random_time;
        form.execution_time.disabled = node.is_random_time;

        renderDynamicFields(node.node_type, node.config);

        configModal.show();
    }

    function renderDynamicFields(type, config) {
        const container = document.getElementById('dynamicFields');
        container.innerHTML = '';
        config = config || {};

        let html = '';

        if (['send_message', 'import_contacts', 'invite'].includes(type)) {
            html += `
                <div class="mb-3">
                    <label class="form-label">Count</label>
                    <input type="number" class="form-control" name="count" value="${config.count || 10}">
                </div>
                <div class="row">
                    <div class="col">
                        <label class="form-label">Min Interval (s)</label>
                        <input type="number" class="form-control" name="interval_min" value="${config.interval_min || 30}">
                    </div>
                    <div class="col">
                        <label class="form-label">Max Interval (s)</label>
                        <input type="number" class="form-control" name="interval_max" value="${config.interval_max || 120}">
                    </div>
                </div>
            `;
        }
        else if (['subscribe', 'visit'].includes(type)) {
            html += `
                <div class="mb-3">
                    <label class="form-label">Target Channels (@username or link)</label>
                    <textarea class="form-control" name="channels" rows="3" placeholder="@channel1, https://t.me/channel2">${config.channels || ''}</textarea>
                    <div class="form-text">Comma separated</div>
                </div>
                <div class="row">
                    <div class="col">
                        <label class="form-label">Count</label>
                        <input type="number" class="form-control" name="count" value="${config.count || 5}">
                    </div>
                    <div class="col">
                        <label class="form-label">Interval (s)</label>
                        <input type="number" class="form-control" name="interval" value="${config.interval || 30}">
                    </div>
                </div>
            `;
        }
        else if (type === 'photo') {
            html += `
                <div class="mb-3">
                    <label class="form-label">Profile Photo</label>
                    <input type="file" class="form-control" id="photoInput">
                    <input type="hidden" name="photo_path" value="${config.photo_path || ''}">
                    <div id="photoPreview" class="mt-2 text-muted small">
                        ${config.photo_path ? 'Current: ' + config.photo_path.split('/').pop() : ''}
                    </div>
                </div>
            `;
        }
        else if (type === 'bio') {
            const defaultBio = config.bio_text || accountData.bio;
            html += `
                <div class="mb-3">
                    <label class="form-label">Bio Text</label>
                    <textarea class="form-control" name="bio_text" rows="3" placeholder="About me">${defaultBio}</textarea>
                </div>
            `;
        }
        else if (type === 'search_filter') {
            html += `
                <div class="mb-3">
                    <label class="form-label">Keywords (one per line)</label>
                    <textarea class="form-control" name="keywords" rows="3" placeholder="Interior Design\nNews NYC\nCrypto Trading">${config.keywords || ''}</textarea>
                    <small class="form-text text-muted">Generic keywords for organic search</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Links (one per line)</label>
                    <textarea class="form-control" name="links" rows="3" placeholder="t.me/example_channel\n@username\nhttps://t.me/another">${config.links || ''}</textarea>
                    <small class="form-text text-muted">Direct channel links or usernames</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Blacklist (comma-separated)</label>
                    <input type="text" class="form-control" name="stopwords" 
                        value="${config.stopwords || 'casino, abuz, dark, scam, porn, xxx, dating, naked'}" 
                        placeholder="casino, scam, porn">
                    <small class="form-text text-muted">Channels containing these words in title will be skipped</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Language</label>
                    <select class="form-select" name="language">
                        <option value="AUTO" ${config.language === 'AUTO' ? 'selected' : ''}>Auto-detect</option>
                        <option value="EN" ${config.language === 'EN' ? 'selected' : ''}>English</option>
                        <option value="RU" ${config.language === 'RU' ? 'selected' : ''}>Russian</option>
                    </select>
                </div>
            `;
        }
        else if (type === 'username') {
            const defaultUser = config.username || accountData.username;
            html += `
                <div class="mb-3">
                    <label class="form-label">Set Username</label>
                    <div class="input-group">
                        <span class="input-group-text">@</span>
                        <input type="text" class="form-control" name="username" value="${defaultUser}">
                    </div>
                </div>
            `;
        }
        else if (type === 'smart_subscribe') {
            html += `
                <div class="alert alert-info small mb-3">
                    <strong>🤖 Smart Subscriber:</strong> Human-like subscription with reading simulation
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Target Entity (Optional)</label>
                    <input type="text" class="form-control" name="target_entity" 
                        value="${config.target_entity || ''}" 
                        placeholder="@channel or leave empty">
                    <small class="form-text text-muted">Your main channel to promote. Leave empty for noise-only mode.</small>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">Random Channels Count</label>
                        <input type="number" class="form-control" name="random_count" 
                            value="${config.random_count || 3}" min="0" max="10">
                        <small class="form-text text-muted">Noise channels from DB</small>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Pool Filter</label>
                        <input type="text" class="form-control" name="pool_filter" 
                            value="${config.pool_filter || ''}" placeholder="e.g. Crypto_Base">
                        <small class="form-text text-muted">Optional: filter by pool name</small>
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>📖 Reading Parameters</h6>
                
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">Posts Min</label>
                        <input type="number" class="form-control" name="posts_limit_min" 
                            value="${config.posts_limit_min || 3}" min="1" max="20">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Posts Max</label>
                        <input type="number" class="form-control" name="posts_limit_max" 
                            value="${config.posts_limit_max || 10}" min="1" max="20">
                    </div>
                </div>
                
                <div class="row mt-2">
                    <div class="col-md-4">
                        <label class="form-label">Comment Chance (%)</label>
                        <input type="number" class="form-control" name="comment_chance" 
                            value="${(config.comment_chance || 0.3) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Media View (%)</label>
                        <input type="number" class="form-control" name="view_media_chance" 
                            value="${(config.view_media_chance || 0.5) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Read Speed</label>
                        <input type="number" class="form-control" name="read_speed_factor" 
                            value="${config.read_speed_factor || 1.0}" min="0.5" max="2.0" step="0.1">
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>🔕 Post-Actions</h6>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="archive_random" 
                                ${config.archive_random !== false ? 'checked' : ''}>
                            <label class="form-check-label">Archive Randoms</label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Mute Target (%)</label>
                        <input type="number" class="form-control form-control-sm" name="mute_target_chance" 
                            value="${(config.mute_target_chance || 0.5) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Mute Randoms (%)</label>
                        <input type="number" class="form-control form-control-sm" name="mute_random_chance" 
                            value="${(config.mute_random_chance || 1.0) * 100}" min="0" max="100">
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>⚙️ Advanced Filters</h6>
                
                <div class="row">
                    <div class="col-md-4">
                        <label class="form-label">Min Participants</label>
                        <input type="number" class="form-control" name="min_participants" 
                            value="${config.min_participants || 100}" min="0">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Dead Days Threshold</label>
                        <input type="number" class="form-control" name="exclude_dead_days" 
                            value="${config.exclude_dead_days || 7}" min="0">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Max Flood Wait (s)</label>
                        <input type="number" class="form-control" name="max_flood_wait_sec" 
                            value="${config.max_flood_wait_sec || 60}" min="10" max="300">
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

        // Attach upload handler for photo
        if (type === 'photo') {
            document.getElementById('photoInput').addEventListener('change', async function (e) {
                if (e.target.files.length > 0) {
                    const formData = new FormData();
                    formData.append('file', e.target.files[0]);

                    try {
                        const btn = document.getElementById('saveNodeConfigBtn');
                        const originalText = btn.innerHTML;
                        btn.disabled = true;
                        btn.innerHTML = 'Uploading...';

                        const resp = await fetch('/scheduler/upload', {
                            method: 'POST',
                            body: formData
                        });
                        const data = await resp.json();

                        if (resp.ok) {
                            document.querySelector('input[name="photo_path"]').value = data.path;
                            document.getElementById('photoPreview').innerText = 'Uploaded: ' + data.filename;
                        } else {
                            alert('Upload failed: ' + data.error);
                        }

                        btn.disabled = false;
                        btn.innerHTML = originalText;
                    } catch (err) {
                        console.error(err);
                        alert('Upload error');
                    }
                }
            });
        }
    }

    async function runNodeNow() {
        if (!currentNode) return;

        if (!confirm('Execute this node IMMEDIATELY?')) return;

        // Grab current config from form
        const form = document.getElementById('nodeConfigForm');
        const formData = new FormData(form);
        const tempConfig = {};
        for (let [key, value] of formData.entries()) {
            if (['execution_time', 'is_random_time'].includes(key)) continue;
            tempConfig[key] = value;
        }

        const payload = {
            node_type: currentNode.node_type,
            config: tempConfig
        };

        // CLOSE MODAL IMMEDIATELY
        configModal.hide();

        // Show running status on node element in calendar
        if (currentNode.el) {
            currentNode.el.classList.add('executing');
            const originalHTML = currentNode.el.innerHTML;
            currentNode.el.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <span class="spinner-border spinner-border-sm text-primary"></span>
                    <strong>${getNodeLabel(currentNode.node_type)}</strong>
                    <span class="badge bg-warning text-dark">Running...</span>
                </div>
            `;

            try {
                const resp = await fetch(`/scheduler/accounts/${schedulerAccountId}/run_node`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();

                if (resp.ok) {
                    // Success
                    currentNode.el.classList.remove('executing');
                    currentNode.el.classList.add('node-success');
                    updateNodeVisuals(currentNode.el, currentNode, currentNodeDay);

                    showToast('✅ Success', `Node executed successfully! ${data.result || data.message || ''}`, 'success');
                } else {
                    // Error
                    currentNode.el.classList.remove('executing');
                    currentNode.el.classList.add('node-error');
                    currentNode.el.innerHTML = originalHTML;

                    showToast('❌ Error', data.error || 'Execution failed', 'danger');
                }
            } catch (err) {
                console.error(err);
                currentNode.el.classList.remove('executing');
                currentNode.el.classList.add('node-error');
                currentNode.el.innerHTML = originalHTML;

                showToast('❌ Error', 'Execution error: ' + err.message, 'danger');
            }
        }
    }

    // Helper function to show Bootstrap toast notifications
    function showToast(title, message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || createToastContainer();

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }

    function saveConfig() {
        if (!currentNode) return;

        const form = document.getElementById('nodeConfigForm');

        // Common
        currentNode.execution_time = form.execution_time.value;
        currentNode.is_random_time = form.is_random_time.checked;

        // Dynamic
        const formData = new FormData(form);
        const newConfig = {};

        for (let [key, value] of formData.entries()) {
            if (['execution_time', 'is_random_time'].includes(key)) continue;

            // Convert percentage fields to decimals for smart_subscribe
            if (currentNode.node_type === 'smart_subscribe' &&
                ['comment_chance', 'view_media_chance', 'mute_target_chance', 'mute_random_chance'].includes(key)) {
                newConfig[key] = parseFloat(value) / 100.0;
            }
            // Convert checkbox to boolean
            else if (key === 'archive_random') {
                newConfig[key] = form.elements[key].checked;
            }
            else {
                newConfig[key] = value;
            }
        }

        currentNode.config = newConfig;

        // Update UI
        if (currentNode.el) {
            updateNodeVisuals(currentNode.el, currentNode, currentNodeDay);
        }

        configModal.hide();
    }

    async function loadSchedule() {
        try {
            const response = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`);
            const data = await response.json();

            if (data.schedule) {
                scheduleData.schedule_id = data.schedule.id;
                scheduleData.nodes = data.nodes || [];

                // Render existing nodes
                data.nodes.forEach(node => {
                    renderNode(node, node.day_number);
                });
            }
        } catch (error) {
            console.error('Error loading schedule:', error);
        }
    }

    let deletedNodeIds = [];

    async function saveSchedule() {
        try {
            // Process deletes first
            for (const id of deletedNodeIds) {
                await fetch(`/scheduler/nodes/${id}`, { method: 'DELETE' });
            }
            deletedNodeIds = [];

            // Create schedule if doesn't exist
            if (!scheduleData.schedule_id) {
                const createResp = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Warmup Schedule' })
                });
                const createData = await createResp.json();
                scheduleData.schedule_id = createData.schedule.id;
            }

            // Save nodes
            for (const node of scheduleData.nodes) {
                if (node.id) {
                    await fetch(`/scheduler/nodes/${node.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(node)
                    });
                } else {
                    const resp = await fetch(`/scheduler/schedules/${scheduleData.schedule_id}/nodes`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(node)
                    });
                    const data = await resp.json();
                    if (data.node) {
                        node.id = data.node.id;
                    }
                }
            }

            showToast('✅ Saved', 'Schedule saved successfully!', 'success');
        } catch (e) {
            console.error(e);
            showToast('❌ Error', 'Error saving: ' + e.message, 'danger');
        }
    }

    async function startSchedule() {
        if (!scheduleData.schedule_id) {
            showToast('⚠️ Warning', 'Please save schedule first', 'warning');
            return;
        }

        if (confirm('Start warmup schedule? This will begin automated execution.')) {
            try {
                const response = await fetch(`/scheduler/schedules/${scheduleData.schedule_id}/start`, {
                    method: 'POST'
                });
                const data = await response.json();
                showToast('✅ Started', 'Schedule started!', 'success');
                setTimeout(() => location.reload(), 1500);
            } catch (error) {
                console.error('Error starting schedule:', error);
                showToast('❌ Error', 'Error starting schedule', 'danger');
            }
        }
    }

    function clearSchedule() {
        if (confirm('Clear all nodes from schedule?')) {
            // Track all for deletion
            scheduleData.nodes.forEach(n => {
                if (n.id) deletedNodeIds.push(n.id);
            });
            scheduleData.nodes = [];
            document.querySelectorAll('.day-nodes').forEach(el => el.innerHTML = '');
        }
    }

})();
