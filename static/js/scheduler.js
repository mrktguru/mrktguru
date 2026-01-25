/**
 * Warmup Scheduler V2 - Time-Grid Logic
 * Features: Time-Grid (30m slots), Pagination, Resize, Drag-n-Drop (Sidebar + Internal)
 */

(function () {
    'use strict';

    // --- CONFIGURATION ---
    const VERSION = 'v38';
    console.log(`Scheduler ${VERSION} Loaded`);

    const PIXELS_PER_MINUTE = 1.0; // 1 min = 1px height
    const SLOT_DURATION_MIN = 60; // 60 min slots (1 hour)
    const SLOT_HEIGHT = SLOT_DURATION_MIN * PIXELS_PER_MINUTE; // 60px per slot
    const TOTAL_MINUTES = 24 * 60; // 1440 min
    const GRID_HEIGHT = TOTAL_MINUTES * PIXELS_PER_MINUTE; // 1440px total height
    const DAYS_PER_VIEW = 7; // Show 7 days at a time

    // --- STATE ---
    let currentWeekOffset = 0; // 0 = Days 1-7, 1 = Days 8-14
    let scheduleData = {
        schedule_id: null,
        nodes: []
    };
    let schedulerAccountId = null;
    let currentNode = null; // Node being configured

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

        configModal = new bootstrap.Modal(document.getElementById('nodeConfigModal'));

        setupControls();
        renderGridStructure();
        loadSchedule();
        initDragAndDrop();
    });

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
        const newOffset = currentWeekOffset + delta;
        if (newOffset < 0) return; // Can't go before week 1
        currentWeekOffset = newOffset;
        renderHeader();
        renderNodes();
    }

    // --- RENDERING GRID ---
    function renderGridStructure() {
        // 1. Render Time Labels (00:00 - 23:00)
        elements.timeLabelsCol.innerHTML = '';
        elements.timeLabelsCol.style.height = `${GRID_HEIGHT}px`;

        for (let i = 0; i < 24; i++) { // 24 slots of 60 mins
            const label = document.createElement('div');
            label.className = 'time-label small text-muted text-end pe-1';
            label.style.height = `${SLOT_HEIGHT}px`;
            label.style.borderBottom = '1px solid transparent'; // visual spacer
            label.style.fontSize = '12px';
            label.style.lineHeight = '1';
            label.style.paddingTop = '2px';

            // Calculate time string
            const hour = i;
            label.innerText = `${hour.toString().padStart(2, '0')}:00`;

            elements.timeLabelsCol.appendChild(label);
        }

        // 2. Render Grid Background (Columns & Rows)
        elements.gridBackground.innerHTML = '';

        // Vertical Day Columns
        for (let d = 0; d < DAYS_PER_VIEW; d++) {
            const col = document.createElement('div');
            col.className = 'grid-day-col position-absolute h-100 border-end';
            col.style.width = `${100 / DAYS_PER_VIEW}%`;
            col.style.left = `${(d * 100) / DAYS_PER_VIEW}%`;
            col.dataset.dayIndex = d; // 0-6 index in current view

            // Horizontal Slot Lines
            for (let i = 0; i < 24; i++) {
                const slot = document.createElement('div');
                slot.className = 'grid-slot border-bottom';
                slot.style.height = `${SLOT_HEIGHT}px`;
                slot.style.boxSizing = 'border-box';
                // Dataset for drop targeting
                slot.dataset.slotIndex = i;
                col.appendChild(slot);
            }

            elements.gridBackground.appendChild(col);
        }

        renderHeader();
    }

    function renderHeader() {
        const startDay = (currentWeekOffset * 7) + 1;
        const endDay = startDay + 6;
        elements.labelWeek.innerText = `Week ${currentWeekOffset + 1} (Days ${startDay}-${endDay})`;

        elements.dayHeaderRow.innerHTML = '';
        for (let i = 0; i < DAYS_PER_VIEW; i++) {
            const dayNum = startDay + i;
            const header = document.createElement('div');
            header.className = 'flex-grow-1 text-center border-end py-1 small fw-bold text-secondary';
            header.style.width = `${100 / DAYS_PER_VIEW}%`;
            header.innerText = `Day ${dayNum}`;
            elements.dayHeaderRow.appendChild(header);
        }
    }

    // --- RENDERING NODES ---
    function renderNodes() {
        elements.eventsContainer.innerHTML = '';
        const startDay = (currentWeekOffset * 7) + 1;
        const endDay = startDay + 6;

        const visibleNodes = scheduleData.nodes.filter(n => n.day_number >= startDay && n.day_number <= endDay);

        visibleNodes.forEach(node => {
            const nodeEl = createNodeElement(node, startDay);
            node.el = nodeEl;
            elements.eventsContainer.appendChild(nodeEl);
        });
    }

    function createNodeElement(node, viewStartDay) {
        // Calculate Position
        const dayIndex = node.day_number - viewStartDay; // 0-6

        let timeStr = node.execution_time || '00:00';
        if (!timeStr.includes(':')) timeStr = '00:00';

        const [h, m] = timeStr.split(':').map(Number);
        const startMin = (h * 60) + m;

        let durationMin = 60; // default 1h
        // Try to get duration from config or specific node types
        if (node.config && node.config.duration_minutes) {
            durationMin = parseInt(node.config.duration_minutes);
        } else if (node.node_type === 'passive_activity' || node.node_type === 'idle') {
            durationMin = node._ui_duration || 60;
        } else {
            durationMin = node._ui_duration || 60;
        }
        node._ui_duration = Math.max(durationMin, 60); // Minimum 1h visual

        const topPx = startMin * PIXELS_PER_MINUTE;
        const heightPx = node._ui_duration * PIXELS_PER_MINUTE;
        const widthPercent = 100 / DAYS_PER_VIEW;
        const leftPercent = dayIndex * widthPercent;

        const el = document.createElement('div');
        el.className = 'scheduled-node position-absolute rounded shadow-sm p-1';
        el.style.top = `${topPx}px`;
        el.style.left = `${leftPercent}%`;
        el.style.width = `${widthPercent}%`;
        el.style.height = `${heightPx}px`;
        el.style.fontSize = '10px';
        el.style.lineHeight = '1.1';
        el.style.overflow = 'hidden';
        el.style.zIndex = 20;

        // Status Colors
        if (node.status === 'completed') {
            el.style.backgroundColor = '#d1e7dd'; // Green ish
            el.style.border = '1px solid #badbcc';
            el.classList.add('node-completed');
        } else if (node.status === 'failed') {
            el.style.backgroundColor = '#f8d7da'; // Red ish
            el.style.border = '1px solid #f5c2c7';
        } else if (node.status === 'skipped') {
            el.style.backgroundColor = '#e2e3e5'; // Gray
            el.style.opacity = '0.7';
        } else if (node.status === 'running') {
            el.style.backgroundColor = '#fff3cd'; // Yellow
            el.style.border = '1px solid #ffecb5';
            el.classList.add('node-running'); // for animation
        } else {
            el.style.backgroundColor = getNodeColor(node.node_type);
            el.style.border = '1px solid rgba(0,0,0,0.1)';
        }

        el.style.cursor = 'move';
        el.style.pointerEvents = 'auto';

        el._nodeObj = node; // Link data

        // Internal Drag Handlers
        el.setAttribute('draggable', 'true');
        el.addEventListener('dragstart', (e) => {
            e.stopPropagation();
            e.dataTransfer.setData('source', 'internal');
            // Store node reference globally for this drag session
            window._draggedNode = node;
            e.dataTransfer.effectAllowed = 'move';
            el.style.opacity = '0.5';
        });

        el.addEventListener('dragend', () => {
            el.style.opacity = '1';
            window._draggedNode = null;
        });

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

        // Click Handlers
        const configBtn = el.querySelector('.node-config-btn');
        const removeBtn = el.querySelector('.node-remove-btn');

        configBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // prevent drag or other bubble
            openNodeConfig(node);
        });

        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeNode(node);
        });

        // Double click to config
        el.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            openNodeConfig(node);
        });

        // Resize Logic
        const handle = el.querySelector('.resize-handle');
        initResize(handle, node, el);

        return el;
    }

    function getNodeColor(type) {
        const colors = {
            'bio': '#e3f2fd',
            'username': '#e3f2fd',
            'photo': '#e3f2fd',
            'import_contacts': '#fff3cd',
            'subscribe': '#d1e7dd',
            'visit': '#d1e7dd',
            'smart_subscribe': '#d1e7dd',
            'idle': '#f8f9fa',
            'passive_activity': '#ffe69c' // Gold/Coffee color
        };
        return colors[type] || '#f8f9fa';
    }

    // --- DRAG AND DROP ---
    function initDragAndDrop() {
        // Sidebar items
        const sidebarItems = document.querySelectorAll('.node-item.draggable');

        sidebarItems.forEach(item => {
            item.setAttribute('draggable', 'true');
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('source', 'sidebar');
                e.dataTransfer.setData('nodeType', item.dataset.nodeType);
            });
        });

        // Grid Background is the drop zone
        elements.gridBackground.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });

        elements.gridBackground.addEventListener('drop', (e) => {
            e.preventDefault();

            // Determine Drop Target
            // Easiest is closest .grid-slot if dropped directly element
            let slotEl = e.target.closest('.grid-slot');
            let dayNumber = null;
            let timeStr = null;

            if (slotEl) {
                // Perfect hit on slot
                const slotIdx = parseInt(slotEl.dataset.slotIndex);
                const colEl = slotEl.parentElement;
                const colIdx = parseInt(colEl.dataset.dayIndex);

                dayNumber = (currentWeekOffset * 7) + 1 + colIdx;
                dayNumber = (currentWeekOffset * 7) + 1 + colIdx;
                const h = slotIdx; // 1 slot = 1 hour
                const m = 0;
                timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;

            } else {
                // Missed a slot element (e.g. hit border, or dropped on margin). 
                // Calculate from coordinates relative to gridBackground
                const rect = elements.gridBackground.getBoundingClientRect();
                const x = e.clientX - rect.left;

                // e.clientY relative to viewport. rect.top relative to viewport.
                // So y = e.clientY - rect.top is Y relative to top-left of gridBackground.
                // This works even if scrolled, because rect.top shifts with scroll.
                const y = e.clientY - rect.top;

                const colWidth = rect.width / DAYS_PER_VIEW;
                const colIndex = Math.floor(x / colWidth);
                const slotIndex = Math.floor(y / SLOT_HEIGHT);

                if (colIndex >= 0 && colIndex < DAYS_PER_VIEW && slotIndex >= 0 && slotIndex < 24) {
                    dayNumber = (currentWeekOffset * 7) + 1 + colIndex;
                    const h = slotIndex; // 1 slot = 1 hour
                    const m = 0;
                    timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
                }
            }

            if (dayNumber !== null && timeStr !== null) {
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
            config: {},
            _ui_duration: 60 // Default 60 min
        };
        // Auto-configure defaults
        if (type === 'passive_activity') {
            node.config.duration_minutes = 60;
            node._ui_duration = 60;
        }

        scheduleData.nodes.push(node);
        renderNodes();

        // No longer auto-open config
        // openNodeConfig(node);
        saveSchedule(true);
    }

    function removeNode(node) {
        if (!confirm('Delete this node?')) return;

        // Track ID for backend deletion
        if (node.id) {
            // Need a list to track deletes. Global var?
            window._deletedNodeIds = window._deletedNodeIds || [];
            window._deletedNodeIds.push(node.id);
        }

        scheduleData.nodes = scheduleData.nodes.filter(n => n !== node);
        renderNodes();
        saveSchedule(true);
    }

    // --- RESIZE LOGIC ---
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
                const snappedHeight = Math.round(newHeight / SLOT_HEIGHT) * SLOT_HEIGHT;
                if (snappedHeight < SLOT_HEIGHT) return; // Min 30 mins

                nodeEl.style.height = `${snappedHeight}px`;

                // Update node data temporary
                const newDuration = snappedHeight / PIXELS_PER_MINUTE;
                node._ui_duration = newDuration;
            }

            function onMouseUp() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);

                // Finalize config update
                if (node.node_type === 'passive_activity' || node.node_type === 'idle') {
                    node.config = node.config || {};
                    node.config.duration_minutes = node._ui_duration;
                }
                // Re-render to clean up styles/snap
                renderNodes();
                saveSchedule(true);
            }

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
    }

    // --- CONFIG MODAL & API ---
    // (Reuse existing config logic but cleaner)
    function openNodeConfig(node) {
        currentNode = node;
        const form = document.getElementById('nodeConfigForm');
        form.execution_time.value = node.execution_time;
        form.is_random_time.checked = node.is_random_time;
        form.execution_time.disabled = node.is_random_time;

        renderDynamicFields(node.node_type, node.config);
        configModal.show();
    }

    // Reuse existing renderDynamicFields from previous version (it was good)
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
                    <input type="number" class="form-control" name="duration_minutes" value="${config.duration_minutes || node._ui_duration || 60}">
                </div>
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" name="enable_scroll" ${config.enable_scroll ? 'checked' : ''} id="enableScrollCheck">
                    <label class="form-check-label" for="enableScrollCheck">Enable Random Scrolling?</label>
                </div>
                <div id="scrollOptions" class="${config.enable_scroll ? '' : 'd-none'}">
                     <!-- Min/Max Inputs -->
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
            const defaultBio = config.bio_text || accountData.bio;
            html += `
                <div class="mb-3">
                    <label class="form-label">Bio Text</label>
                    <textarea class="form-control" name="bio_text" rows="3" placeholder="About me">${defaultBio}</textarea>
                </div>
            `;
        }
        else if (type === 'search_filter') {
            html += `
                <div class="mb-3">
                    <label class="form-label">Keywords (one per line)</label>
                    <textarea class="form-control" name="keywords" rows="3" placeholder="Interior Design\nNews NYC\nCrypto Trading">${config.keywords || ''}</textarea>
                    <small class="form-text text-muted">Generic keywords for organic search</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Links (one per line)</label>
                    <textarea class="form-control" name="links" rows="3" placeholder="t.me/example_channel\n@username\nhttps://t.me/another">${config.links || ''}</textarea>
                    <small class="form-text text-muted">Direct channel links or usernames</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Blacklist (comma-separated)</label>
                    <input type="text" class="form-control" name="stopwords" 
                        value="${config.stopwords || 'casino, abuz, dark, scam, porn, xxx, dating, naked'}" 
                        placeholder="casino, scam, porn">
                    <small class="form-text text-muted">Channels containing these words in title will be skipped</small>
                </div>
                <div class="mb-3">
                    <label class="form-label">Language</label>
                    <select class="form-select" name="language">
                        <option value="AUTO" ${config.language === 'AUTO' ? 'selected' : ''}>Auto-detect</option>
                        <option value="EN" ${config.language === 'EN' ? 'selected' : ''}>English</option>
                        <option value="RU" ${config.language === 'RU' ? 'selected' : ''}>Russian</option>
                    </select>
                </div>
            `;
        }
        else if (type === 'username') {
            const defaultUser = config.username || accountData.username;
            html += `
                <div class="mb-3">
                    <label class="form-label">Set Username</label>
                    <div class="input-group">
                        <span class="input-group-text">@</span>
                        <input type="text" class="form-control" name="username" value="${defaultUser}">
                    </div>
                </div>
            `;
        }
        else if (type === 'smart_subscribe') {
            html += `
                <div class="alert alert-info small mb-3">
                    <strong>🤖 Smart Subscriber:</strong> Human-like subscription with reading simulation
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Target Entity (Optional)</label>
                    <input type="text" class="form-control" name="target_entity" 
                        value="${config.target_entity || ''}" 
                        placeholder="@channel or leave empty">
                    <small class="form-text text-muted">Your main channel to promote. Leave empty for noise-only mode.</small>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">Random Channels Count</label>
                        <input type="number" class="form-control" name="random_count" 
                            value="${config.random_count || 3}" min="0" max="10">
                        <small class="form-text text-muted">Noise channels from DB</small>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Pool Filter</label>
                        <input type="text" class="form-control" name="pool_filter" 
                            value="${config.pool_filter || ''}" placeholder="e.g. Crypto_Base">
                        <small class="form-text text-muted">Optional: filter by pool name</small>
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>📖 Reading Parameters</h6>
                
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">Posts Min</label>
                        <input type="number" class="form-control" name="posts_limit_min" 
                            value="${config.posts_limit_min || 3}" min="1" max="20">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Posts Max</label>
                        <input type="number" class="form-control" name="posts_limit_max" 
                            value="${config.posts_limit_max || 10}" min="1" max="20">
                    </div>
                </div>
                
                <div class="row mt-2">
                    <div class="col-md-4">
                        <label class="form-label">Comment Chance (%)</label>
                        <input type="number" class="form-control" name="comment_chance" 
                            value="${(config.comment_chance || 0.3) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Media View (%)</label>
                        <input type="number" class="form-control" name="view_media_chance" 
                            value="${(config.view_media_chance || 0.5) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Read Speed</label>
                        <input type="number" class="form-control" name="read_speed_factor" 
                            value="${config.read_speed_factor || 1.0}" min="0.5" max="2.0" step="0.1">
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>🔕 Post-Actions</h6>
                
                <div class="row">
                    <div class="col-md-4">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="archive_random" 
                                ${config.archive_random !== false ? 'checked' : ''}>
                            <label class="form-check-label">Archive Randoms</label>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Mute Target (%)</label>
                        <input type="number" class="form-control form-control-sm" name="mute_target_chance" 
                            value="${(config.mute_target_chance || 0.5) * 100}" min="0" max="100">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small">Mute Randoms (%)</label>
                        <input type="number" class="form-control form-control-sm" name="mute_random_chance" 
                            value="${(config.mute_random_chance || 1.0) * 100}" min="0" max="100">
                    </div>
                </div>
                
                <hr class="my-3">
                <h6>⚙️ Advanced Filters</h6>
                
                <div class="row">
                    <div class="col-md-4">
                        <label class="form-label">Min Participants</label>
                        <input type="number" class="form-control" name="min_participants" 
                            value="${config.min_participants || 100}" min="0">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Dead Days Threshold</label>
                        <input type="number" class="form-control" name="exclude_dead_days" 
                            value="${config.exclude_dead_days || 7}" min="0">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Max Flood Wait (s)</label>
                        <input type="number" class="form-control" name="max_flood_wait_sec" 
                            value="${config.max_flood_wait_sec || 60}" min="10" max="300">
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

        // Listeners for dynamic fields
        if (type === 'passive_activity') {
            const cb = document.getElementById('enableScrollCheck');
            if (cb) cb.addEventListener('change', e => document.getElementById('scrollOptions').classList.toggle('d-none', !e.target.checked));
        }
        if (type === 'photo') {
            const phInput = document.getElementById('photoInput');
            if (phInput) {
                phInput.addEventListener('change', async (e) => {
                    const f = e.target.files[0];
                    if (!f) return;
                    const fd = new FormData(); fd.append('file', f);
                    try {
                        const res = await fetch('/scheduler/upload', { method: 'POST', body: fd });
                        const d = await res.json();
                        if (res.ok) document.querySelector('input[name="photo_path"]').value = d.path;
                    } catch (e) { console.error(e); }
                });
            }
        }
    }

    function saveConfig() {
        if (!currentNode) return;
        const form = document.getElementById('nodeConfigForm');

        currentNode.execution_time = form.execution_time.value;
        currentNode.is_random_time = form.is_random_time.checked;

        const fd = new FormData(form);
        const newConf = {};
        for (let [k, v] of fd.entries()) {
            if (k === 'execution_time' || k === 'is_random_time') continue;
            if (k === 'enable_scroll') newConf[k] = form.elements[k].checked;
            else newConf[k] = v;
        }
        currentNode.config = newConf;

        // Update duration if changed in form
        if (newConf.duration_minutes) currentNode._ui_duration = parseInt(newConf.duration_minutes);

        configModal.hide();
        renderNodes();
        saveSchedule(true);
    }

    // --- API ACTIONS ---
    async function loadSchedule() {
        try {
            const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/status`);
            const text = await res.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (e) {
                console.error('Server returned invalid JSON:', text.substring(0, 200));
                return;
            }

            if (data.schedule) {
                scheduleData = data; // includes status_counts
                if (!scheduleData.nodes) scheduleData.nodes = [];

                // Init ui_duration
                scheduleData.nodes.forEach(n => {
                    if (n.config && n.config.duration_minutes) n._ui_duration = parseInt(n.config.duration_minutes);
                    else n._ui_duration = 60;
                    n._ui_duration = Math.max(n._ui_duration, 60);
                });

                renderNodes();
                updateControlsState();
            }
        } catch (e) {
            console.error(e);
        }
    }

    function updateControlsState() {
        const startBtn = document.getElementById('start-schedule-btn');
        const headerTitle = document.querySelector('.card-header h5') || document.querySelector('h3, h4, h5');

        // Remove existing pause/badge
        const existingPause = document.getElementById('pause-schedule-btn');
        if (existingPause) existingPause.remove();

        const statusBadge = document.getElementById('schedule-status-badge');
        if (statusBadge) statusBadge.remove();

        if (!scheduleData.schedule) return;

        const isRunning = scheduleData.schedule.status === 'active';

        // Badge
        if (headerTitle) {
            const badge = document.createElement('span');
            badge.id = 'schedule-status-badge';
            badge.className = `badge ms-2 ${isRunning ? 'bg-success' : 'bg-secondary'}`;
            badge.innerText = isRunning ? 'RUNNING ▶' : 'STOPPED ⏹';
            headerTitle.appendChild(badge);
        }

        if (isRunning) {
            startBtn.classList.add('d-none');

            // Create Pause Button
            const pauseBtn = document.createElement('button');
            pauseBtn.id = 'pause-schedule-btn';
            pauseBtn.className = 'btn btn-warning btn-sm';
            pauseBtn.innerHTML = '<i class="bi bi-pause-fill"></i> Pause';
            pauseBtn.onclick = pauseSchedule;

            startBtn.parentNode.insertBefore(pauseBtn, startBtn);
        } else {
            startBtn.classList.remove('d-none');
        }
    }

    async function pauseSchedule() {
        if (!scheduleData.schedule || !scheduleData.schedule.id) return;
        if (!confirm('Pause execution?')) return;

        try {
            const res = await fetch(`/scheduler/schedules/${scheduleData.schedule.id}/pause`, { method: 'POST' });
            if (res.ok) {
                showToast('⏸ Paused', 'Schedule logic paused.', 'warning');
                loadSchedule();
            } else {
                const d = await res.json();
                showToast('❌ Error', d.error, 'danger');
            }
        } catch (e) {
            console.error(e);
        }
    }

    async function saveSchedule(silent = false) {
        try {
            // 1. Delete removed
            const deleted = window._deletedNodeIds || [];
            if (deleted.length > 0) {
                for (const id of deleted) {
                    await fetch(`/scheduler/nodes/${id}`, { method: 'DELETE' });
                }
                window._deletedNodeIds = [];
            }

            // 2. Create Schedule if needed
            if (!scheduleData.schedule || !scheduleData.schedule.id) {
                const res = await fetch(`/scheduler/accounts/${schedulerAccountId}/schedule`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: 'Warmup Schedule' })
                });

                let d;
                try {
                    const text = await res.text();
                    d = JSON.parse(text);
                } catch (e) {
                    throw new Error(`Server Error (${res.status}): Invalid response`);
                }

                if (res.ok) {
                    scheduleData.schedule = d.schedule;
                    scheduleData.schedule_id = d.schedule.id;
                } else if (d.error && d.error.includes('exists')) {
                    // It exists but we missing state. Fetch it WITHOUT overwriting nodes
                    const getRes = await fetch(`/scheduler/accounts/${schedulerAccountId}/status`);
                    try {
                        const t = await getRes.text();
                        const getData = JSON.parse(t);
                        if (getData.schedule) {
                            scheduleData.schedule = getData.schedule;
                            scheduleData.schedule_id = getData.schedule.id;
                        } else {
                            throw new Error('Could not recover existing schedule ID');
                        }
                    } catch (e) {
                        throw new Error('Could not recover existing schedule (invalid json)');
                    }
                } else {
                    throw new Error(d.error || 'Failed to create schedule');
                }
            }

            // 3. Save/Update Nodes
            const scheduleId = scheduleData.schedule_id || (scheduleData.schedule ? scheduleData.schedule.id : null);
            if (!scheduleId) throw new Error('Schedule ID is missing after creation/recovery.');

            for (const node of scheduleData.nodes) {
                const method = node.id ? 'PUT' : 'POST';
                const url = node.id ? `/scheduler/nodes/${node.id}` : `/scheduler/schedules/${scheduleId}/nodes`;

                // If node has temporary props, clean them? No, backend ignores unknown fields.
                const res = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(node)
                });

                const text = await res.text();
                try {
                    const d = JSON.parse(text);
                    if (!res.ok) throw new Error(d.error || 'Request failed');
                    if (d.node) node.id = d.node.id;
                } catch (e) {
                    console.error('JSON Parse Error:', text);
                    if (!silent) showToast('❌ Error', `Failed to save node: ${text.substring(0, 100)}`, 'danger');
                    return false; // Partial failure
                }
            }
            if (!silent) showToast('✅ Saved', 'Schedule saved successfully!', 'success');
            return true; // Success

        } catch (e) {
            console.error(e);
            if (!silent) showToast('❌ Error', 'Save failed: ' + e.message, 'danger');
            return false; // Failure
        }
    }


    async function startSchedule() {
        // Ensure we rely on scheduleData.schedule.id
        const sId = scheduleData.schedule ? scheduleData.schedule.id : scheduleData.schedule_id;

        if (!sId) {
            // AUTO SAFE before start
            await saveSchedule();
            if (!scheduleData.schedule_id) return; // Still failed
        }

        if (!confirm('Start execution?')) return;

        const finalId = scheduleData.schedule ? scheduleData.schedule.id : scheduleData.schedule_id;
        try {
            const res = await fetch(`/scheduler/schedules/${finalId}/start`, { method: 'POST' });
            const d = await res.json();
            if (res.ok) {
                showToast('🚀 Started', 'Warmup started!', 'success');
                loadSchedule();
            } else {
                showToast('❌ Error', d.error, 'danger');
            }
        } catch (e) {
            showToast('❌ Error', e.message, 'danger');
        }
    }

    function clearSchedule() {
        if (confirm('Clear all?')) {
            scheduleData.nodes.forEach(n => {
                if (n.id) {
                    window._deletedNodeIds = window._deletedNodeIds || [];
                    window._deletedNodeIds.push(n.id);
                }
            });
            scheduleData.nodes = [];
            renderNodes();
        }
    }

    async function runNodeNow() {
        if (!currentNode) return;

        if (!confirm('Execute this node IMMEDIATELY?')) return;

        // Grab current config from form
        const form = document.getElementById('nodeConfigForm');
        const formData = new FormData(form);
        const tempConfig = {};
        for (let [key, value] of formData.entries()) {
            if (['execution_time', 'is_random_time'].includes(key)) continue;
            // Handle checkboxes correctly
            if (key === 'enable_scroll') tempConfig[key] = form.elements[key].checked;
            else tempConfig[key] = value;
        }

        // 1. SAVE node state locally (update object)
        currentNode.execution_time = form.execution_time.value;
        currentNode.is_random_time = form.is_random_time.checked;
        currentNode.config = tempConfig;

        // Update duration if changed
        if (tempConfig.duration_minutes) currentNode._ui_duration = parseInt(tempConfig.duration_minutes);

        // 2. SAVE to server (persist node ID)
        const saved = await saveSchedule(true); // Silent save
        if (!saved) {
            showToast('⚠️ Warning', 'Could not save node state before running. Execution might proceed but node may not be saved.', 'warning');
        }

        const payload = {
            node_type: currentNode.node_type,
            config: tempConfig
        };

        // CLOSE MODAL IMMEDIATELY
        configModal.hide();
        renderNodes(); // Re-render first

        // Show running status on node element in calendar
        if (currentNode.el) {
            currentNode.el.classList.add('executing');
            currentNode.el.style.border = '2px solid #ffc107'; // Ensure visibility

            // Visual feedback
            const badge = document.createElement('span');
            badge.className = 'badge bg-warning text-dark position-absolute top-0 end-0 m-1';
            badge.innerText = 'Running...';
            badge.id = 'running-badge-' + (currentNode.id || 'temp');
            currentNode.el.appendChild(badge);

            try {
                const resp = await fetch(`/scheduler/accounts/${schedulerAccountId}/run_node`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();

                if (resp.ok) {
                    // Success
                    showToast('✅ Success', `Node executed successfully! ${data.result || data.message || ''}`, 'success');
                } else {
                    // Error
                    currentNode.el.classList.remove('executing');
                    currentNode.el.classList.add('node-error');
                    showToast('❌ Error', data.error || 'Execution failed', 'danger');
                }
            } catch (err) {
                console.error(err);
                currentNode.el.classList.remove('executing');
                currentNode.el.classList.add('node-error');
                showToast('❌ Error', 'Execution error: ' + err.message, 'danger');
            }
            // Note: We do NOT call renderNodes() in finally here to keep the "Running" visual
            // The ad-hoc run doesn't change persistent status, so refreshing would wipe the visual.
            // We just let it stay marked until user refreshes or moves it.

            // Actually, better to remove the badge after a timeout if success
            setTimeout(() => {
                const b = document.getElementById('running-badge-' + (currentNode.id || 'temp'));
                if (b) b.remove();
                if (currentNode.el) currentNode.el.style.border = '';
            }, 5000);
        }
    }

    // Helper function to show Bootstrap toast notifications
    function showToast(title, message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || createToastContainer();

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
        return container;
    }

    function getNodeLabel(type) {
        const labels = {
            'bio': '👤 Bio', 'username': '@Username', 'photo': '📷 Photo',
            'import_contacts': '📞 Import', 'subscribe': '📺 Subscribe',
            'visit': '👁️ Visit', 'idle': '💤 Idle',
            'passive_activity': '🧘 Passive Activity', 'smart_subscribe': '🔔 Smart'
        };
        return labels[type] || type;
    }

})();
