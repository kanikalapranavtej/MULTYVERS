import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    # Keep the development server local and disable debug mode by default.
    # Set MULTYVERS_DEBUG=true only for local debugging.
    debug = os.environ.get("MULTYVERS_DEBUG", "false").lower() == "true"
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=debug)
