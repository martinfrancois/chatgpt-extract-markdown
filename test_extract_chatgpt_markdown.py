import json
import re
from pathlib import Path

import pytest

from extract_chatgpt_markdown import (
    ExportValidationError,
    ValidationReport,
    active_markdown_fence,
    as_string_keyed_dict,
    branch_timestamp_value,
    close_unclosed_markdown_fence,
    clean_markdown_link_urls,
    clean_url,
    compact_whitespace,
    contains,
    demote_markdown_headings,
    fenced_block,
    iter_conversation_files,
    iter_strings,
    leaf_node_ids,
    load_conversations,
    looks_like_raw_code,
    main,
    markdown_has_unclosed_fence,
    markdown_escape_inline,
    matching_branch_paths,
    matching_node_ids,
    message_to_markdown,
    node_children,
    node_message,
    output_mode_from_arg,
    output_mode_reasoning_flags,
    output_file_metadata,
    render_branch_markdown,
    render_part,
    role_label,
    safe_filename_part,
    timestamp_for_filename,
    timestamp_to_iso,
    unique_path,
    validate_markdown_output_files,
    validate_conversations_folder,
    validation_error_summary,
    validation_summary,
    write_markdown_files,
)


SEARCH_STRING = "synthetic unique search string for branch extraction tests"
TRACE_TEXT = "synthetic hidden reasoning trace"
CITATION_MARKER = "\ue200cite\ue202turn1search0\ue201"
UNRESOLVED_CITATION_MARKER = "\ue200cite\ue202turn2search0\ue201"
FILE_CITATION_MARKER = "\ue200filecite\ue202turn3file0\ue202L8-L12\ue201"
FILE_CITATION_BASE_MARKER = "\ue200filecite\ue202turn3file0\ue201"
ENTITY_MARKER = '\ue200entity\ue202["organization","Synthetic Linux","test entity"]\ue201'
ORPHAN_LINE_MARKER = "\ue202L8-L12\ue201"
ALT_TERMINATED_MARKER = "\ue200navlist\ue202Synthetic topic\ue202turn0news1\ue20b"
TRUNCATED_CITATION_MARKER = "\ue200cite\ue202turn0"
LEGACY_CITATION_GLYPHS = "\ue203Synthetic sourced sentence\ue204\ue206"
PRIVATE_ICON_GLYPHS = (
    "\ue316 Synthetic place \ue3b8 +00 000 000 \ue0ac user@example.test "
    "\ue2e2 https://example.test \uf8ff settings Synthetic event\ue288 Talk"
)
BRANCH_TIMESTAMP_PREFIX = "2026-02-02T02-40-00.000000Z__"


def message(
    node_id: str,
    role: str,
    text: str,
    parent: str | None = None,
    children: list[str] | None = None,
    content_type: str = "text",
    update_time: object | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": node_id,
        "author": {"role": role},
        "create_time": 1_770_000_000,
        "status": "finished_successfully",
        "channel": "final" if content_type == "text" else "analysis",
        "content": {"content_type": content_type, "parts": [text]},
    }
    if update_time is not None:
        payload["update_time"] = update_time
    return {
        "id": node_id,
        "parent": parent,
        "children": children if children is not None else [],
        "message": payload,
    }


def root_node(children: list[str]) -> dict[str, object]:
    return {
        "id": "root",
        "parent": None,
        "children": children,
        "message": None,
    }


def write_export(export_dir: Path, conversations: list[dict[str, object]]) -> None:
    export_dir.mkdir()
    (export_dir / "conversations-000.json").write_text(
        json.dumps(conversations), encoding="utf-8"
    )


def write_validation_export(export_dir: Path, conversation: dict[str, object]) -> None:
    write_export(export_dir, [conversation])


def grouped_output_files(written: list[Path]) -> tuple[list[Path], list[Path]]:
    normal_files = [path for path in written if not path.name.endswith("-reasoning.md")]
    reasoning_files = [path for path in written if path.name.endswith("-reasoning.md")]
    return normal_files, reasoning_files


def file_bodies(paths: list[Path]) -> list[str]:
    return [path.read_text(encoding="utf-8") for path in paths]


def assert_all_names_start_with(paths: list[Path], prefix: str) -> None:
    assert all(path.name.startswith(prefix) for path in paths)


def assert_no_private_markers(text: str) -> None:
    assert re.search(r"[\ue000-\uf8ff]", text) is None


def matching_conversations() -> list[dict[str, object]]:
    return [
        {
            "title": "First matching conversation",
            "id": "conv-one",
            "conversation_id": "conv-one",
            "current_node": "leaf-a",
            "create_time": 1_770_000_000,
            "update_time": 1_770_000_100,
            "mapping": {
                "root": root_node(["match"]),
                "match": message(
                    "match",
                    "user",
                    SEARCH_STRING,
                    parent="root",
                    children=["trace", "leaf-b"],
                ),
                "trace": message(
                    "trace",
                    "assistant",
                    TRACE_TEXT,
                    parent="match",
                    children=["leaf-a"],
                    content_type="thoughts",
                ),
                "leaf-a": message("leaf-a", "assistant", "Branch A", parent="trace"),
                "leaf-b": message("leaf-b", "assistant", "Branch B", parent="match"),
            },
        },
        {
            "title": "Second matching conversation",
            "id": "conv-two",
            "conversation_id": "conv-two",
            "current_node": "leaf-c",
            "create_time": 1_770_000_000,
            "update_time": 1_770_000_100,
            "mapping": {
                "root": root_node(["leaf-c"]),
                "leaf-c": message("leaf-c", "user", SEARCH_STRING, parent="root"),
            },
        },
        {
            "title": "Non matching conversation",
            "id": "conv-three",
            "conversation_id": "conv-three",
            "current_node": "leaf-d",
            "mapping": {
                "root": root_node(["leaf-d"]),
                "leaf-d": message("leaf-d", "user", "No match here", parent="root"),
            },
        },
    ]


