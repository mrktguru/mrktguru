import { state } from './state.js';
import { getMonday } from './utils.js';
import { loadSchedule, saveSchedule } from './scheduler_service.js';
import { renderGridStructure } from './ui/grid.js';
import { renderNodes } from './ui/nodes.js';
import { initDragAndDrop } from './interactions.js';
import { saveConfig, runNodeNow } from './config.js';
import { setupPagination, setupActionButtons, updateControlButtons } from './ui/controls.js';
import { API } from './api.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Init Elements Cache
    state.elements = {
        container: document.getElementById('scheduler-calendar'),
        dayHeaderRow: document.getElementById('day-header-row'),
        timeLabelsCol: document.getElementById('time-labels-col'),
        gridBackground: document.getElementById('grid-background'),
        eventsContainer: document.getElementById('events-container'),
        labelWeek: document.getElementById('current-week-label')
    };

    if (!state.elements.container) return; // Not on scheduler page

    state.schedulerAccountId = parseInt(state.elements.container.dataset.accountId);

    // 2. Dates
    if (state.elements.container.dataset.createdAt) {
        state.accountCreatedAtDate = new Date(state.elements.container.dataset.createdAt);
        state.accountCreatedAtDate.setHours(0, 0, 0, 0);
    } else {
        state.accountCreatedAtDate = new Date();
        state.accountCreatedAtDate.setHours(0, 0, 0, 0);
    }

    // 3. Calc Offset (Show Current Week)
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const currentMonday = getMonday(now);
    const creationMonday = getMonday(state.accountCreatedAtDate);
    const diffTime = currentMonday.getTime() - creationMonday.getTime();
    state.currentWeekOffset = Math.floor(diffTime / (1000 * 60 * 60 * 24 * 7));

    // 4. Init Modal
    state.configModal = new bootstrap.Modal(document.getElementById('nodeConfigModal'));

    // 5. Setup Controls
    setupPagination((delta) => {
        state.currentWeekOffset += delta;
        renderGridStructure();
        renderNodes();
    });

    setupActionButtons(saveSchedule, async () => {
        if (!confirm("Delete entire schedule?")) return;
        if (!state.scheduleData.schedule_id) return;
        try {
            await fetch(`/scheduler/schedules/${state.scheduleData.schedule_id}`, { method: 'DELETE' });
            window.location.reload();
        } catch (e) {
            console.error(e);
        }
    });

    // Config Modal Listeners
    const saveCfgBtn = document.getElementById('saveNodeConfigBtn');
    if (saveCfgBtn) saveCfgBtn.addEventListener('click', saveConfig);

    const runNowBtn = document.getElementById('runNodeNowBtn');
    if (runNowBtn) runNowBtn.addEventListener('click', runNodeNow);

    const randTimeCheck = document.getElementById('isRandomTime');
    if (randTimeCheck) {
        randTimeCheck.addEventListener('change', (e) => {
            const input = document.querySelector('input[name="execution_time"]');
            if (input) input.disabled = e.target.checked;
        });
    }

    // 6. Initial Render
    renderGridStructure();
    initDragAndDrop();

    // 7. Load Data
    loadSchedule().then(() => {
        updateControlButtons();
    });

    // 8. Auto Refresh
    setInterval(() => {
        if (!state.isSaving) {
            loadSchedule().then(updateControlButtons);
        } else {
            console.log('[Auto-refresh] Skipped: save in progress');
        }
    }, 10000);

    console.log('Scheduler Module Loaded');
});
