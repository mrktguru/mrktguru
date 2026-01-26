/**
 * Warmup Scheduler V2 - Time-Grid Logic
 * Features: Time-Grid (30m slots), Pagination, Resize, Drag-n-Drop (Sidebar + Internal)
 */

(function () {
    'use strict';

    // --- CONFIGURATION ---
    const VERSION = 'v40_fixed_dates';
    console.log(`Scheduler ${VERSION} Loaded`);

    const PIXELS_PER_MINUTE = 1.0; // 1 min = 1px height
    const SLOT_DURATION_MIN = 60; // 60 min slots (1 hour)
    const SLOT_HEIGHT = SLOT_DURATION_MIN * PIXELS_PER_MINUTE; // 60px per slot
    const TOTAL_MINUTES = 24 * 60; // 1440 min
    const GRID_HEIGHT = TOTAL_MINUTES * PIXELS_PER_MINUTE; // 1440px total height
    const DAYS_PER_VIEW = 7; // Show 7 days at a time

    // --- STATE ---
    // createdAtDate: Account creation date (normalized to 00:00)
    let accountCreatedAtDate = null;
    let currentWeekOffset = 0; // Number of weeks away from creation week

    let scheduleData = {
        schedule_id: null,
        nodes: []
    };
    let schedulerAccountId = null;
    let currentNode = null; // Node being configured

    // Account details for pre-filling
    let accountData = { username: '', bio: '' };

    // Cache UI Elements
    let elements = {};
    let configModal = null;

    // --- INITIALIZATION ---
    document.addEventListener('DOMContentLoaded', () => {
        elements = {
            container: document.getElementById('scheduler-calendar'),
            dayHeaderRow: document.getElementById('day-header-row'),
            timeLabelsCol: document.getElementById('time-labels-col'),
            gridBackground: document.getElementById('grid-background'),
            eventsContainer: document.getElementById('events-container'),
            labelWeek: document.getElementById('current-week-label')
        };

        if (!elements.container) return; // Not on scheduler page

        const container = elements.container;
        schedulerAccountId = parseInt(container.dataset.accountId);

        // 1. Read Account Creation Date
        if (container.dataset.createdAt) {
            accountCreatedAtDate = new Date(container.dataset.createdAt);
            accountCreatedAtDate.setHours(0, 0, 0, 0);
        } else {
            // Fallback to today if missing
            accountCreatedAtDate = new Date();
            accountCreatedAtDate.setHours(0, 0, 0, 0);
        }

        // 2. Calculate initial offset to show CURRENT week
        // Grid always starts on MONDAY.
        const now = new Date();
        now.setHours(0, 0, 0, 0);

        // Get Monday of current week
        const currentMonday = getMonday(now);
        // Get Monday of creation week
        const creationMonday = getMonday(accountCreatedAtDate);

        // Difference in weeks
        const diffTime = currentMonday.getTime() - creationMonday.getTime();
        const diffWeeks = Math.floor(diffTime / (1000 * 60 * 60 * 24 * 7));

        currentWeekOffset = diffWeeks;

        configModal = new bootstrap.Modal(document.getElementById('nodeConfigModal'));

        setupControls();
        renderGridStructure();
        loadSchedule(); // fetches nodes from backend
        initDragAndDrop();
    });

    // Helper: Get Monday of the week for a given date
    function getMonday(d) {
        d = new Date(d);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
        return new Date(d.setDate(diff));
    }

    function setupControls() {
        // Pagination
        document.getElementById('prev-week-btn').addEventListener('click', () => changeWeek(-1));
        document.getElementById('next-week-btn').addEventListener('click', () => changeWeek(1));

        // Actions
        document.getElementById('save-schedule-btn').addEventListener('click', saveSchedule);
        document.getElementById('start-schedule-btn').addEventListener('click', startSchedule);
        document.getElementById('clear-schedule-btn').addEventListener('click', clearSchedule);

        // Config Modal
        document.getElementById('saveNodeConfigBtn').addEventListener('click', saveConfig);
        document.getElementById('runNodeNowBtn').addEventListener('click', runNodeNow);

        // Random toggle logic
        document.getElementById('isRandomTime').addEventListener('change', function (e) {
            document.querySelector('input[name="execution_time"]').disabled = e.target.checked;
        });
    }

    function changeWeek(delta) {
        // Allow going back, but visually block days before creation
        currentWeekOffset += delta;
        renderGridStructure();
        renderNodes();
    }

    // --- RENDERING GRID (REWRITTEN) ---
    function renderGridStructure() {
        elements.timeLabelsCol.innerHTML = '';
        elements.gridBackground.innerHTML = '';
        elements.timeLabelsCol.style.height = `${GRID_HEIGHT}px`;

        // Render Time Columns
        for (let i = 0; i < 24; i++) {
            const label = document.createElement('div');
            label.className = 'time-label small text-muted text-end pe-1';
            label.style.height = `${SLOT_HEIGHT}px`;
            label.innerText = `${i.toString().padStart(2, '0')}:00`;
            elements.timeLabelsCol.appendChild(label);
        }

        const now = new Date();
        now.setHours(0, 0, 0, 0);

        // Calculate View Range (Monday - Sunday) based on offset
        const baseMonday = getMonday(accountCreatedAtDate);
        const viewStartMonday = new Date(baseMonday);
        viewStartMonday.setDate(baseMonday.getDate() + (currentWeekOffset * 7));

        // Render Columns
        for (let d = 0; d < DAYS_PER_VIEW; d++) {
            const col = document.createElement('div');
            col.className = 'grid-day-col position-absolute h-100 border-end';
            col.style.width = `${100 / DAYS_PER_VIEW}%`;
            col.style.left = `${(d * 100) / DAYS_PER_VIEW}%`;
            col.dataset.colIndex = d; // 0-6 index in current view (Mon-Sun)

            // Calculate actual date of this column
            const colDate = new Date(viewStartMonday);
            colDate.setDate(viewStartMonday.getDate() + d);
            colDate.setHours(0, 0, 0, 0);

            // Calculate "Account Day Index" (Day 1 = CreatedAt)
            const diffTime = colDate.getTime() - accountCreatedAtDate.getTime();
            const lifeDayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

            // Styling
            if (lifeDayIndex < 1) {
                // Days BEFORE creation
                col.style.backgroundColor = '#e9ecef';
                col.style.backgroundImage = 'linear-gradient(45deg, #dee2e6 25%, transparent 25%, transparent 50%, #dee2e6 50%, #dee2e6 75%, transparent 75%, transparent)';
                col.style.backgroundSize = '10px 10px';
                col.classList.add('day-disabled');
            } else if (colDate.getTime() === now.getTime()) {
                // Today
                col.style.backgroundColor = 'rgba(13, 110, 253, 0.05)';
                col.classList.add('day-today');
            } else if (colDate < now) {
                // Past days
                col.style.backgroundColor = '#f8f9fa';
            }

            // Slots
            for (let i = 0; i < 24; i++) {
                const slot = document.createElement('div');
                slot.className = 'grid-slot border-bottom';
                slot.style.height = `${SLOT_HEIGHT}px`;
                slot.dataset.slotIndex = i;
                col.appendChild(slot);
            }
            elements.gridBackground.appendChild(col);
        }

        renderHeader(viewStartMonday, now);
    }

    function renderHeader(viewStartMonday, todayDate) {
        const viewEnd = new Date(viewStartMonday);
        viewEnd.setDate(viewStartMonday.getDate() + 6);

        elements.labelWeek.innerText = `${viewStartMonday.toLocaleDateString()} - ${viewEnd.toLocaleDateString()}`;

        elements.dayHeaderRow.innerHTML = '';

        for (let i = 0; i < DAYS_PER_VIEW; i++) {
            const d = new Date(viewStartMonday);
            d.setDate(viewStartMonday.getDate() + i);
            d.setHours(0, 0, 0, 0);

            // Life Day Index
            const diffTime = d.getTime() - accountCreatedAtDate.getTime();
            const lifeDayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

            const header = document.createElement('div');
            header.className = 'flex-grow-1 text-center border-end py-1 small fw-bold text-secondary';
            header.style.width = `${100 / DAYS_PER_VIEW}%`;

            const dd = String(d.getDate()).padStart(2, '0');
            const mm = String(d.getMonth() + 1).padStart(2, '0');

            let dayLabel = `<span class="text-muted" style="font-weight:normal;">-</span>`;
            if (lifeDayIndex >= 1) {
                dayLabel = `Day ${lifeDayIndex}`;
            }

            // Today Highlight
            let bgClass = '';
            let textClass = 'text-dark';
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

    // --- RENDERING NODES (REWRITTEN) ---
    function renderNodes() {
        elements.eventsContainer.innerHTML = '';

        // Define current view range
        const baseMonday = getMonday(accountCreatedAtDate);
        const viewStartMonday = new Date(baseMonday);
        viewStartMonday.setDate(baseMonday.getDate() + (currentWeekOffset * 7));

        scheduleData.nodes.forEach(node => {
            if (!node.day_number) return;

            // Calculate Node Date from CreatedAt + DayNumber
            const nodeDate = new Date(accountCreatedAtDate);
            nodeDate.setDate(accountCreatedAtDate.getDate() + (node.day_number - 1));
            nodeDate.setHours(0, 0, 0, 0);

            // Check if falls in current view week
            const diffTime = nodeDate.getTime() - viewStartMonday.getTime();
            const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24)); // 0 = Monday ... 6 = Sunday

            if (diffDays >= 0 && diffDays < 7) {
                // Pass diffDays as the column index (0-6)
                const nodeEl = createNodeElement(node, diffDays);
                elements.eventsContainer.appendChild(nodeEl);
            }
        });
    }

    function createNodeElement(node, colIndex) {
        let timeStr = node.execution_time || '00:00';
        if (!timeStr.includes(':')) timeStr = '00:00';
        const [h, m] = timeStr.split(':').map(Number);
        const startMin = (h * 60) + m;

        // Visual Duration
        let durationMin = 60;
        if (node.config && node.config.duration_minutes) {
            durationMin = parseInt(node.config.duration_minutes);
        }
        node._ui_duration = Math.max(durationMin, 30);

        const topPx = startMin * PIXELS_PER_MINUTE;
        const heightPx = node._ui_duration * PIXELS_PER_MINUTE;
        const widthPercent = 100 / DAYS_PER_VIEW;

        // Left offset based on colIndex (0-6)
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

        // Styling (Colors)
        if (node.status === 'completed') {
            el.style.backgroundColor = '#d1e7dd';
            el.classList.add('node-completed');
        } else if (node.status === 'failed') {
            el.style.backgroundColor = '#f8d7da';
        } else if (node.status === 'running') {
            el.style.backgroundColor = '#fff3cd';
            el.classList.add('node-running');
        } else {
            el.style.backgroundColor = getNodeColor(node.node_type);
        }

        if (node.is_ghost) {
            el.style.cursor = 'default';
            el.setAttribute('draggable', 'false');
            el.style.opacity = '0.8';
        } else {
            el.style.cursor = 'move';
            el.setAttribute('draggable', 'true');
            el.style.pointerEvents = 'auto';
        }
        el._nodeObj = node;

        // Inner Content
        el.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <strong class="text-truncate">${getNodeLabel(node.node_type)}</strong>
                <div class="d-flex gap-1" style="background: rgba(255,255,255,0.5); border-radius: 4px; padding: 0 2px;">
                    <i class="bi bi-gear-fill node-config-btn" style="cursor:pointer; font-size: 10px;" title="Configure"></i>
                    <i class="bi bi-x node-remove-btn" style="cursor:pointer; font-size: 10px; color: #dc3545;" title="Remove"></i>
                </div>
            </div>
            <div class="small text-truncate mt-1">${node.is_random_time ? '🎲' : node.execution_time}</div>
            <div class="resize-handle position-absolute bottom-0 start-0 w-100" style="height:5px; cursor:ns-resize"></div>
        `;

        // Event Listeners
        // Event Listeners
        if (!node.is_ghost) {
            el.addEventListener('dragstart', (e) => {
                e.stopPropagation();
                e.dataTransfer.setData('source', 'internal');
                window._draggedNode = node;
                e.dataTransfer.effectAllowed = 'move';
                el.style.opacity = '0.5';
            });

            // Fix: Double Click
            el.addEventListener('dblclick', (e) => {
                e.preventDefault(); // Prevent text selection
                e.stopPropagation();
                console.log('Double click on node', node);
                openNodeConfig(node);
            });

            // Config Button
            const configBtn = el.querySelector('.node-config-btn');
            if (configBtn) {
                configBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    console.log('Config click on node', node);
                    openNodeConfig(node);
                });
            }

            // Remove Button
            const removeBtn = el.querySelector('.node-remove-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    removeNode(node);
                });
            }

            initResize(el.querySelector('.resize-handle'), node, el);
        }

        el.addEventListener('dragend', () => { el.style.opacity = '1'; window._draggedNode = null; });

        return el;
    }

    // --- DRAG AND DROP (ADJUSTED) ---
    function initDragAndDrop() {
        // Sidebar items
        document.querySelectorAll('.node-item.draggable').forEach(item => {
            item.setAttribute('draggable', 'true');
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('source', 'sidebar');
                e.dataTransfer.setData('nodeType', item.dataset.nodeType);
            });
        });

        // Grid Drop
        elements.gridBackground.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });

        elements.gridBackground.addEventListener('drop', (e) => {
            e.preventDefault();

            // Calculate target slot/column
            const rect = elements.gridBackground.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const colWidth = rect.width / DAYS_PER_VIEW;
            const colIndex = Math.floor(x / colWidth); // 0-6 (Mon-Sun)
            const slotIndex = Math.floor(y / SLOT_HEIGHT); // Hour

            if (colIndex >= 0 && colIndex < DAYS_PER_VIEW && slotIndex >= 0 && slotIndex < 24) {
                // Convert ColIndex -> AccountDayNumber
                const baseMonday = getMonday(accountCreatedAtDate);
                const viewStartMonday = new Date(baseMonday);
                viewStartMonday.setDate(baseMonday.getDate() + (currentWeekOffset * 7));

                const dropDate = new Date(viewStartMonday);
                dropDate.setDate(viewStartMonday.getDate() + colIndex);

                // Check if drop allowed (not before creation)
                const diffTime = dropDate.getTime() - accountCreatedAtDate.getTime();
                const dayNumber = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

                if (dayNumber < 1) {
                    alert("Cannot schedule before account creation date!");
                    return;
                }

                const timeStr = `${slotIndex.toString().padStart(2, '0')}:00`;
                handleDropAction(e, dayNumber, timeStr);
            }
        });
    }

    function handleDropAction(e, dayNumber, timeStr) {
        const source = e.dataTransfer.getData('source');
        if (source === 'sidebar') {
            const nodeType = e.dataTransfer.getData('nodeType');
            if (nodeType) addNode(nodeType, dayNumber, timeStr);
        }
        else if (source === 'internal') {
            if (window._draggedNode) {
                moveNode(window._draggedNode, dayNumber, timeStr);
            }
        }
    }

    // --- EXISTING HELPER FUNCTIONS ---
    function moveNode(node, day, time) {
        node.day_number = day;
        node.execution_time = time;
        node.is_random_time = false;
        renderNodes();
        saveSchedule(true);
    }

    function addNode(type, day, time) {
        const node = {
            node_type: type,
            day_number: day,
            execution_time: time,
            is_random_time: false,
            config: {},
            _ui_duration: 60
        };
        // Defaults
        if (type === 'passive_activity') node.config.duration_minutes = 60;

        scheduleData.nodes.push(node);
        renderNodes();
        saveSchedule(true);
    }

    function removeNode(node) {
        if (!confirm('Delete this node?')) return;
        if (node.id) {
            window._deletedNodeIds = window._deletedNodeIds || [];
            window._deletedNodeIds.push(node.id);
        }
        scheduleData.nodes = scheduleData.nodes.filter(n => n !== node);
        renderNodes();
        saveSchedule(true);
    }

    function getNodeLabel(type) {
        // Simple formatter
        return type.replace(/_/g, ' ').toUpperCase();
    }

    function getNodeColor(type) {
        const colors = {
            'bio': '#e3f2fd', 'username': '#e3f2fd', 'photo': '#e3f2fd',
            'import_contacts': '#fff3cd', 'subscribe': '#d1e7dd', 'visit': '#d1e7dd',
            'smart_subscribe': '#d1e7dd', 'idle': '#f8f9fa', 'passive_activity': '#ffe69c',
            'sync_profile': '#e3f2fd', 'set_2fa': '#f8d7da'
        };
        return colors[type] || '#f8f9fa';
    }

    // --- BACKEND SYNC ---
    async function loadSchedule() {
        try {
            const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`);
            const data = await res.json();
            if (data.schedule) {
                scheduleData.schedule_id = data.schedule.id;
            }
            if (data.nodes) {
                scheduleData.nodes = data.nodes;
            }
            renderNodes();
        } catch (e) {
            console.error(e);
        }
    }

    async function saveSchedule(silent = false) {
        // 1. Ensure Schedule Exists (Lazy Creation)
        if (!scheduleData.schedule_id) {
            try {
                console.log("Creating new schedule...");
                const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Warmup Schedule' })
                });
                const data = await res.json();
                if (data.schedule) {
                    scheduleData.schedule_id = data.schedule.id;
                    console.log("Schedule created with ID:", scheduleData.schedule_id);
                } else {
                    console.error("Failed to create schedule:", data);
                    if (!silent) alert("Error creating schedule: " + (data.error || 'Unknown'));
                    return;
                }
            } catch (e) {
                console.error("Error creating schedule network:", e);
                return;
            }
        }

        // 2. Process Deletions
        if (window._deletedNodeIds && window._deletedNodeIds.length > 0) {
            for (const id of window._deletedNodeIds) {
                try {
                    await fetch(`/scheduler/nodes/${id}`, { method: 'DELETE' });
                } catch (e) { console.error(e); }
            }
            window._deletedNodeIds = [];
        }

        // 3. Process Upserts
        for (const node of scheduleData.nodes) {
            if (node.is_ghost) continue;

            const payload = {
                node_type: node.node_type,
                day_number: node.day_number,
                execution_time: node.execution_time,
                is_random_time: node.is_random_time,
                config: node.config
            };

            try {
                if (node.id) {
                    await fetch(`/scheduler/nodes/${node.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                } else {
                    const res = await fetch(`/scheduler/schedules/${scheduleData.schedule_id}/nodes`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if (data.node) {
                        node.id = data.node.id;
                    }
                }
            } catch (e) {
                console.error("Save error", e);
            }
        }

        if (!silent) {
            console.log('Schedule saved');
        }
    }

    async function startSchedule() {
        // Ensure Schedule Exists before starting
        if (!scheduleData.schedule_id) {
            try {
                const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Warmup Schedule' })
                });
                const data = await res.json();
                if (data.schedule) {
                    scheduleData.schedule_id = data.schedule.id;
                } else {
                    alert("Error creating schedule: " + (data.error || 'Unknown'));
                    return;
                }
            } catch (e) {
                console.error("Error creating schedule network:", e);
                alert("Network error creating schedule");
                return;
            }
        }

        try {
            const res = await fetch(`/scheduler/schedules/${scheduleData.schedule_id}/start`, { method: 'POST' });
            const data = await res.json();
            if (data.error) alert(data.error);
            else {
                alert("Schedule Started!");
                window.location.reload();
            }
        } catch (e) { console.error(e); }
    }

    async function clearSchedule() {
        if (!confirm("Delete entire schedule?")) return;
        if (!scheduleData.schedule_id) return;
        try {
            await fetch(`/scheduler/schedules/${scheduleData.schedule_id}`, { method: 'DELETE' });
            window.location.reload();
        } catch (e) { console.error(e); }
    }

    function openNodeConfig(node) {
        currentNode = node;
        const form = document.getElementById('nodeConfigForm');
        form.reset();

        // Common Fields
        const timeInput = form.elements['execution_time'];
        const randomCheck = form.elements['is_random_time'];

        if (timeInput && randomCheck) {
            if (node.is_random_time) {
                randomCheck.checked = true;
                timeInput.disabled = true;
                timeInput.value = '';
            } else {
                randomCheck.checked = false;
                timeInput.disabled = false;
                timeInput.value = node.execution_time || '';
            }
        }

        // Render Dynamic Fields
        renderDynamicFields(node.node_type, node.config);

        configModal.show();
    }

    function applyFormToNode() {
        if (!currentNode) return;
        const form = document.getElementById('nodeConfigForm');
        const formData = new FormData(form);

        // Common
        currentNode.is_random_time = formData.has('is_random_time');
        currentNode.execution_time = formData.get('execution_time');

        // Config
        currentNode.config = currentNode.config || {};

        // Helper to get ALL inputs from the dynamic container
        const dynamicContainer = document.getElementById('dynamicFields');
        const inputs = dynamicContainer.querySelectorAll('input, select, textarea');

        inputs.forEach(input => {
            const name = input.name;
            if (!name) return;

            if (input.type === 'checkbox') {
                currentNode.config[name] = input.checked;
            } else if (input.type === 'number') {
                if (input.value === '') currentNode.config[name] = null;
                else currentNode.config[name] = parseFloat(input.value);
            } else {
                currentNode.config[name] = input.value;
            }
        });
    }

    async function saveConfig() {
        if (currentNode) {
            applyFormToNode();
            configModal.hide();
            renderNodes();
            await saveSchedule(true);
        }
    }

    async function runNodeNow() {
        if (!currentNode) return;

        // 1. Capture current form state first (config, etc.)
        applyFormToNode();

        // 2. MOVE TO "NOW"
        const now = new Date();
        const startOfDay = new Date(now);
        startOfDay.setHours(0, 0, 0, 0);

        // Calculate Day Index (1-based)
        if (accountCreatedAtDate) {
            const diffTime = startOfDay.getTime() - accountCreatedAtDate.getTime();
            const dayIndex = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
            currentNode.day_number = Math.max(1, dayIndex);
        }

        // Calculate Time HH:MM
        const hh = String(now.getHours()).padStart(2, '0');
        const mm = String(now.getMinutes()).padStart(2, '0');
        currentNode.execution_time = `${hh}:${mm}`;
        currentNode.is_random_time = false;

        // Update UI immediately (so user sees the jump)
        renderNodes();

        // 3. Auto-save to ensure it exists in DB (and we get an ID) and persists the move
        await saveSchedule(true);

        if (!currentNode.id) {
            alert("Could not save node to database. Cannot run.");
            return;
        }

        if (!confirm(`Run this node immediately? (Node moved to Today at ${currentNode.execution_time})`)) return;

        try {
            const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/run_node`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node_id: currentNode.id })
            });
            const data = await res.json();

            if (res.ok) {
                console.log("Started! Task ID: " + data.task_id);
                configModal.hide();
                // Reload to reflect status change if needed, or just let the socket/polling handle it?
                // User asked for calendar update. reload is safe.
                window.location.reload();
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) {
            console.error(e);
            alert("Network error running node");
        }
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

                // Snap to 30 mins (30px)
                const snappedHeight = Math.round(newHeight / 30) * 30;
                if (snappedHeight < 30) return;

                nodeEl.style.height = `${snappedHeight}px`;

                // Update node data temporary
                const newDuration = snappedHeight / PIXELS_PER_MINUTE;
                node._ui_duration = newDuration;
            }

            function onMouseUp() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);

                // Finalize config update
                node.config = node.config || {};
                node.config.duration_minutes = node._ui_duration;

                renderNodes();
                saveSchedule(true);
            }

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
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
            html += `
                <div class="mb-3">
                    <label class="form-label">Bio Text</label>
                    <textarea class="form-control" name="bio_text" rows="3" placeholder="About me">${config.bio_text || ''}</textarea>
                </div>
            `;
        }
        else if (type === 'search_filter') {
            html += `
                <div class="mb-3">
                    <label class="form-label">Keywords</label>
                    <textarea class="form-control" name="keywords" rows="3">${config.keywords || ''}</textarea>
                </div>
                <div class="mb-3">
                    <label class="form-label">Links</label>
                    <textarea class="form-control" name="links" rows="3">${config.links || ''}</textarea>
                </div>
            `;
        }
        else if (type === 'username') {
            html += `
                <div class="mb-3">
                    <label class="form-label">Set Username</label>
                    <div class="input-group">
                        <span class="input-group-text">@</span>
                        <input type="text" class="form-control" name="username" value="${config.username || ''}">
                    </div>
                </div>
            `;
        }
        else if (type === 'sync_profile') {
            html += `<div class="alert alert-info small">Syncs name/bio/photo from Telegram.</div>`;
        }
        else if (type === 'set_2fa') {
            html += `
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" name="remove_password" ${config.remove_password ? 'checked' : ''}>
                    <label class="form-check-label">Remove Password</label>
                </div>
                <div class="mb-3">
                    <label>New Password</label>
                    <input type="text" class="form-control" name="password" value="${config.password || ''}">
                </div>
            `;
        }
        else if (type === 'smart_subscribe') {
            html += `
                <div class="mb-3">
                    <label>Target Entity</label>
                    <input type="text" class="form-control" name="target_entity" value="${config.target_entity || ''}">
                </div>
                <div class="mb-3">
                    <label>Random Count</label>
                    <input type="number" class="form-control" name="random_count" value="${config.random_count || 3}">
                </div>
             `;
        }

        container.innerHTML = html;

        // Re-attach listeners if needed (e.g. for checkbox toggling)
        const scrollCheck = document.getElementById('enableScrollCheck');
        if (scrollCheck) {
            scrollCheck.addEventListener('change', (e) => {
                const opts = document.getElementById('scrollOptions');
                if (opts) opts.classList.toggle('d-none', !e.target.checked);
            });
        }
    }

})();
