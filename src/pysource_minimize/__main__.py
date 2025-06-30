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
    from rich.panel import Panel
    from rich.align import Align
    from rich.markdown import Markdown
except ModuleNotFoundError:
    print("pysource-minimize can only be used if you installed pysource-minimize[cli]")
    exit(1)


from ._minimize import minimize_all


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


def escape_markdown(s: str) -> str:
    return s.replace("_", "\\_")


@click.command()
@click.option(
    "files",
    "--file",
    multiple=True,
    type=click.Path(exists=True),
    help="file to minimize",
)
@click.option(
    "dirs",
    "--dir",
    multiple=True,
    type=click.Path(exists=True),
    help="directory that is recursively searched for .py files",
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
def main(cmd, files, dirs, track, write_back, format):
    if not files and not dirs:
        print("either --dir or --file is required")
        exit(1)

    files = [pathlib.Path(f) for f in files]

    for directory in dirs:
        files += list(pathlib.Path(directory).rglob("*.py"))

    def is_on_track():
        result = sp.run(cmd, capture_output=True)
        return track in (result.stdout.decode() + result.stderr.decode())

    if not is_on_track():
        print("I don't know what you want to minimize for.")
        print(
            f"'{track}' is not a string which in the stdout/stderr of '{' '.join(cmd)}'"
        )
        sys.exit(1)

    original_sources = {f: f.read_text(encoding="utf-8") for f in files}
    console = Console()
    syntax = Syntax(list(original_sources.values())[0], "python", line_numbers=True)

    syntax_panel = Panel(syntax, title_align="left")

    check_count = 0

    last_minimized_sources = {}

    def refresh():
        live.refresh()

    def safe(path, source):
        if source is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(source, encoding="utf-8")

        import shutil

        cache = path.parent / "__pycache__"
        if cache.exists():
            shutil.rmtree(cache)

    def format_source(source):
        if source is None:
            return source, True
        formatted = False
        if format:
            try:
                source = format_str(
                    source,
                    mode=FileMode(line_length=console.size.width - 5),
                )
                formatted = True
            except:  # pragma: no cover
                pass

        return source, formatted

    def checker(sources, filename):
        nonlocal last_minimized_sources
        nonlocal check_count

        info = ""
        formatted = False
        display_source = ""
        for path, current_source in sources.items():
            current_source, current_source_formatted = format_source(current_source)

            if not current_source_formatted and format:
                info = "(formatting failed)"

            if path == filename:
                formatted = current_source_formatted
                display_source = current_source

            safe(path, current_source)

        on_track = is_on_track()

        check_count += 1
        layout["info"].update(f"test {check_count} {info}")
        syntax_panel.title = str(filename)

        last_minimized_source = last_minimized_sources.get(filename, "")
        current_source = sources[filename]

        if current_source is None:
            syntax.code = f"<deleted>"
            live.refresh()

        else:
            assert last_minimized_source is not None

            equal_lines_start, equal_lines_end = num_equal_lines(
                last_minimized_source, current_source
            )
            num_lines = len(last_minimized_source.splitlines())
            start_line = (
                equal_lines_start - 2 if num_lines > console.size.height - 2 else 0
            )

            if not on_track:

                num_lines = len(last_minimized_source.splitlines())

                syntax.highlight_lines = {
                    n
                    for n in range(
                        equal_lines_start + 1, num_lines - equal_lines_end + 1
                    )
                }

                syntax.line_range = (start_line, None)

                live.refresh()

            if sources == last_minimized_sources:
                return True

            syntax.word_wrap = formatted

            original_source = original_sources[filename]
            progress.update(
                task,
                completed=len(original_source) - len(current_source),
                total=len(original_source),
            )

            syntax.highlight_lines = {
                n for n in range(equal_lines_start + 1, num_lines - equal_lines_end + 1)
            }

            if syntax.line_range is None or start_line != syntax.line_range[0]:
                syntax.line_range = (start_line, None)
                refresh()

            syntax.code = display_source

            num_lines = len(current_source.splitlines())

            syntax.highlight_lines = {
                n for n in range(equal_lines_start + 1, num_lines - equal_lines_end + 1)
            }

            refresh()

        if on_track:
            last_minimized_sources = sources
        return on_track

    sponsoring_notification = Align(
        "You can support my work by sponsoring me on GitHub [blue link=https://github.com/sponsors/15r10nk][red]:heart:[/red] github.com/sponsors/15r10nk [/]",
        align="center",
    )

    progress = Progress()
    layout = Layout()
    layout.split_column(
        Layout(name="progress", size=1),
        Layout(name="info", size=1),
        Layout(name="code"),
        Layout(
            sponsoring_notification,
            size=1,
        ),
    )

    layout["progress"].update(progress)
    layout["code"].update(syntax_panel)
    layout["info"].update("start testing ...")

    with Live(layout, auto_refresh=False, screen=True) as live:
        task = progress.add_task("minimize")

        try:
            new_sources = minimize_all(original_sources, checker, retries=1)
        except KeyboardInterrupt:
            for path, original_source in original_sources.items():
                path.write_text(original_source, encoding="utf-8")
            return 1

    console.print(sponsoring_notification)
    console.print()

    deleted_files = [key for key, value in new_sources.items() if value is None]

    if deleted_files:
        print(
            f"These files are deleted as they are not necessary to reproduce the problem"
        )
        if len(deleted_files) >= 10:
            deleted_files = [
                *deleted_files[:3],
                f"... {len(deleted_files)-6} other files",
                *deleted_files[-3:],
            ]

        markdown = "\n".join(f" * {escape_markdown(str(f))}" for f in deleted_files)
        console.print(Markdown(markdown))

    console.print()
    console.print("The minimized code is:")
    for path, new_source in new_sources.items():
        if new_source is not None:
            new_source, _ = format_source(new_source)
            console.print(
                Panel(
                    Syntax(new_source, "python", line_numbers=True, word_wrap=True),
                    title=str(path),
                    title_align="left",
                )
            )
            console.print()

    console.print(
        "Please [blue link=https://github.com/15r10nk/pysource-minimize/issues]report[/] if your code can be further simplified. This will help pysource-minimize to improve further.\n"
    )

    if (
        write_back
        or console.is_terminal
        and Confirm.ask(
            f"Do you want to write the minimized code to the filesystem?", default=False
        )
    ):
        for path, new_source in new_sources.items():
            new_source, _ = format_source(new_source)
            safe(path, new_source)

        console.print("minimized files saved")
    else:
        for path, original_source in original_sources.items():
            path.write_text(original_source, encoding="utf-8")

        console.print("original files restored")


if __name__ == "__main__":
    main()
