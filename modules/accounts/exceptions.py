"""
Custom Exceptions for Accounts Module

These exceptions are raised by services and caught by routes to provide
appropriate HTTP responses (flash messages, redirects, JSON errors).
"""


class AccountError(Exception):
    """Base exception for all account-related errors"""
    pass


class AccountNotFoundError(AccountError):
    """Raised when account doesn't exist in database"""
    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__(f"Account {account_id} not found")


class AccountDuplicateError(AccountError):
    """Raised when trying to create account with existing phone"""
    def __init__(self, phone: str):
        self.phone = phone
        super().__init__(f"Account with phone {phone} already exists")


class SessionNotConfiguredError(AccountError):
    """Raised when account has no session (session_string or session_file)"""
    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__(f"Account {account_id} has no session configured")


class SessionValidationError(AccountError):
    """Raised when session file is invalid or corrupted"""
    def __init__(self, message: str, filename: str = None):
        self.filename = filename
        super().__init__(message)


class SuspiciousSessionError(AccountError):
    """Raised when session file appears suspicious (potential ban risk)"""
    def __init__(self, filename: str, reasons: list[str]):
        self.filename = filename
        self.reasons = reasons
        super().__init__(f"Suspicious session {filename}: {', '.join(reasons)}")


# ===================== Telegram Errors =====================

class TelegramError(AccountError):
    """Base exception for Telegram API errors"""
    pass


class TelegramFloodWaitError(TelegramError):
    """Raised when Telegram returns FloodWait error"""
    def __init__(self, wait_seconds: int):
        self.wait_seconds = wait_seconds
        super().__init__(f"Telegram FloodWait: wait {wait_seconds} seconds")


class TelegramBannedError(TelegramError):
    """Raised when account is banned by Telegram"""
    def __init__(self, reason: str = None):
        self.reason = reason or "Account banned"
        super().__init__(self.reason)


class TelegramSessionInvalidError(TelegramError):
    """Raised when session is invalid (expired, revoked)"""
    def __init__(self, message: str = None):
        super().__init__(message or "Session is invalid")


class TelegramHandshakeError(TelegramError):
    """Raised when handshake/connection fails"""
    def __init__(self, message: str = None):
        super().__init__(message or "Handshake failed")


# ===================== Proxy Errors =====================

class ProxyError(AccountError):
    """Base exception for proxy-related errors"""
    pass


class ProxyNotFoundError(ProxyError):
    """Raised when proxy doesn't exist"""
    def __init__(self, proxy_id: int):
        self.proxy_id = proxy_id
        super().__init__(f"Proxy {proxy_id} not found")


class ProxyNetworkNotFoundError(ProxyError):
    """Raised when proxy network doesn't exist"""
    def __init__(self, network_id: int):
        self.network_id = network_id
        super().__init__(f"Proxy network {network_id} not found")


class ProxyAssignmentError(ProxyError):
    """Raised when proxy assignment fails"""
    pass


# ===================== 2FA Errors =====================

class TwoFAError(AccountError):
    """Base exception for 2FA errors"""
    pass


class TwoFANotSetError(TwoFAError):
    """Raised when trying to remove 2FA that isn't set"""
    def __init__(self, account_id: int):
        self.account_id = account_id
        super().__init__(f"Account {account_id} has no 2FA password stored")


class TwoFASetError(TwoFAError):
    """Raised when setting 2FA fails"""
    pass


# ===================== Cooldown Errors =====================

class CooldownError(AccountError):
    """Raised when action is on cooldown"""
    def __init__(self, action: str, remaining_minutes: int):
        self.action = action
        self.remaining_minutes = remaining_minutes
        super().__init__(f"{action} is on cooldown. Wait {remaining_minutes} minute(s)")
