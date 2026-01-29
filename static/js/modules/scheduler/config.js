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
        return;
    }

    if (!confirm(`Run this node immediately? (Node moved to Today at ${node.execution_time})`)) return;

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
        }
    } catch (e) {
        console.error(e);
        alert("Network error running node");
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
        html += `<div class="mb-3"><label>Photo</label><input type="file" id="photoInput" class="form-control"><input type="hidden" name="photo_path" value="${config.photo_path || ''}"></div>`;
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
                <div class="alert alert-warning small">Enter candidate IDs comma separated (e.g. 12, 45). See "Discovered Channels" for IDs.</div>
                <div class="mb-3">
                    <label>Candidate IDs</label>
                    <input type="text" class="form-control" name="candidate_ids" value="${config.candidate_ids || ''}" placeholder="12, 45, 99">
                </div>
            </div>

            <hr>
            <h6>Behavior</h6>
            <div class="form-check mb-2">
                <input class="form-check-input" type="checkbox" name="mute_notifications" ${config.mute_notifications !== false ? 'checked' : ''}>
                <label class="form-check-label">Mute Notifications</label>
            </div>
            <div class="row g-2 mb-3">
                 <div class="col-6">
                    <label>Delay Min (s)</label>
                    <input type="number" class="form-control" name="delay_min" value="${config.delay_min || 180}">
                 </div>
                 <div class="col-6">
                    <label>Delay Max (s)</label>
                    <input type="number" class="form-control" name="delay_max" value="${config.delay_max || 600}">
                 </div>
            </div>
        `;

        if (!window.toggleSubscribeMode) {
            window.toggleSubscribeMode = (val) => {
                const auto = document.getElementById('sub-auto-fields');
                const man = document.getElementById('sub-manual-fields');
                if (auto) auto.classList.toggle('d-none', val !== 'auto');
                if (man) man.classList.toggle('d-none', val !== 'manual');
            }
        }
    }

    container.innerHTML = html;

    const scrollCheck = document.getElementById('enableScrollCheck');
    if (scrollCheck) {
        scrollCheck.addEventListener('change', (e) => {
            const opts = document.getElementById('scrollOptions');
            if (opts) opts.classList.toggle('d-none', !e.target.checked);
        });
    }
}
