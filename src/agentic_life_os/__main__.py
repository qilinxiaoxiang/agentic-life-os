import os

from .app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("LIFEOS_HOST", "127.0.0.1"),
        port=int(os.environ.get("LIFEOS_PORT", "5050")),
        debug=False,
    )
