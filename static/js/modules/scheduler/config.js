import { state } from './state.js';
import { saveSchedule } from './scheduler_service.js';
import { renderNodes } from './ui/nodes.js';
import { API } from './api.js';

export function openNodeConfig(node) {
    state.currentNode = node;
    const form = document.getElementById('nodeConfigForm');
    form.reset();

    const isReadOnly = (node.status === 'completed' || node.status === 'success' || node.is_ghost);

    const saveBtn = document.getElementById('saveNodeConfigBtn');
    const runBtn = document.getElementById('runNodeNowBtn');

    if (isReadOnly) {
        saveBtn.style.display = 'none';
        runBtn.style.display = 'none';
        document.querySelector('.modal-title').innerText = 'Node Details (History)';
    } else {
        saveBtn.style.display = 'inline-block';
        runBtn.style.display = 'inline-block';
        document.querySelector('.modal-title').innerText = 'Configure Node';
    }

    const timeInput = form.elements['execution_time'];
    const randomCheck = form.elements['is_random_time'];

    if (timeInput) timeInput.disabled = isReadOnly;
    if (randomCheck) randomCheck.disabled = isReadOnly;

    if (timeInput && randomCheck && !isReadOnly) {
        if (node.is_random_time) {
            randomCheck.checked = true;
            timeInput.disabled = true;
            timeInput.value = '';
        } else {
            randomCheck.checked = false;
            timeInput.disabled = false;
            timeInput.value = node.execution_time || '';
        }
    } else if (timeInput && isReadOnly) {
        timeInput.value = node.execution_time || '';
        if (randomCheck) randomCheck.checked = !!node.is_random_time;
    }

    renderDynamicFields(node.node_type, node.config);

    if (isReadOnly) {
        const dynamicContainer = document.getElementById('dynamicFields');
        dynamicContainer.querySelectorAll('input, select, textarea').forEach(el => el.disabled = true);
    }

    state.configModal.show();
}

export async function saveConfig() {
    console.log("[Scheduler] saveConfig start");
    try {
        if (state.currentNode) {
            console.log("[Scheduler] Applying form to node:", state.currentNode);
            applyFormToNode();

            console.log("[Scheduler] Hiding modal");
            if (state.configModal) {
                state.configModal.hide();
            } else {
                console.warn("[Scheduler] state.configModal is null, trying manual hide");
                const modalEl = document.getElementById('nodeConfigModal');
                if (modalEl && typeof bootstrap !== 'undefined') {
                    const inst = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                    inst.hide();
                }
            }

            console.log("[Scheduler] Triggering re-render");
            renderNodes();

            console.log("[Scheduler] Triggering background save");
            await saveSchedule(true);
            console.log("[Scheduler] saveConfig complete");
        } else {
            console.warn("[Scheduler] saveConfig called but state.currentNode is null");
        }
    } catch (e) {
        console.error("[Scheduler] Error in saveConfig:", e);
        alert("Error saving configuration: " + e.message);
    }
}

export async function runNodeNow() {
    if (!state.currentNode) return;
    const node = state.currentNode;
    const btn = document.getElementById('runNodeNowBtn');

    // Prevent double clicks
    if (btn) {
        if (btn.disabled) return;
        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';
    }

    applyFormToNode();

    const now = new Date();
    const startOfDay = new Date(now);
    startOfDay.setHours(0, 0, 0, 0);

    if (state.accountCreatedAtDate) {
        const diffTime = startOfDay.getTime() - state.accountCreatedAtDate.getTime();
        const dayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
        node.day_number = Math.max(1, dayIndex);
    }

    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    node.execution_time = `${hh}:${mm}`;
    node.is_random_time = false;

    renderNodes();
    await saveSchedule(true);

    if (!node.id) {
        alert("Could not save node to database. Cannot run.");
        if (btn) { btn.disabled = false; btn.innerHTML = originalText || 'Run Node Now'; }
        return;
    }

    // No confirm needed if we already clicked Run intentionally? 
    // User requested blocking. Let's keep confirm but handle cancel.
    if (!confirm(`Run this node immediately? (Node moved to Today at ${node.execution_time})`)) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Run Node Now'; // Hardcoded restore as originalText variable scope might be tricky if I don't pass it.
            // Actually originalText is in scope.
            btn.innerHTML = originalText || 'Run Node Now';
        }
        return;
    }

    try {
        const res = await fetch(`/scheduler/accounts/${state.schedulerAccountId}/run_node`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_id: node.id })
        });
        const data = await res.json();

        if (res.ok) {
            console.log("Started! Task ID: " + data.task_id);
            state.configModal.hide();
            window.location.reload();
        } else {
            alert("Error: " + data.error);
            if (btn) { btn.disabled = false; btn.innerHTML = originalText || 'Run Node Now'; }
        }
    } catch (e) {
        console.error(e);
        alert("Network error running node");
        if (btn) { btn.disabled = false; btn.innerHTML = originalText || 'Run Node Now'; }
    }
}