def branching_conversation_without_search_match() -> dict[str, object]:
    return {
        "title": "All branches fixture",
        "id": "all-branches",
        "conversation_id": "all-branches",
        "current_node": "leaf-a",
        "create_time": 1_770_000_000,
        "update_time": 1_770_000_100,
        "mapping": {
            "root": root_node(["start"]),
            "start": message(
                "start",
                "user",
                "ordinary prompt",
                parent="root",
                children=["leaf-a", "leaf-b"],
            ),
            "leaf-a": message("leaf-a", "assistant", "All branch A", parent="start"),
            "leaf-b": message("leaf-b", "assistant", "All branch B", parent="start"),
        },
    }


def minimal_conversation(message_node: dict[str, object]) -> dict[str, object]:
    return {
        "title": "Validation fixture",
        "id": "validation-conv",
        "current_node": "leaf",
        "create_time": 1_770_000_000,
        "update_time": 1_770_000_100,
        "mapping": {
            "root": root_node(["leaf"]),
            "leaf": message_node,
        },
    }


def validation_error_codes(error: ExportValidationError) -> set[str]:
    return {issue.code for issue in error.report.issues}


def write_raw_export(export_dir: Path, payload: object) -> None:
    export_dir.mkdir()
    (export_dir / "conversations-000.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def base_markdown(reasoning: bool) -> str:
    return (
        "# Validation output\n"
        "\n"
        "- Conversation ID: `conv`\n"
        "- Branch: `1 of 1`\n"
        "- Leaf node: `leaf`\n"
        "- Matching message IDs: `leaf`\n"
        f"- Reasoning traces included: `{'yes' if reasoning else 'no'}`\n"
        "\n"
        "## User [MATCH]\n"
        "\n"
        "synthetic body\n"
    )


def write_markdown_validation_pair(
    output_dir: Path, normal_text: str, reasoning_text: str
) -> list[Path]:
    output_dir.mkdir()
    normal_path = output_dir / "conversation.md"
    reasoning_path = output_dir / "conversation-reasoning.md"
    normal_path.write_text(normal_text, encoding="utf-8")
    reasoning_path.write_text(reasoning_text, encoding="utf-8")
    return [normal_path, reasoning_path]


def test_exact_string_matches_multiple_conversations_and_writes_reasoning_pairs(
    tmp_path: Path,
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    write_export(export_dir, matching_conversations())

    # When
    written = write_markdown_files(
        conversations_folder=export_dir,
        output_folder=output_dir,
        search_string=SEARCH_STRING,
        ignore_case=False,
    )
    normal_files, reasoning_files = grouped_output_files(written)
    normal_bodies = file_bodies(normal_files)
    reasoning_bodies = file_bodies(reasoning_files)

    # Then
    assert len(written) == 6
    assert len(normal_files) == 3
    assert len(reasoning_files) == 3
    assert_all_names_start_with(normal_files, BRANCH_TIMESTAMP_PREFIX)
    assert_all_names_start_with(reasoning_files, BRANCH_TIMESTAMP_PREFIX)
    assert all("__" in path.name for path in written)
    assert all(SEARCH_STRING in body for body in normal_bodies + reasoning_bodies)
    assert all("[MATCH]" in body for body in normal_bodies + reasoning_bodies)
    assert sum("First matching conversation" in body for body in normal_bodies) == 2
    assert sum("Second matching conversation" in body for body in normal_bodies) == 1
    assert all("[REASONING TRACE]" not in body for body in normal_bodies)
    assert any("[REASONING TRACE]" in body for body in reasoning_bodies)
    assert TRACE_TEXT not in "\n".join(normal_bodies)
    assert TRACE_TEXT in "\n".join(reasoning_bodies)


def test_case_insensitive_match_and_single_file_export_shape(tmp_path: Path) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    export_dir.mkdir()
    single_export = {
        "conversations": [
            {
                "title": "Case test",
                "id": "case-conv",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": message("leaf", "user", "Mixed CASE needle", parent="root"),
                },
            }
        ]
    }
    (export_dir / "conversations.json").write_text(json.dumps(single_export), encoding="utf-8")

    # When
    written = write_markdown_files(
        conversations_folder=export_dir,
        output_folder=output_dir,
        search_string="case needle",
        ignore_case=True,
    )

    # Then
    assert len(written) == 2
    assert iter_conversation_files(export_dir) == [export_dir / "conversations.json"]


def test_all_mode_exports_every_branch_without_requiring_match_markers(
    tmp_path: Path,
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    write_export(export_dir, [branching_conversation_without_search_match()])

    # When
    written = write_markdown_files(
        conversations_folder=export_dir,
        output_folder=output_dir,
        search_string=None,
        ignore_case=False,
        export_all=True,
        output_mode="normal",
    )
    bodies = file_bodies(written)

    # Then
    assert len(written) == 2
    assert all(not path.name.endswith("-reasoning.md") for path in written)
    assert any("All branch A" in body for body in bodies)
    assert any("All branch B" in body for body in bodies)
    assert all("[MATCH]" not in body for body in bodies)
    assert all("Search string:" not in body for body in bodies)


@pytest.mark.parametrize(
    ("output_mode", "expected_normal", "expected_reasoning"),
    [
        ("both", 1, 1),
        ("normal", 1, 0),
        ("reasoning", 0, 1),
    ],
)
def test_write_markdown_files_honors_output_mode(
    tmp_path: Path,
    output_mode: str,
    expected_normal: int,
    expected_reasoning: int,
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "user", SEARCH_STRING, parent="root")),
    )

    # When
    written = write_markdown_files(
        conversations_folder=export_dir,
        output_folder=output_dir,
        search_string=SEARCH_STRING,
        ignore_case=False,
        output_mode=output_mode_from_arg(output_mode),
    )
    normal_files, reasoning_files = grouped_output_files(written)

    # Then
    assert len(normal_files) == expected_normal
    assert len(reasoning_files) == expected_reasoning
    assert all("[MATCH]" in body for body in file_bodies(written))


