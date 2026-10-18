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

## Stub drift check (optional)

The gate never requires this. `tools/verify-stub.ps1` compares the members declared in `tools/compile-check/Stub/CphStub.cs` with the Plugin Interface of a local Streamer.bot install, so the hand-written stub can be re-checked after a Streamer.bot update.

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir <Streamer.bot folder> [-Facts]
```

- It reads DLL metadata only (reflection-only load); no code from the install is executed, and the `data` folder and logs are never opened.
- Output: `OK <return type> <member>(<parameter types>)` for each stub member found in the real interface, `DRIFT <member>/<arity>: ...` for each one that is not. It prints only the stub's own members and never lists other proxy members.
- Exit code 1 when any `DRIFT` line was printed, otherwise 0.
- `-Facts` also prints the `EventType` values for StreamerbotStarted, StreamerbotExiting, CustomEvent and CustomCodeEvent and the file versions of `Streamer.bot.exe`, `Newtonsoft.Json.dll` and `Microsoft.CodeAnalysis.CSharp.dll`. These are offline facts, not live behavior.
- Streamer.bot DLLs are never committed to this repository.

## Package builder

`build_sb.py` turns repository sources into an importable Streamer.bot `.sb` file. Standard library only.

```text
python -I tools/build_sb.py build spike --check
python -I tools/build_sb.py build spike --out some/other/path.sb
python -I tools/build_sb.py check <file>
python -I tools/build_sb.py audit <file>
python -I tools/build_sb.py decode <file> --pretty --out <path outside the repo>
python -I tools/build_sb.py diff-ids <a> <b>
python -I -m unittest discover -s tools/tests -t tools
```

- `build <package>` reads `tools/packages/<package>.json`, the golden export it names and the C# files listed in `codes[].source`, and writes the `.sb` (default `dist/<package>.sb`). `dist/` is gitignored and a built file is never committed.
- `check <file>` runs generic structural checks on any `.sb`; `audit <file>` is the secret and shape audit; `decode` prints the JSON (use `--pretty` and write the result outside the repo, since it contains the embedded source); `diff-ids` compares object ids between two files.
- Exit codes of `build`: 0 ok, 1 a build-check failed or a required golden template kind is missing, 2 manifest, file or usage error.

### The golden is the only schema authority

`tools/golden/golden-1.0.7.sb` is a real export from Streamer.bot 1.0.7. For every object kind it emits (action, trigger of a type, Execute C# Code and Execute C# Method sub-action, queue, envelope) the builder deep-copies the golden's instance and overrides only keys that instance already has. Overriding a key the golden lacks stops the build with `no invented fields`. If the manifest needs a kind the golden does not contain, the build stops with `golden lacks <kind>` (for example `trigger:707`) and the fix is to re-export the golden following `tools/golden/RECIPE.md`. Only actions marked `"optional": true` are skipped in that case, and the build prints `SKIP <action>: golden lacks <kind>`.

The current golden has no Streamer.bot Exiting trigger (the 1.0.7 trigger picker did not offer it), so `SPIKE | On exiting` is skipped and the spike package has 25 actions.

### What `build <package> --check` proves

The file is written, read back and compared. Each line is `PASS build-check:<name>` or `FAIL build-check:<name> <detail>`.

| Check | Meaning |
|-------|---------|
| `roundtrip` | re-serializing the decoded JSON reproduces the decoded bytes exactly (CRLF, 2-space indent, number tokens such as `0.0` unchanged) |
| `model` | the model decoded from the written file equals the model built in memory |
| `bytecode` | every `byteCode` decodes to the BOM-free, CRLF-normalized text of the manifest source file |
| `no-bom` | neither the JSON nor any embedded source starts with a UTF-8 BOM |
| `deterministic` | a second build in memory packs to identical bytes and reproduces the written JSON |
| `keysets` | every emitted object has the same key names in the same order as the golden object of its kind; copied actions are compared node by node |
| `ids` | all ids are lowercase non-null GUIDs, unique, and equal to the ids recomputed from their stable names |
| `refs` | every GUID reference (`parentId`, `executeCodeId`, `queue`) resolves inside the file and no golden id is left over |
| `methods-exist` | every method named in the manifest is declared as `public bool <Method>()` in its source |

These checks compare the output with the golden and with the repository. They do not prove that Streamer.bot imports the file or that the embedded code compiles there; the offline gate (`compile_check.py`) and the live import are separate steps.

### Determinism

The decoded JSON bytes depend only on the inputs (the serializer is fixed; the unit tests check it on one machine). The `.sb` bytes (base64 of gzip) are identical between two builds on one machine; the compressed bytes can differ between zlib builds, so never compare `.sb` files from different machines byte for byte. Compare decoded JSON (`sha256-json=` in the `built` line) instead.

### Id scheme

Every id is `uuid5(namespace, "<package>/<kind>/<name>")` with the package's fixed `namespace` from its manifest: `<package>/action/<name>`, `<package>/queue/<name>`, `<package>/code/<key>`, `<package>/sub/<action name>/<index>`, `<package>/trigger/<action name>/<index>`. Ids inside an action copied from the golden are `<package>/tpl/<action name>/<golden id>`, and every reference to a golden id is re-pointed to the new one. Do not change a package's `namespace` or these names after a user has imported the package once: Streamer.bot would treat the new ids as new objects and re-importing would create duplicates.

### Known limits

- The code sub-action `references` list is copied from the golden unchanged. The golden lists `mscorlib.dll`, `System.Net.Http.dll` and `Newtonsoft.Json.dll`; the offline gate compiles against the full net48 reference set, so a type from another assembly (for example `System.dll`) would pass offline and still fail to compile inside Streamer.bot if that assembly is not referenced.
- Actions copied from the golden carry the golden's own sub-action values (for example the If/Else inputs) as they were typed in the export.

The live spike tooling and the run sheet are in `docs/live-spikes/RUNSHEET.md` (written by the Phase 1 run-sheet plan, 01-06).
