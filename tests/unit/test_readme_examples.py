"""Every Python example in ``README.md`` compiles and type-checks against the SDK.

The README is the PyPI landing page, so an example that uses a changed API must
fail here rather than in a user's first copy. The blocks are compiled and
type-checked with mypy, never run: they create clients and call the API.

Each ``python`` block is checked as the body of an ``async def``, so a
fragment may ``await`` at its top level, as it would inside the reader's
coroutine. A block may use ``client``, an ``AsyncPolyester``, without creating
it: the README creates one first. Anything else a fragment uses without
defining it, such as an ID an earlier call returned, goes in an HTML comment
directly above the block, which renders as nothing and runs first::

    <!-- readme-setup
    sub_id = "Bht3tfQZv8E"
    -->

``pycon`` blocks are self-contained and need no network: they run as doctests.
"""

from __future__ import annotations

import ast
import doctest
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest
from mypy import api as mypy_api

README = Path(__file__).resolve().parents[2] / "README.md"
FENCE = re.compile(r"^```(?P<lang>\S*)\s*$")
SETUP = re.compile(r"<!-- readme-setup\n(?P<code>(?:(?!-->).)*)\n-->\s*$", re.DOTALL)
ERROR = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): error: (?P<message>.*)$")

PRELUDE = """\
from __future__ import annotations

from polyester import AsyncPolyester

client: AsyncPolyester
"""


@dataclass(frozen=True)
class Block:
    line: int  # README line of the first code line
    code: str
    setup: str


def _blocks(lang: str) -> list[Block]:
    lines = README.read_text().splitlines(keepends=True)
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        match = FENCE.match(lines[index])
        if match is None:
            index += 1
            continue
        end = index + 1
        while not lines[end].startswith("```"):
            end += 1
        if match["lang"] == lang:
            before = "".join(lines[max(0, index - 20) : index])
            setup = SETUP.search(before)
            blocks.append(
                Block(
                    line=index + 2,
                    code="".join(lines[index + 1 : end]),
                    setup=setup["code"] + "\n" if setup else "",
                )
            )
        index = end + 1
    return blocks


BLOCKS = _blocks("python")
DOCTESTS = _blocks("pycon")


def _module(block: Block) -> tuple[str, int]:
    """The block as a module, and the module line of the block's first line."""
    head = PRELUDE + "\n\nasync def _readme_example() -> None:\n"
    head += textwrap.indent(block.setup, "    ")
    return head + textwrap.indent(block.code, "    "), head.count("\n") + 1


def test_readme_has_python_examples() -> None:
    assert len(BLOCKS) > 30


@pytest.mark.parametrize("block", BLOCKS, ids=[f"README.md:{b.line}" for b in BLOCKS])
def test_readme_example_compiles(block: Block) -> None:
    compile(block.code, f"README.md:{block.line}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


def test_readme_examples_type_check(tmp_path: Path) -> None:
    starts: dict[str, tuple[Block, int]] = {}
    for block in BLOCKS:
        source, start = _module(block)
        name = f"readme_l{block.line:04d}.py"
        (tmp_path / name).write_text(source)
        starts[name] = (block, start)
    config = tmp_path / "mypy.ini"
    # Not the repository config: it skips imports, which would make the SDK Any.
    config.write_text("[mypy]\n")
    stdout, stderr, status = mypy_api.run(
        [
            "--config-file",
            str(config),
            "--follow-imports=silent",
            "--check-untyped-defs",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--no-error-summary",
            "--hide-error-context",
            *sorted(str(tmp_path / name) for name in starts),
        ]
    )
    assert status in (0, 1), stderr or stdout
    errors = []
    for line in stdout.splitlines():
        match = ERROR.match(line)
        if match is None:
            continue
        block, start = starts[Path(match["path"]).name]
        offset = int(match["line"]) - start
        where = block.line + offset if offset >= 0 else f"{block.line} (setup)"
        errors.append(f"README.md:{where}: {match['message']}")
    assert errors == [], "\n".join(errors)


def test_readme_has_doctests() -> None:
    assert DOCTESTS


@pytest.mark.parametrize("block", DOCTESTS, ids=[f"README.md:{b.line}" for b in DOCTESTS])
def test_readme_doctest(block: Block) -> None:
    name = f"README.md:{block.line}"
    test = doctest.DocTestParser().get_doctest(block.code, {}, name, str(README), block.line - 1)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    runner.run(test)
    result = runner.summarize(verbose=False)
    assert result.attempted > 0
    assert result.failed == 0
