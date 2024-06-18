import pathlib
import subprocess as sp
import sys

import click
from rich.console import Console
from rich.progress import Progress
from rich.syntax import Syntax

from ._minimize import minimize


@click.command()
@click.option(
    "--file", required=True, type=click.Path(exists=True), help="file to minimize"
)
@click.option(
    "--track",
    required=True,
    help="string which should be in the stdout/stderr of the command during minimization",
)
@click.option(
    "write_back", "-w", "--write", is_flag=True, help="write minimized output to file"
)
@click.argument("cmd", nargs=-1)
def main(cmd, file, track, write_back):
    file = pathlib.Path(file)

    first_result = sp.run(cmd, capture_output=True)

    if track not in (first_result.stdout.decode() + first_result.stderr.decode()):
        print("I dont know what you want to minimize for.")
        print(
            f"'{track}' is not a string which in the stdout/stderr of '{' '.join(cmd)}'"
        )
        sys.exit(1)

    def checker(source):
        file.write_text(source)

        result = sp.run(cmd, capture_output=True)

        if track not in (result.stdout.decode() + result.stderr.decode()):
            return False

        return True

    original_source = file.read_text()

    with Progress() as progress:
        task = progress.add_task("minimize")

        def update(current, total):
            progress.update(task, completed=total - current, total=total)

        new_source = minimize(original_source, checker, progress_callback=update)

    if write_back:
        file.write_text(new_source)
    else:
        file.write_text(original_source)

    console = Console()

    console.print()
    console.print("The minimized code is:")
    console.print(Syntax(new_source, "python", line_numbers=True))
    console.print()

    if not write_back:
        console.print(
            "The file is not changed. Use -w to write the minimized version back to the file."
        )


if __name__ == "__main__":
    main()