@pytest.mark.parametrize(
    ("output_mode", "expected"),
    [
        ("both", [False, True]),
        ("normal", [False]),
        ("reasoning", [True]),
    ],
)
def test_output_mode_reasoning_flags_are_explicit(
    output_mode: str, expected: list[bool]
) -> None:
    # Given
    mode = output_mode

    # When
    result = output_mode_reasoning_flags(output_mode_from_arg(mode))

    # Then
    assert result == expected


def test_validate_conversations_folder_accepts_known_export_shape(tmp_path: Path) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "user", SEARCH_STRING, parent="root")),
    )

    # When
    report = validate_conversations_folder(export_dir)
    summary = validation_summary(report)

    # Then
    assert report.files_scanned == 1
    assert report.conversations_scanned == 1
    assert report.messages_scanned == 1
    assert "Export validation passed" in summary


def test_validate_conversations_folder_accepts_known_truncated_marker_artifacts(
    tmp_path: Path,
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    known_artifact_text = (
        f"known alternate marker {ALT_TERMINATED_MARKER} and "
        f"known truncated marker {TRUNCATED_CITATION_MARKER}"
    )
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "assistant", known_artifact_text, parent="root")),
    )

    # When
    report = validate_conversations_folder(export_dir)

    # Then
    assert report.marker_kinds["navlist"] == 1
    assert report.marker_kinds["cite"] == 1


def test_validate_conversations_folder_accepts_known_private_use_glyphs(
    tmp_path: Path,
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(
        export_dir,
        minimal_conversation(
            message(
                "leaf",
                "assistant",
                f"{LEGACY_CITATION_GLYPHS} {PRIVATE_ICON_GLYPHS}",
                parent="root",
            )
        ),
    )

    # When
    report = validate_conversations_folder(export_dir)

    # Then
    assert report.messages_scanned == 1
    assert report.issues == []


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ("not a conversation export", "top_level_shape"),
        ({"conversations": "not a list"}, "conversations_shape"),
        (["not an object"], "conversation_shape"),
    ],
)
def test_validate_conversations_folder_fails_for_invalid_top_level_shapes(
    tmp_path: Path, payload: object, expected_code: str
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_raw_export(export_dir, payload)

    # When
    def validate_fixture() -> None:
        validate_conversations_folder(export_dir)

    # Then
    with pytest.raises(ExportValidationError) as error:
        validate_fixture()
    assert expected_code in validation_error_codes(error.value)


def test_validate_conversations_folder_fails_for_invalid_json(tmp_path: Path) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    export_dir.mkdir()
    (export_dir / "conversations-000.json").write_text("{not-json", encoding="utf-8")

    # When
    def validate_fixture() -> None:
        validate_conversations_folder(export_dir)

    # Then
    with pytest.raises(ExportValidationError) as error:
        validate_fixture()
    assert "json_decode" in validation_error_codes(error.value)


@pytest.mark.parametrize(
    ("conversation", "expected_code"),
    [
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "content": {"content_type": "future_type", "parts": ["hello"]},
                    },
                }
            ),
            "unknown_content_type",
        ),
        (
            minimal_conversation(
                message(
                    "leaf",
                    "user",
                    "hello \ue200futuremarker\ue202payload\ue201",
                    parent="root",
                )
            ),
            "unknown_marker_kind",
        ),
        (
            {
                "title": "Bad graph",
                "id": "bad-graph",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["missing"]),
                    "leaf": message("leaf", "user", "hello", parent="root"),
                },
            },
            "child_reference",
        ),
        (
            {
                "title": "Bad mapping",
                "id": "bad-mapping",
                "mapping": "not a mapping",
            },
            "mapping_shape",
        ),
        (
            {
                "title": "Bad current node",
                "id": "bad-current-node",
                "current_node": "missing",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": message("leaf", "user", "hello", parent="root"),
                },
            },
            "current_node_reference",
        ),
        (
            {
                "title": "Bad parent",
                "id": "bad-parent",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": message("leaf", "user", "hello", parent="missing"),
                },
            },
            "parent_reference",
        ),
        (
            {
                "title": "Bad node",
                "id": "bad-node",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": "not a node",
                },
            },
            "node_shape",
        ),
        (
            {
                "title": "Bad children",
                "id": "bad-children",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": {
                        "id": "leaf",
                        "parent": "root",
                        "children": "not a list",
                        "message": {
                            "id": "leaf",
                            "author": {"role": "user"},
                            "create_time": 1_770_000_000,
                            "status": "finished_successfully",
                            "channel": "final",
                            "content": {"content_type": "text", "parts": ["hello"]},
                        },
                    },
                },
            },
            "children_shape",
        ),
        (
            {
                "title": "Bad message",
                "id": "bad-message",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": {
                        "id": "leaf",
                        "parent": "root",
                        "children": [],
                        "message": "not a message",
                    },
                },
            },
            "message_shape",
        ),
        (
            {
                "title": "Bad timestamp",
                "id": "bad-timestamp",
                "current_node": "leaf",
                "create_time": "not numeric",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": message("leaf", "user", "hello", parent="root"),
                },
            },
            "timestamp_shape",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "final",
                        "content": "not content",
                    },
                }
            ),
            "message_content_shape",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "final",
                        "content": {"parts": ["hello"]},
                    },
                }
            ),
            "content_type_shape",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "future-channel",
                        "content": {"content_type": "text", "parts": ["hello"]},
                    },
                }
            ),
            "unknown_channel",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "future-status",
                        "channel": "final",
                        "content": {"content_type": "text", "parts": ["hello"]},
                    },
                }
            ),
            "unknown_status",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "final",
                        "content": {"content_type": "text", "parts": ["hello"]},
                        "metadata": {"content_references": "not a list"},
                    },
                }
            ),
            "content_references_shape",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "final",
                        "content": {"content_type": "text", "parts": ["hello"]},
                        "metadata": {"content_references": ["not a reference"]},
                    },
                }
            ),
            "content_reference_shape",
        ),
        (
            minimal_conversation(
                {
                    "id": "leaf",
                    "parent": "root",
                    "children": [],
                    "message": {
                        "id": "leaf",
                        "author": {"role": "user"},
                        "create_time": 1_770_000_000,
                        "status": "finished_successfully",
                        "channel": "final",
                        "content": {"content_type": "text", "parts": ["hello"]},
                        "metadata": {
                            "content_references": [{"type": "future_reference"}]
                        },
                    },
                }
            ),
            "unknown_reference_type",
        ),
        (
            minimal_conversation(
                message("leaf", "user", "hello \ue200", parent="root")
            ),
            "malformed_marker",
        ),
    ],
)
def test_validate_conversations_folder_fails_loudly_for_unknown_or_bad_shapes(
    tmp_path: Path, conversation: dict[str, object], expected_code: str
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(export_dir, conversation)

    # When
    def validate_fixture() -> None:
        validate_conversations_folder(export_dir)

    # Then
    with pytest.raises(ExportValidationError) as error:
        validate_fixture()
    assert expected_code in validation_error_codes(error.value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"valid": 1}, {"valid": 1}),
        ({1: "invalid"}, None),
        ("invalid", None),
    ],
)
def test_as_string_keyed_dict_validates_shapes(
    value: object, expected: dict[str, object] | None
) -> None:
    # Given
    candidate = value

    # When
    result = as_string_keyed_dict(candidate)

    # Then
    assert result == expected