function applyFormToNode() {
    if (!state.currentNode) return;
    const form = document.getElementById('nodeConfigForm');
    if (!form) {
        console.error("[Scheduler] nodeConfigForm not found");
        return;
    }

    const node = state.currentNode;

    // Use direct element access for critical fields
    const randomCheck = form.querySelector('[name="is_random_time"]');
    const timeInput = form.querySelector('[name="execution_time"]');

    if (randomCheck) node.is_random_time = randomCheck.checked;
    if (timeInput) node.execution_time = timeInput.value || '00:00';

    console.log(`[Scheduler] applyFormToNode result - time: ${node.execution_time}, random: ${node.is_random_time}`);

    node.config = node.config || {};

    const dynamicContainer = document.getElementById('dynamicFields');
    if (dynamicContainer) {
        const inputs = dynamicContainer.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            const name = input.name;
            if (!name || name === 'execution_time' || name === 'is_random_time') return;

            if (input.type === 'checkbox') {
                node.config[name] = input.checked;
            } else if (input.type === 'number') {
                if (input.value === '') node.config[name] = null;
                else node.config[name] = parseFloat(input.value);
            } else {
                node.config[name] = input.value;
            }
        });
    }

    // Force node to pending if it's currently draft or undefined
    if (!node.status || node.status === 'draft') {
        node.status = 'pending';
        console.log(`[Scheduler] Node ${node.id || 'new'} status set to pending`);
    }

    // Reference safety: ensure the node in the state array is updated too
    // in case state.currentNode is a stale reference from an old refresh
    if (node.id) {
        const index = state.scheduleData.nodes.findIndex(n => n.id === node.id);
        if (index !== -1 && state.scheduleData.nodes[index] !== node) {
            console.warn(`[Scheduler] Stale reference detected for node ${node.id}, updating state array.`);
            state.scheduleData.nodes[index] = node;
        }
    }
}

