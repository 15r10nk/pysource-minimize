import pathlib
import subprocess as sp
import sys

try:
    import click
    from black import format_str, FileMode
    from rich.console import Console
    from rich.live import Live
    from rich.progress import Progress
    from rich.syntax import Syntax
    from rich.prompt import Confirm
    from rich.layout import Layout
except ModuleNotFoundError:
    print("pysource-minimize can only be used if you installed pysource-minimize[cli]")
    exit(1)


from ._minimize import minimize


def num_equal_lines(a: str, b: str):
    lines_a = a.splitlines()
    lines_b = b.splitlines()
    start = 0
    for line_a, line_b in zip(lines_a, lines_b):
        if line_a != line_b:
            break
        start += 1

    end = 0
    for line_a, line_b in zip(reversed(lines_a), reversed(lines_b)):
        if line_a != line_b:
            break
        end += 1
    return start, end


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
@click.option(
    "format",
    "-f",
    "--format",
    is_flag=True,
    help="format the file with black to provide better output for complex files",
)
@click.argument("cmd", nargs=-1)
def main(cmd, file, track, write_back, format):
    file = pathlib.Path(file)

    first_result = sp.run(cmd, capture_output=True)

    if track not in (first_result.stdout.decode() + first_result.stderr.decode()):
        print("I dont know what you want to minimize for.")
        print(
            f"'{track}' is not a string which in the stdout/stderr of '{' '.join(cmd)}'"
        )
        sys.exit(1)

    original_source = file.read_text()
    console = Console()
    syntax = Syntax(original_source, "python", line_numbers=True)

    check_count = 0

    last_minimized_code = ""

    def refresh():
        live.refresh()

    def checker(source):
        nonlocal last_minimized_code
        nonlocal check_count

        info = ""
        formatted = False
        if format:
            try:
                source = format_str(
                    source, mode=FileMode(line_length=console.size.width - 5)
                )
                formatted = True
            except:
                info = "(formatting failed)"

        file.write_text(source)

        result = sp.run(cmd, capture_output=True)
        check_count += 1
        layout["info"].update(f"test {check_count} {info}")

        equal_lines_start, equal_lines_end = num_equal_lines(
            last_minimized_code, source
        )
        num_lines = len(last_minimized_code.splitlines())
        start_line = equal_lines_start - 2 if num_lines > console.size.height - 2 else 0

        if track not in (result.stdout.decode() + result.stderr.decode()):

            num_lines = len(last_minimized_code.splitlines())

            syntax.highlight_lines = {
                n for n in range(equal_lines_start + 1, num_lines - equal_lines_end + 1)
            }

            syntax.line_range = (start_line, None)

            live.refresh()

            return False

        if source == last_minimized_code:
            return True

        syntax.word_wrap = formatted

        progress.update(
            task,
            completed=len(original_source) - len(source),
            total=len(original_source),
        )

        syntax.highlight_lines = {
            n for n in range(equal_lines_start + 1, num_lines - equal_lines_end + 1)
        }

        if syntax.line_range is None or start_line != syntax.line_range[0]:
            syntax.line_range = (start_line, None)
            refresh()

        syntax.code = source

        num_lines = len(source.splitlines())

        syntax.highlight_lines = {
            n for n in range(equal_lines_start + 1, num_lines - equal_lines_end + 1)
        }

        refresh()

        last_minimized_code = source
        return True

    progress = Progress()
    layout = Layout()
    layout.split_column(
        Layout(name="progress", size=1),
        Layout(name="info", size=1),
        Layout(name="code"),
    )
    layout["progress"].update(progress)
    layout["code"].update(syntax)
    layout["info"].update("start testing ...")

    with Live(layout, auto_refresh=False, screen=True) as live:
        task = progress.add_task("minimize")

        new_source = minimize(original_source, checker, retries=2)

    console.print()
    console.print("The minimized code is:")
    console.print(Syntax(new_source, "python", line_numbers=True, word_wrap=True))
    console.print()

    if write_back or Confirm.ask(
        f"do you want to write the minimized code to {file}?", default=False
    ):
        file.write_text(new_source)
    else:
        file.write_text(original_source)


if __name__ == "__main__":
    main()
