class ClientAPIException(RuntimeError):
    def __init__(self, message: str | None = None):
        super().__init__(message)