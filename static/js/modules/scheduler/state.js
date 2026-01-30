export const state = {
    accountCreatedAtDate: null,
    currentWeekOffset: 0,

    scheduleData: {
        schedule_id: null,
        status: 'draft',
        nodes: []
    },

    schedulerAccountId: null,
    currentNode: null,

    // UI Cache
    elements: {},
    configModal: null,

    // Locks
    isSaving: false,
    isModalOpen: false,

    // Deleted nodes cache for sync
    deletedNodeIds: []
};
