"""Example: implementing a custom storage backend using StorageInterface."""

from pdf_autofiller_core import StorageConfig, StorageInterface


class MyCustomStorage(StorageInterface):
    def __init__(self, config: StorageConfig):
        self.config = config

    def read(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def write(self, path: str, data: bytes) -> None:
        with open(path, "wb") as f:
            f.write(data)

    def exists(self, path: str) -> bool:
        import os
        return os.path.exists(path)

    def delete(self, path: str) -> None:
        import os
        os.remove(path)


if __name__ == "__main__":
    config = StorageConfig(backend="custom", base_path="/tmp/my-storage")
    storage = MyCustomStorage(config)
    storage.write("/tmp/my-storage/test.txt", b"hello world")
    print(storage.read("/tmp/my-storage/test.txt"))
