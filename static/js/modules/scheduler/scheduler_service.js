import { API } from './api.js';
import { state } from './state.js';
import { renderNodes } from './ui/nodes.js';

export async function loadSchedule() {
    try {
        if (!state.schedulerAccountId) return;
        const data = await API.getSchedule(state.schedulerAccountId);

        if (data.schedule) {
            state.scheduleData.schedule_id = data.schedule.id;
            state.scheduleData.status = data.schedule.status;
            // updateControlButtons(); // TODO: Add callback or trigger
        }
        if (data.nodes) {
            state.scheduleData.nodes = data.nodes;
        }
        renderNodes();
    } catch (e) {
        console.error("Load Schedule Error", e);
    }
}

export async function saveSchedule(silent = false) {
    if (state.isSaving) {
        console.warn("Save in progress...");
        // Simple polling or just ignore (debounce preferred in real world)
        return;
    }

    state.isSaving = true;
    try {
        await _internalSaveSchedule(silent);
    } catch (e) {
        console.error("Save error:", e);
    } finally {
        state.isSaving = false;
    }
}

async function _internalSaveSchedule(silent) {
    // 1. Ensure Schedule Exists
    if (!state.scheduleData.schedule_id) {
        try {
            const data = await API.createSchedule(state.schedulerAccountId);
            if (data.schedule) {
                state.scheduleData.schedule_id = data.schedule.id;
            } else {
                if (!silent) alert("Error creating schedule: " + (data.error || 'Unknown'));
                return;
            }
        } catch (e) { return; }
    }

    // 2. Process Deletions
    if (state.deletedNodeIds.length > 0) {
        for (const id of state.deletedNodeIds) {
            await API.deleteNode(id);
        }
        state.deletedNodeIds = [];
    }

    // 3. Process Upserts
    for (const node of state.scheduleData.nodes) {
        if (node.is_ghost) continue;

        const payload = {
            node_type: node.node_type,
            day_number: node.day_number,
            execution_time: node.execution_time,
            is_random_time: node.is_random_time,
            config: node.config,
            status: node.status
        };

        try {
            if (node.id) {
                await API.updateNode(node.id, payload);
            } else {
                const data = await API.createNode(state.scheduleData.schedule_id, payload);
                if (data.node) node.id = data.node.id;
            }
        } catch (e) { console.error(e); }
    }

    if (!silent) console.log('Schedule saved');
}

export function addNode(type, day, time) {
    const node = {
        node_type: type,
        day_number: day,
        execution_time: time,
        is_random_time: false,
        config: {},
        _ui_duration: 60,
        status: 'draft'
    };
    if (type === 'passive_activity') node.config.duration_minutes = 60;

    state.scheduleData.nodes.push(node);
    renderNodes();
    saveSchedule(true);
}

export function moveNode(node, day, time) {
    node.day_number = day;
    node.execution_time = time;
    node.is_random_time = false;
    renderNodes();
    saveSchedule(true);
}

export function removeNode(node) {
    if (!confirm('Delete this node?')) return;
    if (node.id) {
        state.deletedNodeIds.push(node.id);
    }
    state.scheduleData.nodes = state.scheduleData.nodes.filter(n => n !== node);
    renderNodes();
    saveSchedule(true);
}
