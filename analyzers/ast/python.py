"""Python AST adapter."""
from __future__ import annotations

import ast
import logging
import tokenize
from pathlib import Path

from analyzers.ast.parser import Import, ParseResult
from models.symbols import Evidence, Relationship, Symbol

logger = logging.getLogger(__name__)


def module_name(path: str) -> str:
    parts = list(Path(path).with_suffix("").parts)
    if parts[-1] == "__init__" and len(parts) > 1:
        parts.pop()
    return ".".join(parts)


class PythonParser:
    language = "Python"
    extensions = (".py",)

    def parse(self, root: Path, path: str) -> ParseResult:
        result = ParseResult()
        try:
            resolved = (root / path).resolve()
            resolved.relative_to(root.resolve())
            with tokenize.open(resolved) as stream:
                source = stream.read()
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            logger.warning("Cannot read Python source %s: %s", path, exc)
            return result
        lines = source.splitlines()
        module = Symbol(
            id=f"python:module:{path}", qualified_name=module_name(path),
            kind="module", language=self.language, path=path, start_line=1,
            end_line=max(1, len(lines)), parent_symbol_id=None, visibility="public",
            evidence=[Evidence(path, 1, 0, lines[0] if lines else "", "python-ast")],
        )
        result.symbols.append(module)
        try:
            tree = ast.parse(source, filename=path)
        except (SyntaxError, ValueError, RecursionError) as exc:
            logger.warning("Cannot parse Python source %s: %s", path, exc)
            return result
        result.syntax_tree = tree
        result.source_lines = lines

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.parent = module

            def evidence(self, node: ast.AST) -> Evidence:
                line = node.lineno
                return Evidence(path, line, node.col_offset, lines[line - 1], "python-ast")

            def declaration(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                kind = "class" if isinstance(node, ast.ClassDef) else (
                    "method" if self.parent.kind == "class" else "function"
                )
                symbol = Symbol(
                    id=f"python:{kind}:{path}:{node.lineno}:{node.col_offset}",
                    qualified_name=f"{self.parent.qualified_name}.{node.name}",
                    kind=kind, language="Python", path=path, start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno, parent_symbol_id=self.parent.id,
                    visibility="private" if node.name.startswith("_") else "public",
                    evidence=[self.evidence(node)],
                )
                result.symbols.append(symbol)
                result.relationships.append(Relationship(
                    self.parent.id, symbol.id, "DECLARES", 1.0, True, symbol.evidence[:]
                ))
                previous = self.parent
                self.parent = symbol
                self.generic_visit(node)
                self.parent = previous

            visit_ClassDef = declaration
            visit_FunctionDef = declaration
            visit_AsyncFunctionDef = declaration

            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    result.imports.append(Import(
                        self.parent.id, alias.name, None, 0, self.evidence(node), alias.asname
                    ))

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                for alias in node.names:
                    result.imports.append(Import(
                        self.parent.id, node.module or "", alias.name, node.level,
                        self.evidence(node), alias.asname
                    ))

        Visitor().visit(tree)
        return result
