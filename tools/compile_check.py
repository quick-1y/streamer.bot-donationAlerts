"""Offline compile gate for Streamer.bot code sub-action sources.

Run it as:  python -I tools/compile_check.py --files path/to/source.cs

Each source is compiled as its own compilation against the net48 reference
assemblies, Newtonsoft.Json and a hand-written CPH stub. Pass or fail comes
only from the dotnet exit code and CSnnnn / NUnnnn / MSBnnnn codes, never from
message text, because the toolchain output can be localized.

An offline pass does NOT prove the code compiles or behaves correctly inside
Streamer.bot itself. See tools/README.md.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = REPO_ROOT / "tools" / "compile-check"

CS_CODE = re.compile(r"error (CS\d{4})")
TOOL_CODE = re.compile(r"error (NU\d{4}|MSB\d{4})")
MAX_DIAGNOSTIC_LINES = 5

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_ENVIRONMENT = 2


def configure_output():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")


def child_environment():
    env = dict(os.environ)
    env["DOTNET_CLI_UI_LANGUAGE"] = "en"
    env["VSLANG"] = "1033"
    env["DOTNET_NOLOGO"] = "1"
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    return env


def run_dotnet(args, env):
    completed = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )
    output = completed.stdout.decode("utf-8", errors="replace")
    return completed.returncode, output


def extract_codes(output):
    codes = set(CS_CODE.findall(output))
    codes.update(TOOL_CODE.findall(output))
    return sorted(codes)


def diagnostic_lines(output):
    lines = []
    for line in output.splitlines():
        text = line.strip()
        if "error " in text and text not in lines:
            lines.append(text)
        if len(lines) >= MAX_DIAGNOSTIC_LINES:
            break
    return lines


def display_path(path):
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_input(raw):
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for base in (Path.cwd(), REPO_ROOT):
        resolved = (base / candidate).resolve()
        if resolved.is_file():
            return resolved
    return None


class Workspace:
    """A private temporary copy of the project, so builds never touch the repo."""

    def __init__(self, dotnet, lang):
        self.dotnet = dotnet
        self.lang = lang
        self.env = child_environment()
        self.root = Path(tempfile.mkdtemp(prefix="da-compile-check-"))
        self.project = self.root / "CompileCheck.csproj"

    def prepare(self):
        shutil.copy2(PROJECT_DIR / "CompileCheck.csproj", self.project)
        shutil.copytree(PROJECT_DIR / "Stub", self.root / "Stub")

    def restore(self):
        code, output = run_dotnet(
            [self.dotnet, "restore", str(self.project), "-nologo"], self.env
        )
        if code == 0:
            return True
        print("compile_check: restore failed")
        for found in extract_codes(output):
            print("  " + found)
        for line in diagnostic_lines(output):
            print("  " + line)
        return False

    def compile(self, source):
        args = [
            self.dotnet,
            "build",
            str(self.project),
            "--no-restore",
            "--no-incremental",
            "-nologo",
            "-v",
            "q",
            "-p:CcSource=" + str(source),
            "-o",
            str(self.root / "out"),
        ]
        if self.lang:
            args.append("-p:CcLangVersion=" + self.lang)
        code, output = run_dotnet(args, self.env)
        codes = extract_codes(output)
        return code, codes, output

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def check_files(workspace, sources):
    passed = 0
    failed = 0
    for source in sources:
        code, codes, output = workspace.compile(source)
        label = display_path(source)
        if code == 0 and not codes:
            passed += 1
            print("OK " + label)
        else:
            failed += 1
            print("FAIL " + label + " codes=" + ",".join(codes))
            for line in diagnostic_lines(output):
                print("  " + line)
    print("compile_check: {0} passed, {1} failed".format(passed, failed))
    return EXIT_OK if failed == 0 else EXIT_FAILED


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog="compile_check.py",
        description="Offline compile gate for Streamer.bot code sub-action sources.",
    )
    parser.add_argument("--files", nargs="+", metavar="PATH", help="compile only these sources")
    parser.add_argument("--lang", metavar="VER", help="C# LangVersion (default 7.3)")
    return parser.parse_args(argv)


def main(argv):
    configure_output()
    options = parse_arguments(argv)
    if not options.files:
        print("compile_check: no sources given (use --files)")
        return EXIT_ENVIRONMENT

    sources = []
    for raw in options.files:
        resolved = resolve_input(raw)
        if resolved is None:
            print("compile_check: not found: " + raw)
            return EXIT_ENVIRONMENT
        sources.append(resolved)

    dotnet = shutil.which("dotnet")
    if dotnet is None:
        print("compile_check: dotnet SDK not found")
        return EXIT_ENVIRONMENT

    workspace = Workspace(dotnet, options.lang)
    try:
        workspace.prepare()
        if not workspace.restore():
            return EXIT_ENVIRONMENT
        return check_files(workspace, sources)
    finally:
        workspace.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
