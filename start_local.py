#!/usr/bin/env python
"""Start the production-style local ICUMS Simulator server."""

import argparse
import ipaddress
import os


def validated_host(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a numeric loopback address such as 127.0.0.1.") from exc
    if not address.is_loopback:
        raise argparse.ArgumentTypeError("Local serving is restricted to a loopback address.")
    return value


def main():
    parser = argparse.ArgumentParser(description="Serve ICUMS Simulator locally using Waitress.")
    parser.add_argument("--host", type=validated_host, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_production")
    import django
    django.setup()

    from django.core.management import call_command
    from waitress import serve

    call_command("check")
    call_command("collectstatic", interactive=False, verbosity=0)
    from config.wsgi import application

    print(f"ICUMS Simulator is available at http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop the local server.")
    serve(application, host=args.host, port=args.port, threads=4)


if __name__ == "__main__":
    main()
