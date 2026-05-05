class CreateContainerException(RuntimeError):
    def __init__(self):
        super().__init__("Couldn't create container")