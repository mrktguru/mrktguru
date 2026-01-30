import { COLORS } from './constants.js';

export function getMonday(d) {
    d = new Date(d);
    d.setHours(0, 0, 0, 0); // Always standardize to midnight
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const mon = new Date(d.setDate(diff));
    mon.setHours(0, 0, 0, 0);
    return mon;
}

export function getNodeLabel(type, id = null) {
    if (!type) return 'Unknown';
    let label = type.replace(/_/g, ' ').toUpperCase();

    // User requested IDs for these types
    if (id && (type === 'passive_activity' || type === 'search_filter')) {
        label += ` ${id}`;
    }
    return label;
}

export function getNodeColor(type) {
    return COLORS[type] || '#f8f9fa';
}
