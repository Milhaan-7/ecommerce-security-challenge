"""Run the hardened app locally. Bound to 127.0.0.1 only."""
import sys

from app import ALLOWED_HOST, create_app


def main(host=ALLOWED_HOST, port=5000):
    if host != ALLOWED_HOST:
        sys.exit(f"Refusing to start: host must be {ALLOWED_HOST}, got {host!r}")
    create_app().run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
