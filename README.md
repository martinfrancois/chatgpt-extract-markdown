# ChatGPT Export Markdown Extractor

Extract ChatGPT data-export conversations to Markdown. You can search for conversations containing a string, or export every conversation branch with `--all`.

## Features

- Search mode accepts three positional inputs:
  - path to a ChatGPT export `Conversations` folder
  - search string to find in message content
  - output folder for generated Markdown
- All-export mode uses `--all` and an explicit `--output-folder` to export every conversation branch without a search string.
- Creates the output folder if it does not already exist.
- Supports both `conversations.json` and split `conversations-*.json` export files.
- Matches against message content, not raw JSON metadata.
- Supports exact matching by default and case-insensitive matching with `--ignore-case`.
- Validates the ChatGPT export format before conversion and fails loudly on unknown content types, marker kinds, reference types, malformed node graphs, or malformed timestamps.
- Supports `--validate-only` to scan export files without writing Markdown.
- Finds every matching exported conversation record.
- Exports every matching branch path as its own complete root-to-leaf transcript.
- Exports every root-to-leaf branch in every conversation when `--all` is used.
- Handles branch fan-out after a matching message, so one matching conversation can produce multiple branch transcripts.
- Supports `--output-mode both`, `--output-mode normal`, and `--output-mode reasoning` to control whether paired files, normal files only, or reasoning files only are written.
- Defaults to writing two files per exported branch:
  - normal transcript: visible/user-facing messages only
  - paired `-reasoning.md` transcript: same branch plus hidden reasoning/trace entries
- Clearly marks matching messages with `[MATCH]`.
- Clearly marks hidden reasoning/trace entries with `[REASONING TRACE]` in reasoning files.
- Includes useful reasoning node metadata: node ID, content type, channel, and status.
- Prefixes output filenames with the branch leaf message timestamp in sortable UTC form with microsecond precision.
- Uses the leaf message `update_time` first, then leaf message `create_time`, then conversation `update_time` as a fallback.
- Preserves the descriptive branch filename after the timestamp prefix.
- Avoids filename collisions by choosing a unique output path when needed.
- Converts ChatGPT export web citation markers into readable Markdown links when citation metadata is available.
- Converts ChatGPT export file citation markers into readable file references, including line ranges when present.
- Converts entity annotation markers into readable entity names when possible.
- Handles known malformed ChatGPT marker fragments observed in exports, including alternate-terminated navigation markers and truncated citation fragments.
- Removes unresolved, orphaned, or malformed raw marker glyphs instead of leaving unreadable artifacts in the transcript.
- Normalizes known private-use icon glyphs from copied content into readable text labels, including location, phone, email, link, Apple menu, and separator icons.
- Cleans citation and Markdown-link URLs by removing known tracking query parameters such as `utm_*`, `srsltid`, `fbclid`, and `gclid`.
- Normalizes citation link labels to single-line readable text.
- Demotes Markdown headings inside message bodies so transcript message headers remain visually dominant.
- Preserves hashes in prose, hashtags, escaped hashes, indented comments, fenced code, and raw code-like messages.
- Leaves headings inside fenced code blocks unchanged.
- Closes unclosed fenced code blocks at message boundaries so one malformed message cannot swallow the next transcript header.
- Handles common content shapes from the export, including text parts, code content, attachments, file references, and nested text fields.
- Processes one conversation JSON file at a time, so large split exports do not require loading the whole export into memory at once.
- Omits the per-file path list for `--all` exports to avoid flooding the terminal with thousands of paths.
- Keeps generated private transcript output in ignored folders such as `private-output/`, `output/`, or `extracted*/`.
- Includes pytest tests, coverage enforcement, strict pyrefly checking, and GitHub Actions CI.
- Keeps tests structured with explicit Given/When/Then comments and parameterized edge-case tables where appropriate.

## Requirements

- Python 3.10 or newer
- `pytest` for tests
- `pytest-cov` for test coverage
- `pyrefly` for type checking and 100% type coverage enforcement

## Quick Start

Clone the repository, then from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

The extractor itself uses only the Python standard library. The dependencies are for testing and type checking. Installing with `-e .` adds the `chatgpt-extract-markdown` console command.

## Usage

Search for a string and export matching branches:

```bash
python extract_chatgpt_markdown.py \
  "/path/to/ChatGPT export/User Online Activity/Conversations" \
  "string that appears in the conversation" \
  "/path/to/output-folder"
```

After installing the project, the same command can be run through the console entry point:

```bash
chatgpt-extract-markdown \
  "/path/to/ChatGPT export/User Online Activity/Conversations" \
  "string that appears in the conversation" \
  "/path/to/output-folder"
```

The output folder is created if it does not already exist.

Export every conversation branch without searching:

```bash
python extract_chatgpt_markdown.py \
  "/path/to/ChatGPT export/User Online Activity/Conversations" \
  --all \
  --output-folder "/path/to/output-folder"
```

Control which file variants are written:

```bash
python extract_chatgpt_markdown.py \
  "/path/to/ChatGPT export/User Online Activity/Conversations" \
  --all \
  --output-folder "/path/to/output-folder" \
  --output-mode normal
```

Available output modes:

- `both`: write normal files and paired `-reasoning.md` files; this is the default
- `normal`: write normal files only
- `reasoning`: write `-reasoning.md` files only

