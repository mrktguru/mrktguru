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

export function getNodeLabel(type) {
    if (!type) return 'Unknown';
    return type.replace(/_/g, ' ').toUpperCase();
}

export function getNodeColor(type) {
    return COLORS[type] || '#f8f9fa';
}
