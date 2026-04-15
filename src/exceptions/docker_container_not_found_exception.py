class DockerContainerNotFoundException(RuntimeError):
    def __init__(self, server_id: str):
        super().__init__(f"Docker container {server_id} not found")