class DockerImageNotFoundException(RuntimeError):
    def __init__(self, image: str):
        super().__init__(f"Docker image '{image}' not found")