@pytest.mark.parametrize(
    ("haystack", "needle", "ignore_case", "expected"),
    [
        ("Alpha", "alpha", True, True),
        ("Alpha", "alpha", False, False),
    ],
)
def test_contains_honors_case_sensitivity(
    haystack: str, needle: str, ignore_case: bool, expected: bool
) -> None:
    # Given
    search_text = haystack

    # When
    result = contains(search_text, needle, ignore_case)

    # Then
    assert result is expected


@pytest.mark.parametrize(
    ("value", "fallback", "expected"),
    [
        (" Hello, World! ", "conversation", "hello-world"),
        ("!!!", "fallback", "fallback"),
    ],
)
def test_safe_filename_part_normalizes_values(
    value: str, fallback: str, expected: str
) -> None:
    # Given
    raw_filename_part = value

    # When
    result = safe_filename_part(raw_filename_part, fallback=fallback)

    # Then
    assert result == expected


def test_string_iteration_escaping_and_unique_paths(tmp_path: Path) -> None:
    # Given
    nested_strings = {"a": ["one", {"b": "two"}], "c": 3}
    existing_path = tmp_path / "result.md"
    existing_path.write_text("existing", encoding="utf-8")

    # When
    strings = list(iter_strings(nested_strings))
    escaped = markdown_escape_inline("a`b")

    # Then
    assert strings == ["one", "two"]
    assert escaped == "a\\`b"
    assert unique_path(existing_path) == tmp_path / "result-2.md"
    assert unique_path(tmp_path / "new.md") == tmp_path / "new.md"


@pytest.mark.parametrize(
    ("value", "expected_prefix"),
    [
        (None, ""),
        (1_770_000_000, "2026-02-02T02:40:00"),
        (1_770_000_000_000, "2026-02-02T02:40:00"),
        (1_770_000_000_000_000_000, "2026-02-02T02:40:00"),
        (float("inf"), "inf"),
    ],
)
def test_timestamp_to_iso_handles_units_and_invalid_values(
    value: object, expected_prefix: str
) -> None:
    # Given
    timestamp_value = value

    # When
    result = timestamp_to_iso(timestamp_value)

    # Then
    assert result.startswith(expected_prefix)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "0000-00-00T00-00-00.000000Z"),
        (1_770_000_000, "2026-02-02T02-40-00.000000Z"),
        (1_770_000_000.123456, "2026-02-02T02-40-00.123456Z"),
        (1_770_000_000_000, "2026-02-02T02-40-00.000000Z"),
        (1_770_000_000_000_000_000, "2026-02-02T02-40-00.000000Z"),
        (float("inf"), "0000-00-00T00-00-00.000000Z"),
    ],
)
def test_timestamp_for_filename_handles_units_and_invalid_values(
    value: object, expected: str
) -> None:
    # Given
    timestamp_value = value

    # When
    result = timestamp_for_filename(timestamp_value)

    # Then
    assert result == expected


