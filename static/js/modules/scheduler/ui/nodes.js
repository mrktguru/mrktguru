import { state } from '../state.js';
import { getMonday, getNodeLabel } from '../utils.js';
import { CONFIG, DAYS_PER_VIEW } from '../constants.js';
import { saveSchedule, removeNode } from '../scheduler_service.js';
import { openNodeConfig } from '../config.js';
import { setDraggedNode } from '../interactions.js';

export function renderNodes() {
    const { elements, scheduleData, accountCreatedAtDate, currentWeekOffset } = state;
    elements.eventsContainer.innerHTML = '';

    const baseMonday = getMonday(accountCreatedAtDate);
    const viewStartMonday = new Date(baseMonday);
    viewStartMonday.setDate(baseMonday.getDate() + (currentWeekOffset * 7));
    viewStartMonday.setHours(0, 0, 0, 0);

    const clusters = {};

    scheduleData.nodes.forEach(node => {
        if (!node.day_number) return;

        const nodeDate = new Date(accountCreatedAtDate);
        nodeDate.setDate(accountCreatedAtDate.getDate() + (node.day_number - 1));
        nodeDate.setHours(0, 0, 0, 0);

        const diffTime = nodeDate.getTime() - viewStartMonday.getTime();
        const colIndex = Math.round(diffTime / (1000 * 60 * 60 * 24));

        if (colIndex >= 0 && colIndex < DAYS_PER_VIEW) {
            const timeStr = node.execution_time || '00:00';
            const key = `${colIndex}_${timeStr}`;

            console.log(`[Scheduler] Node ${node.id} cluster: dayIndex=${colIndex}, time=${timeStr}`);

            if (!clusters[key]) {
                clusters[key] = {
                    colIndex: colIndex,
                    timeStr: timeStr,
                    nodes: []
                };
            }
            clusters[key].nodes.push(node);
        }
    });

    Object.values(clusters).forEach(cluster => {
        cluster.nodes.sort((a, b) => a.id - b.id);

        if (cluster.nodes.length > 1) {
            renderSuperNode(cluster);
        } else {
            const node = cluster.nodes[0];
            const el = createNodeElement(node, cluster.colIndex);
            elements.eventsContainer.appendChild(el);
        }
    });
}

function renderSuperNode(cluster) {
    const { elements } = state;
    let timeStr = cluster.timeStr;
    if (!timeStr.includes(':')) timeStr = '00:00';
    const [h, m] = timeStr.split(':').map(Number);
    const startMin = (h * 60) + m;
    const topPx = startMin * CONFIG.PIXELS_PER_MINUTE;

    const colWidthPercent = 100 / DAYS_PER_VIEW;
    const leftPercent = cluster.colIndex * colWidthPercent;

    const wrapper = document.createElement('div');
    wrapper.className = 'supernode-wrapper';
    wrapper.style.top = `${topPx}px`;
    wrapper.style.left = `${leftPercent}%`;
    wrapper.style.width = `calc(${colWidthPercent}% - 4px)`;
    wrapper.style.marginLeft = '2px';

    wrapper.innerHTML = `
        <div class="supernode-label">
            <span><i class="bi bi-layers-fill"></i> Supernode</span>
            <span>${cluster.nodes.length} actions</span>
        </div>
    `;

    cluster.nodes.forEach((node, index) => {
        const nodeEl = createNodeElement(node, 0); // 0 because inside relative wrapper
        nodeEl.style.position = 'relative';
        nodeEl.style.left = '0';
        nodeEl.style.top = '0';
        nodeEl.style.width = '100%';

        if (index < cluster.nodes.length - 1) {
            nodeEl.style.borderBottom = '1px dashed #ccc';
        }
        wrapper.appendChild(nodeEl);
    });

    elements.eventsContainer.appendChild(wrapper);
}

