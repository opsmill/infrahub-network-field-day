"""`.env` writes replace an entry and its comment, and never grow on a re-mint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solution_arista_avd.envfile import read_env, upsert_env

if TYPE_CHECKING:
    from pathlib import Path


def test_a_missing_file_reads_empty_and_is_created(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    assert not read_env(env, "TOKEN")

    upsert_env(env, "TOKEN", "abc", "The token.")

    assert env.read_text() == "# The token.\nTOKEN=abc\n"
    assert read_env(env, "TOKEN") == "abc"


def test_re_minting_replaces_the_value_and_its_comment(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("KEEP=1\n\n# The token.\nTOKEN=old\n\n# Other.\nOTHER=2\n")

    upsert_env(env, "TOKEN", "new", "The token.")
    upsert_env(env, "TOKEN", "newer", "The token.")

    text = env.read_text()
    assert text.count("# The token.") == 1
    assert "TOKEN=old" not in text
    assert read_env(env, "TOKEN") == "newer"
    assert read_env(env, "KEEP") == "1"
    assert read_env(env, "OTHER") == "2"
    assert "\n\n\n" not in text


def test_comments_an_earlier_writer_orphaned_are_cleaned_up(tmp_path: Path) -> None:
    """The shape the live `.env` had reached: two comments with no value under them."""
    env = tmp_path / ".env"
    env.write_text("# The token.\n\n# The token.\n\nA=1\n\n# The token.\nTOKEN=x\n")

    upsert_env(env, "TOKEN", "y", "The token.")

    assert env.read_text() == "A=1\n\n# The token.\nTOKEN=y\n"