def test_branch_timestamp_prefers_leaf_update_then_create_then_conversation() -> None:
    # Given
    timestamp_node = message(
        "leaf",
        "assistant",
        "leaf with update time",
        update_time=1_770_000_123.456789,
    )
    timestamp_mapping: dict[str, object] = {"leaf": timestamp_node}
    conversation: dict[str, object] = {"update_time": 1_770_000_100}

    # When
    leaf_payload = timestamp_node["message"]

    # Then
    assert node_message(timestamp_mapping, "leaf") is not None
    assert node_message(timestamp_mapping, "missing") is None
    assert branch_timestamp_value(timestamp_mapping, ["leaf"], conversation) == (
        1_770_000_123.456789
    )
    assert isinstance(leaf_payload, dict)
    leaf_payload.pop("update_time")
    assert branch_timestamp_value(timestamp_mapping, ["leaf"], conversation) == 1_770_000_000
    leaf_payload.pop("create_time")
    assert branch_timestamp_value(timestamp_mapping, ["leaf"], conversation) == 1_770_000_100
    assert branch_timestamp_value(timestamp_mapping, [], conversation) == 1_770_000_100


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("# Title\n### Detail\n", "### Title\n##### Detail\n"),
        ("```md\n# Not demoted\n```\n# Demoted\n", "```md\n# Not demoted\n```\n### Demoted\n"),
        ("~~~md\n# Not demoted\n~~~\n# Demoted\n", "~~~md\n# Not demoted\n~~~\n### Demoted\n"),
        ("Use C# and issue #123.\n", "Use C# and issue #123.\n"),
        ("#tag is not a heading\n", "#tag is not a heading\n"),
        ("\\# escaped heading\n", "\\# escaped heading\n"),
        ("    # indented code comment\n", "    # indented code comment\n"),
        ("> # Quoted heading\n", "> ### Quoted heading\n"),
        ("> > ## Nested quoted heading\n", "> > #### Nested quoted heading\n"),
        ("- # List heading\n1. ## Ordered heading\n", "- ### List heading\n1. #### Ordered heading\n"),
        ("###### Max heading\n", "###### Max heading\n"),
        ("# comment\nprint('hello')\n", "# comment\nprint('hello')\n"),
        ("I use C# for issue #123.\n# Real heading\n", "I use C# for issue #123.\n### Real heading\n"),
    ],
)
def test_markdown_heading_demotions_preserve_code_and_hash_edges(
    source: str, expected: str
) -> None:
    # Given
    markdown = source

    # When
    result = demote_markdown_headings(markdown)

    # Then
    assert result == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("# comment\nprint('hello')\n", True),
        ("#!/usr/bin/env bash\n# comment\necho hi\n", True),
        ("// comment\nconst value = 1;\n", True),
        ("# Heading\nThis is prose.\n", False),
    ],
)
def test_raw_code_detection_handles_common_cases(source: str, expected: bool) -> None:
    # Given
    text = source

    # When
    result = looks_like_raw_code(text)

    # Then
    assert result is expected


def citation_message() -> dict[str, object]:
    return {
        "content": {
            "content_type": "text",
            "parts": [
                (
                    f"Claim {CITATION_MARKER} missing {UNRESOLVED_CITATION_MARKER} "
                    f"file {FILE_CITATION_MARKER} entity {ENTITY_MARKER} orphan "
                    f"{ORPHAN_LINE_MARKER}"
                )
            ],
        },
        "metadata": {
            "content_references": [
                {
                    "matched_text": CITATION_MARKER,
                    "items": [
                        {
                            "title": "Primary Source",
                            "attribution": "Example Docs",
                            "url": "https://example.com/source?utm_source=chatgpt.com",
                            "supporting_websites": [
                                {
                                    "title": "Supporting Source",
                                    "attribution": "Example",
                                    "url": "https://example.com/support?utm_medium=test",
                                }
                            ],
                        }
                    ],
                },
                {
                    "matched_text": FILE_CITATION_BASE_MARKER,
                    "type": "file",
                    "name": "SYNTHETIC.md",
                },
            ]
        },
    }


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        (None, ""),
        ("plain", "plain"),
        ({"asset_pointer": "file-abc"}, "[Attachment: file-abc]"),
        ({"file_id": "file-def"}, "[File: file-def]"),
        ({"content_type": "custom", "items": ["nested"]}, "nested"),
        (["one", {"text": "two"}], "one\ntwo"),
        (12, "12"),
    ],
)
def test_render_part_handles_common_export_shapes(part: object, expected: str) -> None:
    # Given
    export_part = part

    # When
    result = render_part(export_part)

    # Then
    assert result == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"content": "loose content"}, "loose content"),
        ({"content": {"content_type": "text", "parts": "# single part"}}, "### single part"),
        ({"content": {"content_type": "text", "parts": "# comment\nx = 1\nprint(x)"}}, "# comment\nx = 1\nprint(x)"),
        ({"content": {"content_type": "text", "text": "text field"}}, "text field"),
        ({"content": {"content_type": "text", "other": ["fallback"]}}, "fallback"),
    ],
)
def test_message_to_markdown_handles_text_content_shapes(
    payload: dict[str, object], expected: str
) -> None:
    # Given
    message_payload = payload

    # When
    result = message_to_markdown(message_payload)

    # Then
    assert result == expected


