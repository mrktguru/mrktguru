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

    // 2. Dates - ALWAYS use account creation date for Day calculations
    const createdAtRaw = state.elements.container.dataset.createdAt;

    if (createdAtRaw) {
        // Extract just the date part (YYYY-MM-DD) to avoid timezone issues
        const datePart = createdAtRaw.substring(0, 10); // '2026-01-16T20:53:53' -> '2026-01-16'
        const [year, month, day] = datePart.split('-').map(Number);
        // Create date in local timezone at midnight (months are 0-indexed)
        state.accountCreatedAtDate = new Date(year, month - 1, day, 0, 0, 0, 0);
        console.log("[Scheduler] Using account creation date as anchor:", datePart, "->", state.accountCreatedAtDate);
    } else {
        state.accountCreatedAtDate = new Date();
        state.accountCreatedAtDate.setHours(0, 0, 0, 0);
        console.log("[Scheduler] No creation date, using today");
    }

    // 3. Calc Offset (Show Current Week)
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const currentMonday = getMonday(now);
    const creationMonday = getMonday(state.accountCreatedAtDate);
    const diffTime = currentMonday.getTime() - creationMonday.getTime();
    state.currentWeekOffset = Math.round(diffTime / (1000 * 60 * 60 * 24 * 7));

    // 4. Init Modal
    const modalEl = document.getElementById('nodeConfigModal');
    if (modalEl && typeof bootstrap !== 'undefined') {
        state.configModal = new bootstrap.Modal(modalEl);
        modalEl.addEventListener('show.bs.modal', () => { state.isModalOpen = true; });
        modalEl.addEventListener('hidden.bs.modal', () => { state.isModalOpen = false; });
    }

    // 5. Setup Controls
    const timeInput = document.querySelector('input[name="execution_time"]');
    if (timeInput) {
        timeInput.addEventListener('input', (e) => {
            const input = e.target;
            let cursor = input.selectionStart;
            let oldLen = input.value.length;
            let value = input.value.replace(/\D/g, '');

            if (value.length > 4) value = value.slice(0, 4);

            if (value.length > 2) {
                input.value = value.slice(0, 2) + ':' + value.slice(2);
            } else {
                input.value = value;
            }

            // Simple cursor adjustment
            if (input.value.length > oldLen && cursor === 3) cursor++;
            input.setSelectionRange(cursor, cursor);
        });
    }

    setupPagination((delta) => {
        state.currentWeekOffset += delta;
        renderGridStructure();
        renderNodes();
    });

    setupActionButtons(saveSchedule, async () => {
        if (!confirm("Delete entire schedule?")) return;
        if (!state.scheduleData.schedule_id) return;
        try {
            await API.deleteSchedule(state.scheduleData.schedule_id);
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
        if (!state.isSaving && !state.isModalOpen) {
            loadSchedule().then(updateControlButtons);
        } else {
            console.log('[Auto-refresh] Skipped: save in progress or modal open');
        }
    }, 10000);

    console.log('Scheduler Module Loaded');
});
