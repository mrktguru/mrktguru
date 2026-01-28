export const API = {
    async getSchedule(accountId) {
        const res = await fetch(`/scheduler/accounts/${accountId}/schedule`);
        return await res.json();
    },

    async createSchedule(accountId, name = 'Warmup Schedule') {
        const res = await fetch(`/scheduler/accounts/${accountId}/schedule`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        return await res.json();
    },

    async deleteNode(nodeId) {
        return await fetch(`/scheduler/nodes/${nodeId}`, { method: 'DELETE' });
    },

    async updateNode(nodeId, payload) {
        const res = await fetch(`/scheduler/nodes/${nodeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async createNode(scheduleId, payload) {
        const res = await fetch(`/scheduler/schedules/${scheduleId}/nodes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await res.json();
    },

    async startSchedule(scheduleId) {
        const res = await fetch(`/scheduler/schedules/${scheduleId}/start`, { method: 'POST' });
        return await res.json();
    },

    async pauseSchedule(scheduleId) {
        const res = await fetch(`/scheduler/schedules/${scheduleId}/pause`, { method: 'POST' });
        return await res.json();
    }
};
