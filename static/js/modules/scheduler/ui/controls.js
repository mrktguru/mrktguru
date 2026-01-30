import { state } from '../state.js';
import { API } from '../api.js';

export function setupPagination(onChangeWeek) {
    document.getElementById('prev-week-btn').addEventListener('click', () => onChangeWeek(-1));
    document.getElementById('next-week-btn').addEventListener('click', () => onChangeWeek(1));
}

export function setupActionButtons(onSave, onClear) {
    document.getElementById('save-schedule-btn').addEventListener('click', () => onSave(false));
    document.getElementById('clear-schedule-btn').addEventListener('click', onClear);
}

export function updateControlButtons() {
    const btn = document.getElementById('start-schedule-btn');
    if (!btn) return;

    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    if (state.scheduleData.status === 'active') {
        newBtn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop';
        newBtn.className = 'btn btn-sm btn-danger';
        newBtn.addEventListener('click', stopScheduleAction);
    } else {
        newBtn.innerHTML = '<i class="bi bi-play-fill"></i> Start';
        newBtn.className = 'btn btn-sm btn-success';
        newBtn.addEventListener('click', startScheduleAction);
    }
}

async function stopScheduleAction() {
    if (!confirm("Stop the schedule?")) return;
    try {
        const res = await API.pauseSchedule(state.scheduleData.schedule_id);
        if (res.error) alert(res.error);
        else {
            alert("Schedule Stopped!");
            window.location.reload();
        }
    } catch (e) {
        console.error(e);
        alert("Error stopping schedule");
    }
}

async function startScheduleAction() {
    if (!state.scheduleData.schedule_id) {
        try {
            const data = await API.createSchedule(state.schedulerAccountId);
            if (data.schedule) state.scheduleData.schedule_id = data.schedule.id;
        } catch (e) { return; }
    }

    try {
        const res = await API.startSchedule(state.scheduleData.schedule_id);
        if (res.error) alert(res.error);
        else {
            alert("Schedule Started!");
            window.location.reload();
        }
    } catch (e) {
        console.error(e);
        alert("Error starting schedule");
    }
}
