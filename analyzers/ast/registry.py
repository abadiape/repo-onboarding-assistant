"""Language parser registry."""
from __future__ import annotations

from analyzers.ast.parser import Parser
from analyzers.ast.python import PythonParser


class ParserRegistry:
    def __init__(self, parsers: tuple[Parser, ...] = ()) -> None:
        self._parsers: dict[str, Parser] = {}
        for parser in parsers:
            self.register(parser)

    def register(self, parser: Parser) -> None:
        for extension in parser.extensions:
            if extension.lower() in self._parsers:
                raise ValueError(f"Parser already registered for {extension}")
            self._parsers[extension.lower()] = parser

    def for_path(self, path: str) -> Parser | None:
        from pathlib import Path

        return self._parsers.get(Path(path).suffix.lower())


DEFAULT_REGISTRY = ParserRegistry((PythonParser(),))
