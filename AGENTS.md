# Agent Notes

This project was created to extract selected conversations from a ChatGPT data export into Markdown.

## Documentation Maintenance

- Keep `README.md` synchronized with implemented behavior. When a feature, output format, CLI behavior, privacy rule, test requirement, or quality gate changes, update the README in the same turn.
- Keep this `AGENTS.md` file updated with any user preference or project constraint that would be useful in a fresh session.
- Autonomously update `README.md` and `AGENTS.md` as requirements evolve; do not wait for a separate reminder when the change is relevant.
- Do not add private export paths, personal names, exact private search strings, or extracted transcript content to README or AGENTS.
- The user chose GPL-3.0-or-later for this project. Keep `LICENSE`, `README.md`, and package metadata aligned with that choice.

## Session-Specific Requirements

- Do not write into the ChatGPT export folder. Treat it as read-only input.
- Keep reusable project files free of private export paths, personal names, exact private search strings, and extracted transcript content.
- Generated transcript output belongs under ignored folders such as `private-output/`, `output/`, or `extracted*/`.
- By default, each exported branch must export two Markdown files:
  - a normal transcript file
  - a paired `-reasoning.md` file
- Preserve `--output-mode both|normal|reasoning`. `both` is the default; `normal` suppresses reasoning files; `reasoning` writes only `-reasoning.md` files.
- Preserve `--all` as the explicit all-conversations export mode. Require `--output-folder` with `--all` rather than relying on ambiguous positional arguments.
- Do not run `--all` against the full private export during routine validation; use `--validate-only` for the full export and small synthetic fixtures for all-mode conversion tests.
- Keep all-mode scalable: process one conversation JSON file at a time, avoid holding generated Markdown for the whole export in memory, and avoid printing thousands of output paths to the terminal.
- The `-reasoning.md` file must clearly mark hidden reasoning/trace entries with `[REASONING TRACE]` and include useful node metadata.
- Normal transcript files must not include reasoning trace markers or hidden reasoning content.
- Output filenames must start with a branch-specific timestamp in sortable UTC form:
  `YYYY-MM-DDTHH-MM-SS.microsecondsZ__`, followed by the existing descriptive branch filename.
- Choose the filename timestamp from the branch leaf message `update_time` first, then branch leaf message `create_time`, then conversation `update_time` as a fallback.
- Do not leave raw ChatGPT private-use marker glyphs in extracted Markdown. Handle web citations, file citations, entity annotations, and orphan line-reference markers; use export metadata for readable links or file labels when possible, and remove unresolved markers.
- Preserve explicit conversion behavior for newly observed export artifacts: alternate-terminated navigation markers and truncated citation fragments are removed because they lack reliable citation metadata; copied private-use icon glyphs are converted to readable labels such as `Location:`, `Phone:`, `Email:`, `Link:`, `Apple menu`, or a simple separator.
- Do not broaden private-use glyph handling into silent deletion. Add a specific conversion rule and synthetic tests for each newly observed glyph or marker form, then rerun full-export `--validate-only`.
- Demote Markdown headings inside message bodies so the transcript's own message headers remain the top visible structure. Do not demote headings inside fenced code blocks, raw code-like messages, hashtags, escaped hashes, indented comments, or ordinary prose containing `#`.
- Close unclosed fenced code blocks at message boundaries so malformed exported Markdown cannot swallow the next transcript header.
- Clean known tracking query parameters from citation and Markdown-link URLs outside code fences.
- Keep export validation fail-closed. Unknown content types, marker kinds, reference types, malformed node graphs, and malformed timestamps should produce validation errors rather than best-effort output. Preserve `--validate-only` so full exports can be scanned without converting all conversations.
- Treat README as the public feature inventory for the script.

## Quality Gates

- Use `pytest` for tests.
- Maintain at least 90% test coverage through pytest-cov.
- Keep tests readable and maintainable with explicit `# Given`, `# When`, and `# Then` comments, and prefer `pytest.mark.parametrize` for repeated input/output cases.
- Preserve the extractor's helper boundaries during future changes: keep timestamp normalization, branch/path handling, ChatGPT marker cleanup, fence tracking, message rendering, and paired file writing centralized rather than duplicating that logic inline.
- Use pyrefly in strict mode:

```bash
pyrefly check --preset strict
pyrefly coverage check --strict --fail-under 100
```

- Keep strict pyrefly type coverage at 100%.
- Keep the GitHub Actions workflow aligned with the local test and pyrefly commands.
- Keep the installable console entry point working:

```bash
python -m pip install -e .
chatgpt-extract-markdown --help
```

## Privacy Checks

Before considering changes complete, scan reusable files for accidentally embedded private data. Exclude ignored/generated output and the virtual environment from this scan.
