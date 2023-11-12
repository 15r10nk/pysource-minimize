from pathlib import Path

import nox

nox.options.sessions = ["clean", "test", "report", "mypy"]
nox.options.reuse_existing_virtualenvs = True

python_version = ["3.8", "3.9", "3.10", "3.11", "3.12"]


@nox.session(python="python3.10")
def clean(session):
    session.run_always("poetry", "install", "--with=dev", external=True)
    session.env["TOP"] = str(Path(__file__).parent)
    session.run("coverage", "erase")


@nox.session(python=python_version)
def mypy(session):
    session.install("poetry")
    session.run("poetry", "install", "--with=dev")

    if Path("../pysource-minimize/").exists():
        session.install("../pysource-minimize/")

    session.run("mypy", "pysource_minimize", "tests")


@nox.session(python=python_version)
def test(session):
    session.run_always("poetry", "install", "--with=dev", external=True)
    session.env["COVERAGE_PROCESS_START"] = str(
        Path(__file__).parent / "pyproject.toml"
    )
    session.env["TOP"] = str(Path(__file__).parent)
    args = [] if session.posargs else ["-n", "auto", "-v"]
    session.install("attrs")  # some bug with pytest-subtests
    if Path("../pysource-minimize/").exists():
        session.install("../pysource-minimize/")

    session.run("pytest", *args, "tests", *session.posargs)


@nox.session(python="python3.10")
def report(session):
    session.run_always("poetry", "install", "--with=dev", external=True)
    session.env["TOP"] = str(Path(__file__).parent)
    try:
        session.run("coverage", "combine")
    except:
        pass
    session.run("coverage", "html")
    session.run("coverage", "report")


# @nox.session(python="python3.10")
# def docs(session):
#    session.install("poetry")
#    session.run("poetry", "install", "--with=doc")
#    session.run("mkdocs", "build")
