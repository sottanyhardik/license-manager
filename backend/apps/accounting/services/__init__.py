"""Write-side accounting services. Every financial write goes through here (ARCHITECTURE_RULES 3)."""


class AccountingError(Exception):
    """Business-rule violation; message is user-facing."""

    def __init__(self, message: str, code: str = "accounting_error"):
        super().__init__(message)
        self.code = code
