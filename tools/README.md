# Developer tools

## Purpose

`compile_check.py` is the offline compile gate. It compile-checks each Streamer.bot code sub-action source against the .NET Framework 4.8 reference assemblies, Newtonsoft.Json 13.0.3 and a hand-written CPH stub, so a broken line is caught before the file is ever pasted or imported into Streamer.bot.

Nothing in `tools/` is part of a `.sb` package or needed by Streamer.bot at runtime. The reference packages are dev-time only.

## Prerequisites

- .NET SDK 9.0.304 or newer (`dotnet` on PATH)
- Python 3.13, standard library only
- Network access only for the first `dotnet restore`; after that the two packages come from `~/.nuget/packages` and the gate works offline

## Commands

```text
python -I tools/compile_check.py
python -I tools/compile_check.py --self-test
python -I tools/compile_check.py --files path/a.cs path/b.cs
python -I tools/compile_check.py --lang 9.0
```

- No arguments: compile every `codes[].source` listed in `tools/packages/*.json` (manifest order), then every `tools/golden/*.cs` (sorted). One compilation per file.
- `--self-test`: compile the three fixtures in `tools/fixtures/compile/` and check the gate behaves: `good.cs` passes, `bad_syntax.cs` (one missing semicolon) fails with CS1002, `net48_gap.cs` (uses `HashCode` and `Span<int>`) fails with CS0246. Prints `PASS self-test:<case>` or `FAIL self-test:<case> ...`.
- `--files`: compile only the listed files, each on its own.
- `--lang VER`: C# language version, passed as `-p:CcLangVersion=VER`. The default is 7.3 until the language version Streamer.bot really uses is read live (finding F6).

Output lines: `OK <path>`, `FAIL <path> codes=<list>` (followed by up to five diagnostic lines), `PASS self-test:<case>`, `FAIL self-test:<case> ...`, and the summary `compile_check: <n> passed, <m> failed`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | every input passed (or every self-test case behaved as expected) |
| 1 | at least one input failed to compile, or a self-test case misbehaved |
| 2 | environment or usage problem: no sources found, bad manifest, input file not found, `dotnet` missing, or `dotnet restore` failed |

## How verdicts are decided

The verdict comes from the `dotnet build` exit code and from the diagnostic codes `CSnnnn`, `NUnnnn` and `MSBnnnn` found in its output. Message text is never inspected, because the toolchain output on this machine is Russian-localized. The child process also gets `DOTNET_CLI_UI_LANGUAGE=en` and `VSLANG=1033`, but nothing depends on that.

Every run builds in its own temporary copy of `tools/compile-check/`, so parallel runs never share `obj/` or `bin/` and the repository never receives build output. The temporary directory is removed at the end of the run.

## Why `python -I`

Isolated mode ignores `PYTHON*` environment variables and the user site directory, so the same command behaves the same on every machine. The scripts are standalone and import nothing from their own folder.

## What an offline pass does NOT prove

A pass means only: this file compiles against the net48 reference assemblies, Newtonsoft.Json 13.0.3 and the stub. It does NOT prove:

- Streamer.bot's own reference resolution (the references it passes to its compiler)
- the language version Streamer.bot configures (live finding F6; the gate's 7.3 default is a conservative guess)
- Streamer.bot's rewriting of the class (the `#if EXTERNAL_EDITOR` header below is a vendor-documented convention, not a measured result)
- any runtime behavior: lifecycle, triggers, listeners, shutdown

The stub is hand-written from signatures reflected from the Streamer.bot 1.0.7 `Streamer.bot.Plugin.Interface.dll`, so it is only as accurate as those signatures. A live compile in Streamer.bot is still required for every shipped file.

## Source rules

- One `.cs` file is one code sub-action and is compiled alone. Two files that both declare `CPHInline` never share a compilation.
- Every code sub-action source starts its class with the vendor-documented conditional header:

```csharp
#if EXTERNAL_EDITOR
public class CPHInline : CPHInlineBase
#else
public class CPHInline
#endif
```

- The gate defines `EXTERNAL_EDITOR`, so the base class from the stub is used offline; Streamer.bot does not define it.
- Default `LangVersion` is 7.3 until finding F6 is read live. `TreatWarningsAsErrors` is off.

## Inputs

Only package-manifest sources (`tools/packages/*.json`, field `codes[].source`) and `tools/golden/*.cs` are default inputs. The legacy scripts in the repository root (`integration.cs`, `updateChecker.cs`) are never inputs: they do not compile today and are rewritten in Phase 2.