function renderDynamicFields(type, config) {
    const container = document.getElementById('dynamicFields');
    container.innerHTML = '';
    config = config || {};
    let html = '';

    if (type === 'passive_activity') {
        html += `
            <div class="alert alert-warning small mb-3">
                <strong>🧘 Passive Activity:</strong> Simulates human behavior.
            </div>
            <div class="mb-3">
                <label class="form-label">Total Duration (minutes)</label>
                <input type="number" class="form-control" name="duration_minutes" value="${config.duration_minutes || 60}">
            </div>
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" name="enable_scroll" ${config.enable_scroll ? 'checked' : ''} id="enableScrollCheck">
                <label class="form-check-label" for="enableScrollCheck">Enable Random Scrolling?</label>
            </div>
            <div id="scrollOptions" class="${config.enable_scroll ? '' : 'd-none'}">
                    <div class="row mb-2">
                    <div class="col-md-6"><label>Scroll Count (Min)</label><input type="number" class="form-control" name="scroll_count_min" value="${config.scroll_count_min || 3}"></div>
                    <div class="col-md-6"><label>Scroll Count (Max)</label><input type="number" class="form-control" name="scroll_count_max" value="${config.scroll_count_max || 6}"></div>
                    </div>
                    <div class="row">
                    <div class="col-md-6"><label>Duration Min (s)</label><input type="number" class="form-control" name="scroll_duration_min" value="${config.scroll_duration_min || 30}"></div>
                    <div class="col-md-6"><label>Duration Max (s)</label><input type="number" class="form-control" name="scroll_duration_max" value="${config.scroll_duration_max || 120}"></div>
                    </div>
            </div>
        `;
    }
    // ... Copy rest of logic essentially ...
    else if (['send_message', 'import_contacts', 'invite'].includes(type)) {
        html += `<div class="mb-3"><label>Count</label><input type="number" class="form-control" name="count" value="${config.count || 10}"></div>`;
    }
    else if (['subscribe', 'visit'].includes(type)) {
        html += `<div class="mb-3"><label>Target Channels</label><textarea class="form-control" name="channels" rows="3">${config.channels || ''}</textarea></div>`;
        html += `<div class="mb-3"><label>Count</label><input type="number" class="form-control" name="count" value="${config.count || 5}"></div>`;
    }
    else if (type === 'photo') {
        const currentPath = config.photo_path || '';
        const hasPhoto = currentPath && currentPath.length > 0;
        html += `
            <div class="mb-3">
                <label class="form-label">Profile Photo</label>
                <input type="file" id="photoInput" class="form-control" accept="image/*">
                <input type="hidden" name="photo_path" id="photoPathInput" value="${currentPath}">
                <div id="photoUploadStatus" class="mt-2 small ${hasPhoto ? 'text-success' : 'text-muted'}">
                    ${hasPhoto ? '✅ Photo selected: ' + currentPath.split('/').pop() : 'No photo selected'}
                </div>
                ${hasPhoto ? `<img src="/${currentPath}" class="mt-2 img-thumbnail" style="max-width: 100px; max-height: 100px;" onerror="this.style.display='none'">` : ''}
            </div>
        `;
    }
    else if (type === 'bio') {
        html += `<div class="mb-3"><label class="form-label">Bio Text</label><textarea class="form-control" name="bio_text" rows="3" placeholder="About me">${config.bio_text || ''}</textarea></div>`;
    }
    else if (type === 'search_filter') {
        html += `
            <div class="mb-3"><label class="form-label">Keywords</label><textarea class="form-control" name="keywords" rows="3">${config.keywords || ''}</textarea></div>
            <div class="mb-3"><label class="form-label">Mixed Source List</label><textarea class="form-control" name="links" rows="4">${config.links || ''}</textarea></div>
        `;
    }
    else if (type === 'username') {
        html += `<div class="mb-3"><label class="form-label">Set Username</label><div class="input-group"><span class="input-group-text">@</span><input type="text" class="form-control" name="username" value="${config.username || ''}"></div></div>`;
    }
    else if (type === 'sync_profile') {
        html += `<div class="alert alert-info small">Syncs name/bio/photo from Telegram.</div>`;
    }
    else if (type === 'set_2fa') {
        html += `<div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="remove_password" ${config.remove_password ? 'checked' : ''}><label>Remove Password</label></div><div class="mb-3"><label>New Password</label><input type="text" class="form-control" name="password" value="${config.password || ''}"></div>`;
    }
    else if (type === 'smart_subscribe' || type === 'subscribe') {
        const mode = config.mode || 'auto';
        html += `
            <div class="mb-3">
                <label class="form-label">Mode</label>
                <select class="form-select" name="mode" onchange="window.toggleSubscribeMode(this.value)">
                    <option value="auto" ${mode === 'auto' ? 'selected' : ''}>Auto (Smart Discovery)</option>
                    <option value="manual" ${mode === 'manual' ? 'selected' : ''}>Manual (Select Channels)</option>
                </select>
            </div>
            
            <div id="sub-auto-fields" class="${mode === 'manual' ? 'd-none' : ''}">
                <div class="row g-2 mb-3">
                    <div class="col-6">
                        <label>Count</label>
                        <input type="number" class="form-control" name="count" value="${config.count || 1}" min="1">
                    </div>
                    <div class="col-6">
                        <label>Ignore Old (Days)</label>
                        <input type="number" class="form-control" name="exclude_dead_days" value="${config.exclude_dead_days || 30}" min="0">
                    </div>
                </div>
                <div class="row g-2 mb-3">
                    <div class="col-6">
                        <label>Min Subs</label>
                        <input type="number" class="form-control" name="min_subs" value="${config.min_subs || 0}">
                    </div>
                    <div class="col-6">
                        <label>Max Subs</label>
                        <input type="number" class="form-control" name="max_subs" value="${config.max_subs || 10000000}">
                    </div>
                </div>
            </div>

            <div id="sub-manual-fields" class="${mode === 'auto' ? 'd-none' : ''}">
                <label class="form-label">Select Candidates:</label>
                <div id="manualRequestList" style="max-height: 250px; overflow-y: auto; border: 1px solid #dee2e6; padding: 10px; border-radius: 4px; background: #fff;">
                     <div class="text-center text-muted p-2"><span class="spinner-border spinner-border-sm"></span> Loading candidates...</div>
                </div>
                <!-- Hidden Input to store comma-separated IDs -->
                <input type="text" class="d-none" name="candidate_ids" id="hidden_candidate_ids" value="${config.candidate_ids || ''}">
            </div>

            <hr>
            <h6>Behavior</h6>
            <div class="form-check mb-2">
                <input class="form-check-input" type="checkbox" name="mute_notifications" ${config.mute_notifications !== false ? 'checked' : ''}>
                <label class="form-check-label">Mute Notifications</label>
            </div>
            <div class="row g-2 mb-3">
                 <div class="col-6">
                    <label>Cooldown Min (sec)</label>
                    <input type="number" class="form-control" name="delay_min" value="${config.delay_min || 180}">
                 </div>
                 <div class="col-6">
                    <label>Cooldown Max (sec)</label>
                    <input type="number" class="form-control" name="delay_max" value="${config.delay_max || 600}">
                 </div>
            </div>
        `;

        // Define Window Helpers if not exists
        if (!window.toggleSubscribeMode) {
            window.toggleSubscribeMode = (val) => {
                const auto = document.getElementById('sub-auto-fields');
                const man = document.getElementById('sub-manual-fields');
                if (auto) auto.classList.toggle('d-none', val !== 'auto');
                if (man) man.classList.toggle('d-none', val !== 'manual');

                if (val === 'manual') {
                    if (window.loadManualCandidates) window.loadManualCandidates();
                }
            }
        }

        // Define Loader Function
        // Redefine inside closure to capture 'state'
        window.loadManualCandidates = async () => {
            const list = document.getElementById('manualRequestList');
            if (!list) return;
            if (list.dataset.loaded === 'true') return;

            const accountId = state.schedulerAccountId;
            if (!accountId) {
                list.innerHTML = '<div class="text-danger">Account ID missing</div>';
                return;
            }

            try {
                const res = await fetch(`/accounts/${accountId}/discovered-channels?per_page=100`);
                const data = await res.json();

                if (data.success) {
                    list.innerHTML = '';
                    const input = document.getElementById('hidden_candidate_ids');
                    const existingIds = (input ? input.value : '').split(',').map(s => s.trim());

                    if (data.channels.length === 0) {
                        list.innerHTML = '<div class="text-muted small text-center">No discovered channels found. Run "Search & Filter" first.</div>';
                        return;
                    }

                    data.channels.forEach(ch => {
                        if (ch.status === 'SUBSCRIBED' || ch.status === 'BANNED' || ch.status === 'JOINED') return;

                        const div = document.createElement('div');
                        div.className = 'form-check';
                        // Safe strings
                        const label = (ch.title || ch.username || `ID: ${ch.peer_id}`).replace(/</g, "&lt;");
                        const subText = ch.participants_count ? `${ch.participants_count.toLocaleString()} subs` : '';
                        const info = subText ? `<small class="text-muted ms-1">(${subText})</small>` : '';

                        const checked = existingIds.includes(String(ch.id)) ? 'checked' : '';

                        div.innerHTML = `
                            <input class="form-check-input candidate-check" type="checkbox" value="${ch.id}" id="chk_${ch.id}" ${checked} onchange="window.updateCandidateIds()">
                            <label class="form-check-label text-truncate w-100" for="chk_${ch.id}">
                                ${label} ${info}
                            </label>
                         `;
                        list.appendChild(div);
                    });
                    list.dataset.loaded = 'true';
                } else {
                    list.innerHTML = `<div class=\"text-danger small\">${data.error}</div>`;
                }
            } catch (e) {
                list.innerHTML = '<div class=\"text-danger small\">Connection error</div>';
            }
        };

        window.updateCandidateIds = () => {
            const checks = document.querySelectorAll('.candidate-check:checked');
            const ids = Array.from(checks).map(c => c.value).join(',');
            const input = document.getElementById('hidden_candidate_ids');
            if (input) input.value = ids;
        };

        // Trigger load initial if manual
        if (config.mode === 'manual') {
            setTimeout(window.loadManualCandidates, 100);
        }
    }

    container.innerHTML = html;

    // Photo upload handler
    const photoInput = document.getElementById('photoInput');
    if (photoInput) {
        photoInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const status = document.getElementById('photoUploadStatus');
            const pathInput = document.getElementById('photoPathInput');
            
            status.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Uploading...';
            status.className = 'mt-2 small text-info';
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/scheduler/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error('Upload failed');
                }
                
                const result = await response.json();
                
                if (result.path) {
                    pathInput.value = result.path;
                    status.innerHTML = `✅ Photo uploaded: ${file.name}`;
                    status.className = 'mt-2 small text-success';
                } else {
                    throw new Error(result.error || 'Unknown error');
                }
            } catch (err) {
                console.error('Photo upload error:', err);
                status.innerHTML = `❌ Upload failed: ${err.message}`;
                status.className = 'mt-2 small text-danger';
            }
        });
    }

    const scrollCheck = document.getElementById('enableScrollCheck');
    if (scrollCheck) {
        scrollCheck.addEventListener('change', (e) => {
            const opts = document.getElementById('scrollOptions');
            if (opts) opts.classList.toggle('d-none', !e.target.checked);
        });
    }
}
