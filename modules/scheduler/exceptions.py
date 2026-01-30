"""
Scheduler Module Exceptions
"""

class SchedulerError(Exception):
    """Base exception for scheduler operations"""
    pass

class ScheduleNotFoundError(SchedulerError):
    """Raised when schedule is not found"""
    pass

class NodeNotFoundError(SchedulerError):
    """Raised when schedule node is not found"""
    pass

class ScheduleAlreadyExistsError(SchedulerError):
    """Raised when attempting to create a duplicate schedule"""
    pass

class ScheduleAlreadyActiveError(SchedulerError):
    """Raised when attempting to start an active schedule"""
    pass

class InvalidNodeDataError(SchedulerError):
    """Raised when node data is invalid"""
    pass
