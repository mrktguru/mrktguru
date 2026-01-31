import { CONFIG, DAYS_PER_VIEW } from '../constants.js';
import { getMonday } from '../utils.js';
import { state } from '../state.js';

export function renderGridStructure() {
    const { elements } = state;
    if (!elements.timeLabelsCol || !elements.gridBackground) return;

    elements.timeLabelsCol.innerHTML = '';
    elements.gridBackground.innerHTML = '';
    elements.timeLabelsCol.style.height = `${CONFIG.GRID_HEIGHT}px`;

    // Render Time Columns
    for (let i = 0; i < 24; i++) {
        const label = document.createElement('div');
        label.className = 'time-label small text-muted text-end pe-1';
        label.style.height = `${CONFIG.SLOT_HEIGHT}px`;
        label.innerText = `${i.toString().padStart(2, '0')}:00`;
        elements.timeLabelsCol.appendChild(label);
    }

    const now = new Date();
    now.setHours(0, 0, 0, 0);

    // Calculate View Range
    const baseMonday = getMonday(state.accountCreatedAtDate);
    const viewStartMonday = new Date(baseMonday);
    viewStartMonday.setDate(baseMonday.getDate() + (state.currentWeekOffset * 7));

    // Render Columns
    for (let d = 0; d < DAYS_PER_VIEW; d++) {
        const col = document.createElement('div');
        col.className = 'grid-day-col position-absolute h-100 border-end';
        col.style.width = `${100 / DAYS_PER_VIEW}%`;
        col.style.left = `${(d * 100) / DAYS_PER_VIEW}%`;
        col.dataset.colIndex = d;

        const colDate = new Date(viewStartMonday);
        colDate.setDate(viewStartMonday.getDate() + d);
        colDate.setHours(0, 0, 0, 0);

        const diffTime = colDate.getTime() - state.accountCreatedAtDate.getTime();
        const lifeDayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

        // Days before account creation (before Day 1) - striped pattern
        if (lifeDayIndex < 1) {
            col.style.background = 'repeating-linear-gradient(45deg, #e9ecef, #e9ecef 10px, #d0d0d0 10px, #d0d0d0 20px)';
            col.classList.add('day-before-creation');
            col.style.opacity = '0.7';
        }
        // Past days (before today but after account creation) - dimmed out
        else if (colDate < now) {
            col.style.backgroundColor = '#e9ecef';
            col.classList.add('day-past');
            col.style.opacity = '0.6';
        } else if (colDate.getTime() === now.getTime()) {
            // Today - highlighted
            col.style.backgroundColor = 'rgba(13, 110, 253, 0.1)';
            col.classList.add('day-today');
        }

        // Slots
        for (let i = 0; i < 24; i++) {
            const slot = document.createElement('div');
            slot.className = 'grid-slot border-bottom';
            slot.style.height = `${CONFIG.SLOT_HEIGHT}px`;
            slot.dataset.slotIndex = i;
            col.appendChild(slot);
        }
        elements.gridBackground.appendChild(col);
    }

    renderHeader(viewStartMonday, now);
}

function renderHeader(viewStartMonday, todayDate) {
    const { elements } = state;
    const viewEnd = new Date(viewStartMonday);
    viewEnd.setDate(viewStartMonday.getDate() + 6);

    elements.labelWeek.innerText = `${viewStartMonday.toLocaleDateString()} - ${viewEnd.toLocaleDateString()}`;
    elements.dayHeaderRow.innerHTML = '';

    for (let i = 0; i < DAYS_PER_VIEW; i++) {
        const d = new Date(viewStartMonday);
        d.setDate(viewStartMonday.getDate() + i);
        d.setHours(0, 0, 0, 0);

        const diffTime = d.getTime() - state.accountCreatedAtDate.getTime();
        const lifeDayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

        const header = document.createElement('div');
        header.className = 'flex-grow-1 text-center border-end py-1 small fw-bold text-secondary';
        header.style.width = `${100 / DAYS_PER_VIEW}%`;

        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');

        let dayLabel = `<span class="text-muted" style="font-weight:normal;">-</span>`;
        if (lifeDayIndex >= 1) dayLabel = `Day ${lifeDayIndex}`;

        let bgClass = '', textClass = 'text-dark';
        if (d.getTime() === todayDate.getTime()) {
            bgClass = 'bg-primary';
            textClass = 'text-white';
        }

        header.innerHTML = `
            <div class="${bgClass} ${textClass} rounded-top" style="margin: -4px -1px 0;">
                <div style="font-size: 1.1em;">${dd}.${mm}</div>
                <div style="font-size: 0.85em; opacity: 0.9;">${dayLabel}</div>
            </div>
        `;
        elements.dayHeaderRow.appendChild(header);
    }
}
