"""CLI commands for Sentinel."""

import click

from sentinel import __version__


@click.group()
@click.version_option(version=__version__, prog_name="sentinel")
def main() -> None:
    """Sentinel - Personal Energy Guardian CLI.

    Detect schedule conflicts that calendars miss. Sentinel uses knowledge graphs
    to find hidden energy collisions in your schedule.

    Example: sentinel --help
    """
    pass


if __name__ == "__main__":
    main()