function createNodeElement(node, colIndex) {
    let timeStr = node.execution_time || '00:00';
    if (!timeStr.includes(':')) timeStr = '00:00';
    const [h, m] = timeStr.split(':').map(Number);
    const startMin = (h * 60) + m;

    let durationMin = 60;
    if (node.config && node.config.duration_minutes) {
        durationMin = parseInt(node.config.duration_minutes);
    }
    node._ui_duration = Math.max(durationMin, 30);

    const topPx = startMin * CONFIG.PIXELS_PER_MINUTE;
    const heightPx = node._ui_duration * CONFIG.PIXELS_PER_MINUTE;
    const widthPercent = 100 / DAYS_PER_VIEW;
    const leftPercent = colIndex * widthPercent;

    const el = document.createElement('div');
    el.className = 'scheduled-node position-absolute rounded shadow-sm p-1';
    el.style.top = `${topPx}px`;
    el.style.left = `${leftPercent}%`;
    el.style.width = `${widthPercent}%`;
    el.style.height = `${heightPx}px`;
    el.style.fontSize = '10px';
    el.style.lineHeight = '1.1';
    el.style.zIndex = 20;

    if (node.status === 'completed' || node.status === 'success') {
        el.style.backgroundColor = '#e9ecef';
        el.classList.add('node-completed');
    } else if (node.status === 'running' || node.status === 'processing') {
        el.style.backgroundColor = '#cfe2ff';
        el.classList.add('node-running');
        el.style.animation = 'pulse 2s infinite';
    } else if (node.status === 'pending') {
        el.style.backgroundColor = '#d1e7dd';
        el.classList.add('node-ready');
    } else {
        el.style.backgroundColor = '#fff3cd';
        el.classList.add('node-draft');
    }

    const isLocked = (node.is_ghost || node.status === 'completed' || node.status === 'success' || node.status === 'running');

    if (isLocked) {
        el.style.cursor = 'default';
        el.setAttribute('draggable', 'false');
        el.style.opacity = '0.9';
    } else {
        el.style.cursor = 'move';
        el.setAttribute('draggable', 'true');
        el.style.pointerEvents = 'auto';
    }
    el._nodeObj = node;

    const isReady = node.status === 'pending';
    el.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <strong class="text-truncate">${getNodeLabel(node.node_type)}</strong>
            <div class="d-flex gap-1" style="background: rgba(255,255,255,0.5); border-radius: 4px; padding: 0 2px;">
                ${isReady ? '<i class="bi bi-check-circle-fill text-success" title="Ready" style="font-size: 10px;"></i>' : ''}
                <i class="bi bi-gear-fill node-config-btn" style="cursor:pointer; font-size: 10px;" title="View Details"></i>
                ${!isLocked ? '<i class="bi bi-x node-remove-btn" style="cursor:pointer; font-size: 10px; color: #dc3545;" title="Remove"></i>' : ''}
            </div>
        </div>
        <div class="d-flex justify-content-between align-items-center mt-1">
            <div class="small text-truncate">${node.is_random_time ? '🎲' : node.execution_time}</div>
            <div class="small text-muted" style="font-size: 0.7em; opacity: 0.7;">${node.ordinal_id ? '#' + node.ordinal_id : 'new'}</div>
        </div>
        ${!isLocked ? '<div class="resize-handle position-absolute bottom-0 start-0 w-100" style="height:5px; cursor:ns-resize"></div>' : ''}
    `;

    if (!node.is_ghost) {
        if (!isLocked) {
            el.addEventListener('dragstart', (e) => {
                e.stopPropagation();
                e.dataTransfer.setData('source', 'internal');
                setDraggedNode(node);
                e.dataTransfer.effectAllowed = 'move';
                el.style.opacity = '0.5';
            });
            el.addEventListener('dragend', () => {
                el.style.opacity = '1';
                setDraggedNode(null);
            });

            const resizeHandle = el.querySelector('.resize-handle');
            if (resizeHandle) initResize(resizeHandle, node, el);
        }

        el.addEventListener('dblclick', (e) => {
            e.preventDefault();
            e.stopPropagation();
            openNodeConfig(node);
        });

        const configBtn = el.querySelector('.node-config-btn');
        if (configBtn) configBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openNodeConfig(node);
        });

        const removeBtn = el.querySelector('.node-remove-btn');
        if (removeBtn) removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeNode(node);
        });
    }

    return el;
}

function initResize(handle, node, nodeEl) {
    handle.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        e.preventDefault();

        const startY = e.clientY;
        const startHeight = parseFloat(getComputedStyle(nodeEl).height);

        function onMouseMove(moveEvent) {
            const deltaY = moveEvent.clientY - startY;
            let newHeight = startHeight + deltaY;
            const snappedHeight = Math.round(newHeight / 30) * 30;
            if (snappedHeight < 30) return;

            nodeEl.style.height = `${snappedHeight}px`;
            const newDuration = snappedHeight / CONFIG.PIXELS_PER_MINUTE;
            node._ui_duration = newDuration;
        }

        function onMouseUp() {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);

            node.config = node.config || {};
            node.config.duration_minutes = node._ui_duration;

            renderNodes();
            saveSchedule(true);
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}
