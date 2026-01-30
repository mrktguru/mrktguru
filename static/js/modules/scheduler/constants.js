export const CONFIG = {
    PIXELS_PER_MINUTE: 1.0,
    SLOT_DURATION_MIN: 60,
    DAYS_PER_VIEW: 7,
    get SLOT_HEIGHT() { return this.SLOT_DURATION_MIN * this.PIXELS_PER_MINUTE; },
    get TOTAL_MINUTES() { return 24 * 60; },
    get GRID_HEIGHT() { return this.TOTAL_MINUTES * this.PIXELS_PER_MINUTE; }
};

export const DAYS_PER_VIEW = CONFIG.DAYS_PER_VIEW;
export const SLOT_HEIGHT = CONFIG.SLOT_HEIGHT;

export const COLORS = {
    'bio': '#e3f2fd', 'username': '#e3f2fd', 'photo': '#e3f2fd',
    'import_contacts': '#fff3cd', 'subscribe': '#d1e7dd', 'visit': '#d1e7dd',
    'smart_subscribe': '#d1e7dd', 'idle': '#f8f9fa', 'passive_activity': '#ffe69c',
    'sync_profile': '#e3f2fd', 'set_2fa': '#f8d7da'
};