def test_code_messages_and_marker_cleanup_render_readably() -> None:
    # Given
    py_code: dict[str, object] = {
        "content": {"content_type": "code", "language": "py", "text": "print('x')"}
    }
    py_code_parts: dict[str, object] = {
        "content": {"content_type": "code", "language": "py", "parts": ["print('x')"]}
    }
    bash_code: dict[str, object] = {
        "content": {
            "content_type": "code",
            "language": "bash",
            "text": "# comment\necho hi",
        }
    }
    citation_payload = citation_message()
    malformed_marker_payload: dict[str, object] = {
        "content": {
            "content_type": "text",
            "parts": [
                (
                    f"Before {ALT_TERMINATED_MARKER} middle "
                    f"{TRUNCATED_CITATION_MARKER} after"
                )
            ],
        }
    }
    private_glyph_payload: dict[str, object] = {
        "content": {
            "content_type": "text",
            "parts": [f"{LEGACY_CITATION_GLYPHS} {PRIVATE_ICON_GLYPHS}"],
        }
    }

    # When
    citation_body = message_to_markdown(citation_payload)
    code_with_hash = message_to_markdown(bash_code)
    malformed_marker_body = message_to_markdown(malformed_marker_payload)
    private_glyph_body = message_to_markdown(private_glyph_payload)

    # Then
    assert "````" in fenced_block("```nested```")
    assert "python" in fenced_block("print('ok')", "python!")
    assert message_to_markdown(py_code).startswith("```py")
    assert message_to_markdown(py_code_parts).startswith("```py")
    assert "# comment" in code_with_hash
    assert "### comment" not in code_with_hash
    assert role_label({}) == "Message"
    assert role_label({"author": {"role": "assistant", "name": "tool"}}) == "Assistant (tool)"
    assert clean_url("https://example.com/page?utm_source=chatgpt.com&srsltid=abc&a=1") == (
        "https://example.com/page?a=1"
    )
    assert clean_url("https://example.com/[broken") == "https://example.com/[broken"
    assert compact_whitespace(" Title\n\n  with   spaces ") == "Title with spaces"
    assert CITATION_MARKER not in citation_body
    assert UNRESOLVED_CITATION_MARKER not in citation_body
    assert FILE_CITATION_MARKER not in citation_body
    assert ENTITY_MARKER not in citation_body
    assert ORPHAN_LINE_MARKER not in citation_body
    assert_no_private_markers(citation_body)
    assert "[Primary Source (Example Docs)](https://example.com/source)" in citation_body
    assert "[Supporting Source (Example)](https://example.com/support)" in citation_body
    assert "(File: `SYNTHETIC.md`, lines 8-12)" in citation_body
    assert "Synthetic Linux" in citation_body
    assert "Synthetic topic" not in malformed_marker_body
    assert "turn0" not in malformed_marker_body
    assert_no_private_markers(malformed_marker_body)
    assert "Synthetic sourced sentence" in private_glyph_body
    assert "Location: Synthetic place" in private_glyph_body
    assert "Phone: +00 000 000" in private_glyph_body
    assert "Email: user@example.test" in private_glyph_body
    assert "Link: https://example.test" in private_glyph_body
    assert "Apple menu settings" in private_glyph_body
    assert "Synthetic event -  Talk" in private_glyph_body
    assert_no_private_markers(private_glyph_body)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "[Example](https://example.com/page?utm_source=x&srsltid=y&a=1)",
            "[Example](https://example.com/page?a=1)",
        ),
        (
            "```md\n[Keep](https://example.com/page?utm_source=x&a=1)\n```",
            "```md\n[Keep](https://example.com/page?utm_source=x&a=1)\n```",
        ),
        (
            "![Image](https://example.com/image.png?utm_source=x)",
            "![Image](https://example.com/image.png?utm_source=x)",
        ),
    ],
)
def test_clean_markdown_link_urls_removes_tracking_outside_code(
    source: str, expected: str
) -> None:
    # Given
    markdown = source

    # When
    result = clean_markdown_link_urls(markdown)

    # Then
    assert result == expected