Validate an export without converting conversations:

```bash
python extract_chatgpt_markdown.py \
  "/path/to/ChatGPT export/User Online Activity/Conversations" \
  --validate-only
```

Example:

```bash
python extract_chatgpt_markdown.py \
  "/path/to/export/User Online Activity/Conversations" \
  "a unique sentence from the conversation" \
  "./output"
```

## Matching Behavior

- The script searches visible/user-facing message content for the requested string.
- Hidden reasoning/trace messages do not cause a match by themselves.
- If a matching message appears before branch fan-out, each downstream branch is exported as a separate complete transcript.
- Use `--ignore-case` for case-insensitive matching.
- `--all` ignores `search_string`, exports every root-to-leaf branch, and does not add `[MATCH]` markers.
- With `--all`, pass the output path using `--output-folder`; positional output arguments are rejected to avoid ambiguity with the optional `search_string` positional.

## Validation Behavior

- Validation runs before every conversion.
- `--validate-only` validates all conversation JSON files in the input folder without writing Markdown.
- Unknown export shapes are treated as errors instead of being converted silently.
- Known private-use glyphs are converted explicitly; unknown private-use glyphs remain validation errors so new export artifacts cannot slip through silently.
- After conversion, generated Markdown is checked for raw ChatGPT marker glyphs, unclosed code fences, reasoning leakage into normal files, and output-mode mismatches.
- Search-mode output is also checked for missing `[MATCH]` markers.
- Paired metadata is checked when `--output-mode both` is used.
- To verify a large export without writing every transcript, use `--validate-only`; tests use small synthetic fixtures for `--all` rather than converting a full private archive.

## Reference Full-Export Run

These numbers are from one local full-export run with `--all --output-mode both`. They are meant as a rough reference; runtime and output size depend heavily on export size, branch count, message length, and disk speed.

| Metric | Value |
|---|---:|
| Source JSON files | 52 |
| Conversations | 5,195 |
| Nodes | 127,811 |
| Messages | 122,616 |
| Root-to-leaf branches | 8,339 |
| Markdown files written | 16,678 |
| Normal transcript files | 8,339 |
| Reasoning transcript files | 8,339 |
| Conversion time | 61.20 seconds |
| Throughput | 272.5 files/second |
| Output size | 645.4 MiB |
| Normal transcript size | 256.4 MiB |
| Reasoning transcript size | 389.0 MiB |
| Median file size | 9.3 KiB |
| Largest file size | 1.7 MiB |
| Median lines per file | 179 |
| Largest file lines | 38,566 |
| Post-conversion integrity check | 22.51 seconds |

The integrity check found zero raw private-use marker glyphs, zero unclosed Markdown fences, zero reasoning traces leaking into normal transcripts, and zero missing reasoning headers.

## Marker And Glyph Conversion Behavior

- Web citation markers with export metadata become readable Markdown links.
- File citation markers with export metadata become readable file references, with line ranges when present.
- Entity markers become readable entity names when the marker payload contains one.
- Unresolved full markers, orphan line markers, alternate-terminated navigation markers, and truncated citation fragments are removed because the export does not contain enough reliable inline information to render them correctly.
- Legacy citation wrapper glyphs are stripped while preserving the surrounding sentence text.
- Known copied icon-font glyphs are converted to labels: location, phone, email, link, Apple menu, or a simple separator.
- Any newly observed marker kind, reference type, content type, graph shape, or private-use glyph that is not explicitly handled fails validation.

## Tests And Type Checking

Run the test suite:

```bash
pytest
```

The test suite enforces at least 90% line coverage for the extractor.

Run pyrefly in strict mode with 100% strict type coverage enforcement:

```bash
pyrefly check --preset strict
pyrefly coverage check --strict --fail-under 100
```

Both commands are also run by the GitHub Actions workflow in `.github/workflows/ci.yml`.

Check the installed CLI entry point:

```bash
chatgpt-extract-markdown --help
```

## Privacy

- Do not place ChatGPT export files in this project unless they are intentionally private and ignored.
- Do not commit generated transcripts.
- `.gitignore` excludes common export files, generated output folders, virtual environments, caches, and coverage artifacts.
- Tests use synthetic data only and should not contain private export paths, exact private search strings, or transcript content.

## License

This project is licensed under the GNU General Public License v3.0 or later. See `LICENSE`.

## Output Format

Output filenames begin with a branch-specific timestamp in UTC:

```text
YYYY-MM-DDTHH-MM-SS.microsecondsZ__previous-filename-shape.md
YYYY-MM-DDTHH-MM-SS.microsecondsZ__previous-filename-shape-reasoning.md
```

The timestamp prefix sorts well lexicographically and includes microseconds to reduce collisions. It is chosen from the branch leaf message `update_time`, then leaf message `create_time`, then conversation `update_time` if the leaf has no usable timestamp.

Each Markdown file includes:

- Conversation title and ID
- Source JSON file
- Branch and leaf node information
- Created and updated timestamps
- Matching message IDs
- The conversation messages in branch order
- In search mode, a `[MATCH]` marker on messages containing the search string

The paired `-reasoning.md` file includes the same branch plus reasoning/trace entries from the export. Those entries are clearly marked with `[REASONING TRACE]` and include node metadata such as content type, channel, and status.
