import os

os.environ.setdefault("FC_CLOUD_HOST", "0.0.0.0")

from server import run


if __name__ == "__main__":
    run()
