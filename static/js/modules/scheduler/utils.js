import { COLORS } from './constants.js';

export function getMonday(d) {
    d = new Date(d);
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
    return new Date(d.setDate(diff));
}

export function getNodeLabel(type) {
    if (!type) return 'Unknown';
    return type.replace(/_/g, ' ').toUpperCase();
}

export function getNodeColor(type) {
    return COLORS[type] || '#f8f9fa';
}
