import { state } from './state.js';
import { addNode, moveNode } from './scheduler_service.js';
import { getMonday } from './utils.js';
import { SLOT_HEIGHT, DAYS_PER_VIEW } from './constants.js';

let draggedNode = null;

export function getDraggedNode() { return draggedNode; }
export function setDraggedNode(node) { draggedNode = node; }

export function initDragAndDrop() {
    const { elements } = state;

    // Sidebar Items
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
        const rect = elements.gridBackground.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const colWidth = rect.width / DAYS_PER_VIEW;
        const colIndex = Math.floor(x / colWidth);
        const slotIndex = Math.floor(y / SLOT_HEIGHT);

        if (colIndex >= 0 && colIndex < DAYS_PER_VIEW && slotIndex >= 0 && slotIndex < 24) {
            handleDropLogic(colIndex, slotIndex, e);
        }
    });

    // Handle Drop from Internal Node
    // This part is handled by handleDropLogic + state
}

function handleDropLogic(colIndex, slotIndex, e) {
    const baseMonday = getMonday(state.accountCreatedAtDate);
    const viewStartMonday = new Date(baseMonday);
    viewStartMonday.setDate(baseMonday.getDate() + (state.currentWeekOffset * 7));

    const dropDate = new Date(viewStartMonday);
    dropDate.setDate(viewStartMonday.getDate() + colIndex);

    const diffTime = dropDate.getTime() - state.accountCreatedAtDate.getTime();
    const dayNumber = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;

    if (dayNumber < 1) {
        alert("Cannot schedule before account creation date!");
        return;
    }

    const timeStr = `${slotIndex.toString().padStart(2, '0')}:00`;
    const source = e.dataTransfer.getData('source');

    if (source === 'sidebar') {
        const nodeType = e.dataTransfer.getData('nodeType');
        if (nodeType) addNode(nodeType, dayNumber, timeStr);
    } else if (source === 'internal') {
        if (draggedNode) {
            moveNode(draggedNode, dayNumber, timeStr);
            draggedNode = null;
        }
    }
}
