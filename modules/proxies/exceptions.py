"""
Proxy Module Exceptions
"""

class ProxyError(Exception):
    """Base exception for proxy operations"""
    pass

class ProxyValidationError(ProxyError):
    """Raised when proxy data is invalid"""
    pass

class ProxyNotFoundError(ProxyError):
    """Raised when proxy is not found"""
    pass

class NetworkValidationError(ProxyError):
    """Raised when network data is invalid"""
    pass

class NetworkInUseError(ProxyError):
    """Raised when deleting a network that is in use"""
    pass

class NetworkNotFoundError(ProxyError):
    """Raised when network is not found"""
    pass

class BulkImportError(ProxyError):
    """Raised when bulk import fails or has format errors"""
    pass
