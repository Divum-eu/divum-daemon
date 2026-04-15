class ServerNameAlreadyExistsException(RuntimeError):
    def __init__(self, server_name):
        super().__init__(f"Server {server_name} already exists")