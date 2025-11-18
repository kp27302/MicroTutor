import os
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Also try loading from current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, rely on system environment variables
    pass

from ui.interface import build_interface


def main():
    app = build_interface()
    app.launch(share=True)


if __name__ == "__main__":
    main()