def test_graph_and_branch_rendering_skip_invalid_hidden_and_empty_nodes(tmp_path: Path) -> None:
    # Given
    hidden_message = message("hidden", "assistant", "hidden text", content_type="text")
    hidden_payload = hidden_message["message"]
    assert isinstance(hidden_payload, dict)
    hidden_payload["metadata"] = {"is_visually_hidden_from_conversation": True}
    mapping: dict[str, object] = {
        "bad": "not a node",
        "no-message": {"children": []},
        "root": root_node(["match"]),
        "match": message(
            "match",
            "user",
            SEARCH_STRING,
            parent="root",
            children=["child"],
        ),
        "child": {"id": "child", "parent": "match", "children": "not-list", "message": None},
        "hidden": hidden_message,
    }

    # When
    markdown = render_branch_markdown(
        conversation={
            "title": "Render edges",
            "id": "render-id",
            "current_node": "match",
            "mapping": {
                "missing-node": "invalid",
                "empty": {"message": {"author": {"role": "assistant"}, "content": {"parts": []}}},
                "match": message("match", "user", SEARCH_STRING),
            },
        },
        source_file=tmp_path / "conversations-000.json",
        branch_index=1,
        branch_count=1,
        path=["missing-node", "empty", "match"],
        matching_ids=["match"],
        search_string=SEARCH_STRING,
        include_reasoning=False,
    )

    # Then
    assert matching_node_ids(mapping, SEARCH_STRING, ignore_case=False) == ["match"]
    assert node_children(mapping, "missing") == []
    assert node_children(mapping, "child") == []
    assert leaf_node_ids({"only": {"children": ["only"]}}, "only") == ["only"]
    assert matching_branch_paths({"match": {"parent": None, "children": ["match"]}}, None, ["match"]) == [
        ["match"]
    ]
    assert "Render edges" in markdown
    assert "[MATCH]" in markdown


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("```py\nprint('open')\n", True),
        ("```py\nprint('closed')\n```\n", False),
        ("~~~sh\necho open\n", True),
        ("~~~sh\necho closed\n~~~~\n", False),
    ],
)
def test_markdown_output_helper_detects_unclosed_fences(
    source: str, expected: bool
) -> None:
    # Given
    markdown = source

    # When
    result = markdown_has_unclosed_fence(markdown)

    # Then
    assert result is expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("```tsx\n<Kbd>Tab</K", "```tsx\n<Kbd>Tab</K\n```"),
        ("~~~sh\necho hello\n", "~~~sh\necho hello\n~~~"),
        ("```py\nprint('ok')\n```\n", "```py\nprint('ok')\n```\n"),
    ],
)
def test_close_unclosed_markdown_fence_closes_message_boundary(
    source: str, expected: str
) -> None:
    # Given
    markdown = source

    # When
    result = close_unclosed_markdown_fence(markdown)

    # Then
    assert result == expected
    assert active_markdown_fence(result) is None


def test_render_branch_markdown_closes_unclosed_message_fence_before_next_header(
    tmp_path: Path,
) -> None:
    # Given
    conversation: dict[str, object] = {
        "title": "Unclosed fence fixture",
        "id": "unclosed-fence",
        "current_node": "assistant",
        "mapping": {
            "root": root_node(["user"]),
            "user": message(
                "user",
                "user",
                "```tsx\n<TableCell>\n  <Kbd>Tab</K",
                parent="root",
                children=["assistant"],
            ),
            "assistant": message("assistant", "assistant", "after fence", parent="user"),
        },
    }

    # When
    markdown = render_branch_markdown(
        conversation=conversation,
        source_file=tmp_path / "conversations-000.json",
        branch_index=1,
        branch_count=1,
        path=["user", "assistant"],
        matching_ids=[],
        search_string=None,
        include_reasoning=False,
    )

    # Then
    assert markdown_has_unclosed_fence(markdown) is False
    assert "\n```\n\n## Assistant" in markdown


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Conversation ID", "- Conversation ID: `conv`"),
        ("Missing", ""),
    ],
)
def test_output_file_metadata_finds_expected_header_lines(
    label: str, expected: str
) -> None:
    # Given
    markdown = base_markdown(reasoning=False)

    # When
    result = output_file_metadata(markdown, label)

    # Then
    assert result == expected


def test_validate_markdown_output_files_accepts_valid_normal_reasoning_pair(
    tmp_path: Path,
) -> None:
    # Given
    written = write_markdown_validation_pair(
        tmp_path / "out",
        base_markdown(reasoning=False),
        base_markdown(reasoning=True),
    )

    # When
    validate_markdown_output_files(written)

    # Then
    assert all(path.exists() for path in written)


@pytest.mark.parametrize(
    ("output_mode", "expected_message"),
    [
        ("normal", "unexpected reasoning file for normal output mode"),
        ("reasoning", "unexpected normal file for reasoning output mode"),
    ],
)
def test_validate_markdown_output_files_rejects_wrong_output_mode_files(
    tmp_path: Path, output_mode: str, expected_message: str
) -> None:
    # Given
    written = write_markdown_validation_pair(
        tmp_path / "out",
        base_markdown(reasoning=False),
        base_markdown(reasoning=True),
    )

    # When
    def validate_outputs() -> None:
        validate_markdown_output_files(
            written,
            output_mode=output_mode_from_arg(output_mode),
        )

    # Then
    with pytest.raises(RuntimeError, match=re.escape(expected_message)):
        validate_outputs()


def test_validate_markdown_output_files_can_skip_match_requirement(
    tmp_path: Path,
) -> None:
    # Given
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    normal_path = output_dir / "all-mode.md"
    normal_path.write_text(
        base_markdown(reasoning=False).replace(" [MATCH]", ""),
        encoding="utf-8",
    )

    # When
    validate_markdown_output_files(
        [normal_path],
        require_match=False,
        output_mode="normal",
    )

    # Then
    assert normal_path.exists()


@pytest.mark.parametrize(
    ("case", "expected_message"),
    [
        ("missing_newline", "missing final newline"),
        ("raw_marker", "raw ChatGPT marker glyph remains"),
        ("unclosed_fence", "unclosed Markdown code fence"),
        ("missing_match", "missing [MATCH] marker"),
        ("reasoning_leak", "normal transcript includes reasoning marker"),
        ("reasoning_header", "reasoning transcript missing reasoning header"),
        ("metadata_mismatch", "paired reasoning metadata mismatch"),
        ("missing_pair", "missing paired reasoning file"),
    ],
)
def test_validate_markdown_output_files_fails_for_bad_outputs(
    tmp_path: Path, case: str, expected_message: str
) -> None:
    # Given
    normal_text = base_markdown(reasoning=False)
    reasoning_text = base_markdown(reasoning=True)
    if case == "missing_newline":
        normal_text = normal_text.rstrip("\n")
    elif case == "raw_marker":
        normal_text = normal_text + "\ue200"
    elif case == "unclosed_fence":
        normal_text = normal_text + "```py\nprint('oops')\n"
    elif case == "missing_match":
        normal_text = normal_text.replace(" [MATCH]", "")
    elif case == "reasoning_leak":
        normal_text = normal_text + "[REASONING TRACE]\n"
    elif case == "reasoning_header":
        reasoning_text = reasoning_text.replace(
            "- Reasoning traces included: `yes`\n", ""
        )
    elif case == "metadata_mismatch":
        reasoning_text = reasoning_text.replace(
            "- Branch: `1 of 1`\n", "- Branch: `2 of 2`\n"
        )
    written = write_markdown_validation_pair(
        tmp_path / "out", normal_text, reasoning_text
    )
    if case == "missing_pair":
        written = [written[0]]

    # When
    def validate_outputs() -> None:
        validate_markdown_output_files(written)

    # Then
    with pytest.raises(RuntimeError, match=re.escape(expected_message)):
        validate_outputs()


def test_validation_error_summary_limits_long_issue_lists(tmp_path: Path) -> None:
    # Given
    report = ValidationReport()
    for index in range(11):
        report.add_issue(
            tmp_path / "conversations-000.json",
            "synthetic_issue",
            f"issue {index}",
            conversation_index=index,
        )

    # When
    summary = validation_error_summary(report)

    # Then
    assert "issue 0" in summary
    assert "issue 10" not in summary
    assert "... and 1 more validation issue(s)" in summary


@pytest.mark.parametrize(
    ("folder_name", "create_folder"),
    [
        ("missing", False),
        ("empty", True),
    ],
)
def test_write_markdown_files_reports_missing_input_errors(
    tmp_path: Path, folder_name: str, create_folder: bool
) -> None:
    # Given
    conversations_dir = tmp_path / folder_name
    output_dir = tmp_path / "out"
    if create_folder:
        conversations_dir.mkdir()

    # When
    def write_missing_export() -> None:
        write_markdown_files(conversations_dir, output_dir, SEARCH_STRING, ignore_case=False)

    # Then
    with pytest.raises(FileNotFoundError):
        write_missing_export()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("not conversations", []),
        ({"id": "one"}, [{"id": "one"}]),
    ],
)
def test_load_conversations_handles_invalid_and_single_shapes(
    tmp_path: Path, payload: object, expected: list[dict[str, object]]
) -> None:
    # Given
    export_file = tmp_path / "conversations.json"
    export_file.write_text(json.dumps(payload), encoding="utf-8")

    # When
    result = load_conversations(export_file)

    # Then
    assert result == expected


def test_main_returns_error_for_missing_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    missing_dir = tmp_path / "missing"
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        "sys.argv",
        [
            "extract_chatgpt_markdown.py",
            str(missing_dir),
            SEARCH_STRING,
            str(output_dir),
        ],
    )

    # When
    exit_code = main()

    # Then
    assert exit_code == 1


def test_main_returns_error_when_extract_args_are_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "user", SEARCH_STRING, parent="root")),
    )
    monkeypatch.setattr("sys.argv", ["extract_chatgpt_markdown.py", str(export_dir)])

    # When
    exit_code = main()

    # Then
    assert exit_code == 1


def test_main_validate_only_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "user", SEARCH_STRING, parent="root")),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["extract_chatgpt_markdown.py", str(export_dir), "--validate-only"],
    )

    # When
    exit_code = main()

    # Then
    assert exit_code == 0


@pytest.mark.parametrize(
    "argv_suffix",
    [
        ["--all"],
        ["--all", "ambiguous-output-folder"],
    ],
)
def test_main_all_mode_requires_named_output_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv_suffix: list[str]
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    write_validation_export(
        export_dir,
        minimal_conversation(message("leaf", "user", "hello", parent="root")),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["extract_chatgpt_markdown.py", str(export_dir), *argv_suffix],
    )

    # When
    exit_code = main()

    # Then
    assert exit_code == 1


def test_main_all_mode_success_with_named_output_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    write_export(export_dir, [branching_conversation_without_search_match()])
    monkeypatch.setattr(
        "sys.argv",
        [
            "extract_chatgpt_markdown.py",
            str(export_dir),
            "--all",
            "--output-folder",
            str(output_dir),
            "--output-mode",
            "normal",
        ],
    )

    # When
    exit_code = main()

    # Then
    assert exit_code == 0
    assert len(list(output_dir.glob("*.md"))) == 2
    assert not list(output_dir.glob("*-reasoning.md"))


def test_main_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    export_dir = tmp_path / "Conversations"
    output_dir = tmp_path / "out"
    write_export(
        export_dir,
        [
            {
                "title": "CLI success",
                "id": "cli-conv",
                "current_node": "leaf",
                "mapping": {
                    "root": root_node(["leaf"]),
                    "leaf": message("leaf", "user", SEARCH_STRING, parent="root"),
                },
            }
        ],
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "extract_chatgpt_markdown.py",
            str(export_dir),
            SEARCH_STRING,
            str(output_dir),
        ],
    )

    # When
    exit_code = main()

    # Then
    assert exit_code == 0
