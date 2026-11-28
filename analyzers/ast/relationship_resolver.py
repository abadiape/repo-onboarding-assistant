"""Evidence-backed Python relationship resolution over parsed repository files."""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from analyzers.ast.parser import Import, ParseResult
from models.symbols import Evidence, Relationship, Symbol

Declaration = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def _expression(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expression(node.value)
        return f"{prefix}.{node.attr}" if prefix else ""
    if isinstance(node, (ast.Call, ast.Subscript)):
        return _expression(node.func if isinstance(node, ast.Call) else node.value)
    return ""


def _static_reference(node: ast.AST, *, generic: bool = False) -> bool:
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Attribute):
        return _static_reference(node.value)
    if generic and isinstance(node, ast.Subscript):
        return _static_reference(node.value, generic=True)
    return False


class Context:
    def __init__(
        self, path: str, result: ParseResult, symbols: list[Symbol], by_id: dict[str, Symbol],
        children: dict[tuple[str, str], list[Symbol]],
        imports: list[tuple[Import, Relationship]],
    ) -> None:
        assert isinstance(result.syntax_tree, ast.Module)
        self.path, self.tree, self.lines = path, result.syntax_tree, result.source_lines
        self.by_id = by_id
        self.module_id = f"python:module:{path}"
        self.scope: dict[ast.AST, str] = {}
        self.declarations: dict[ast.AST, Symbol] = {}
        self.bindings: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        self.imports = [(item, rel) for item, rel in imports if item.evidence.path == path]
        self.children = children
        for symbol in symbols:
            if symbol.kind in {"class", "function", "method"}:
                self.bindings[symbol.parent_symbol_id or ""][symbol.qualified_name.rsplit(".", 1)[-1]].add(symbol.id)
        locations = {
            (symbol.start_line, symbol.evidence[0].column): symbol
            for symbol in symbols if symbol.kind in {"class", "function", "method"} and symbol.evidence
        }
        context = self

        class Index(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current = context.module_id

            def generic_visit(self, node: ast.AST) -> None:
                context.scope[node] = self.current
                super().generic_visit(node)

            def declaration(self, node: Declaration) -> None:
                context.scope[node] = self.current
                symbol = locations[(node.lineno, node.col_offset)]
                context.declarations[node] = symbol
                for decorator in node.decorator_list:
                    self.visit(decorator)
                for parameter in getattr(node, "type_params", ()):
                    self.visit(parameter)
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        self.visit(base)
                    for keyword in node.keywords:
                        self.visit(keyword.value)
                else:
                    arguments = node.args
                    for default in (*arguments.defaults, *arguments.kw_defaults):
                        if default is not None:
                            self.visit(default)
                    for argument in (
                        *arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                        arguments.vararg, arguments.kwarg,
                    ):
                        if argument is not None and argument.annotation is not None:
                            self.visit(argument.annotation)
                    if node.returns is not None:
                        self.visit(node.returns)
                previous = self.current
                self.current = symbol.id
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                        context.bindings[self.current][arg.arg].add("")
                    for arg in (node.args.vararg, node.args.kwarg):
                        if arg:
                            context.bindings[self.current][arg.arg].add("")
                for child in node.body:
                    self.visit(child)
                self.current = previous

            visit_ClassDef = declaration
            visit_FunctionDef = declaration
            visit_AsyncFunctionDef = declaration

            def visit_Name(self, node: ast.Name) -> None:
                context.scope[node] = self.current
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    context.bindings[self.current][node.id].add("")

            def visit_Lambda(self, node: ast.Lambda) -> None:
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    context.bindings[self.current][arg.arg].add("")
                for arg in (node.args.vararg, node.args.kwarg):
                    if arg:
                        context.bindings[self.current][arg.arg].add("")
                self.generic_visit(node)

        Index().visit(self.tree)
        for item, rel in self.imports:
            if item.name == "*":
                continue
            if item.name is not None:
                binding = item.alias or item.name
                self.bindings[item.source_id][binding].add(rel.target_id)
            elif item.alias or "." not in item.module:
                self.bindings[item.source_id][item.alias or item.module].add(rel.target_id)
            else:
                self.bindings[item.source_id][item.module].add(rel.target_id)
                self.bindings[item.source_id][item.module.split(".")[0]].add("")

    def evidence(self, node: ast.AST, detector: str) -> Evidence:
        line = getattr(node, "lineno", 1)
        return Evidence(self.path, line, getattr(node, "col_offset", 0), self.lines[line - 1], detector)

    def resolve(self, node: ast.AST, scope: str) -> str:
        name = _expression(node)
        if not name:
            return f"unresolved:python:{ast.unparse(node)}"
        original = name
        current: str | None = scope
        while current:
            bindings = self.bindings.get(current, {})
            prefix = name
            while prefix:
                if prefix in bindings:
                    candidates = bindings[prefix]
                    if len(candidates) != 1 or "" in candidates:
                        return f"unresolved:python:{original}"
                    target = next(iter(candidates))
                    rest = name[len(prefix):].lstrip(".")
                    for part in rest.split(".") if rest else ():
                        if target.startswith("unresolved:python:"):
                            target += "." + part
                        else:
                            matches = self.children.get((target, part), [])
                            if len(matches) != 1:
                                return f"unresolved:python:{original}"
                            target = matches[0].id
                    return target
                prefix = prefix.rpartition(".")[0]
            symbol = self.by_id.get(current)
            parent = self.by_id.get(symbol.parent_symbol_id or "") if symbol else None
            if symbol and symbol.kind in {"function", "method"} and parent and parent.kind == "class":
                current = parent.parent_symbol_id
            else:
                current = symbol.parent_symbol_id if symbol else None
        return f"unresolved:python:{original}"


class RelationshipResolver(Protocol):
    def resolve(self, contexts: list[Context]) -> list[Relationship]: ...


class InheritanceResolver:
    def resolve(self, contexts: list[Context]) -> list[Relationship]:
        bases: list[tuple[Context, Symbol, ast.AST, str]] = []
        interfaces: dict[str, Evidence] = {}
        markers = {"unresolved:python:typing.Protocol", "unresolved:python:typing_extensions.Protocol",
                   "unresolved:python:abc.ABC", "unresolved:python:abc.ABCMeta"}
        for context in contexts:
            for node, symbol in context.declarations.items():
                if not isinstance(node, ast.ClassDef):
                    continue
                scope = context.scope[node]
                for base in node.bases:
                    target = (
                        f"unresolved:python:{ast.unparse(base)}"
                        if not _static_reference(base, generic=True) else context.resolve(base, scope)
                    )
                    resolved = context.by_id.get(target)
                    if resolved is not None and resolved.kind != "class":
                        target = f"unresolved:python:{ast.unparse(base)}"
                    bases.append((context, symbol, base, target))
                    if target in markers:
                        interfaces[symbol.id] = context.evidence(base, "python-ast-interface")
                for keyword in node.keywords:
                    if keyword.arg == "metaclass" and context.resolve(keyword.value, scope) in markers:
                        interfaces[symbol.id] = context.evidence(keyword.value, "python-ast-interface")
        return [
            Relationship(symbol.id, target, "IMPLEMENTS" if target in interfaces else "INHERITS",
                         0.85 if target in interfaces else 0.9, target not in interfaces,
                         [context.evidence(base, "python-ast-inheritance")]
                         + ([interfaces[target]] if target in interfaces else []))
            for context, symbol, base, target in bases
        ]


class DecoratorResolver:
    def resolve(self, contexts: list[Context]) -> list[Relationship]:
        result = []
        for context in contexts:
            for node, symbol in context.declarations.items():
                for decorator in node.decorator_list:
                    target = (
                        f"unresolved:python:{ast.unparse(decorator)}"
                        if not _static_reference(decorator)
                        else context.resolve(decorator, context.scope[node])
                    )
                    resolved = context.by_id.get(target)
                    if resolved is not None and resolved.kind not in {"class", "function", "method"}:
                        target = f"unresolved:python:{ast.unparse(decorator)}"
                    result.append(Relationship(
                        target, symbol.id, "DECORATES",
                        0.9, True, [context.evidence(decorator, "python-ast-decorator")],
                    ))
        return result


class RegistrationResolver:
    def resolve(self, contexts: list[Context]) -> list[Relationship]:
        result = []
        for context in contexts:
            for node in ast.walk(context.tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if not _static_reference(node.func.value):
                    continue
                receiver = _expression(node.func.value)
                if node.func.attr not in {"register", "add", "include_router"} or not receiver:
                    continue
                name = receiver.rsplit(".", 1)[-1].lower()
                if not any(name == part or name.endswith("_" + part) for part in ("registry", "container", "router")):
                    continue
                for argument in node.args:
                    if not _static_reference(argument):
                        continue
                    scope = context.scope[node]
                    result.append(Relationship(
                        context.resolve(node.func.value, scope), context.resolve(argument, scope),
                        "REGISTERS", 0.8, True, [context.evidence(node, "python-ast-registration")],
                    ))
        return result


class ExportResolver:
    def resolve(self, contexts: list[Context]) -> list[Relationship]:
        result = []
        for context in contexts:
            if Path(context.path).name != "__init__.py":
                continue
            module = context.by_id[context.module_id]
            if not module.parent_symbol_id:
                continue
            explicit: set[str] | None = None
            unknown = False
            for node in ast.walk(context.tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                        value = node.value
                        if explicit is not None or not isinstance(value, (ast.List, ast.Tuple)) or not all(
                            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts
                        ):
                            unknown = True
                        else:
                            explicit = {item.value for item in value.elts}
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (
                    isinstance(node.func.value, ast.Name) and node.func.value.id == "__all__"
                ):
                    unknown = True
            if unknown:
                continue
            imported_names = set()
            for item, relation in context.imports:
                if item.source_id != context.module_id or item.name == "*":
                    continue
                name = item.alias or item.name or item.module.split(".")[0]
                imported_names.add(name)
                if (explicit is not None and name not in explicit) or (explicit is None and name.startswith("_")):
                    continue
                target = relation.target_id
                if item.name is None and item.alias is None and "." in item.module:
                    target = f"unresolved:python:{name}"
                result.append(Relationship(
                    module.parent_symbol_id, target, "EXPORTS", 0.85, False,
                    [Evidence(item.evidence.path, item.evidence.line, item.evidence.column,
                              item.evidence.extract, "python-ast-export")],
                ))
            if explicit is not None:
                for name in sorted(explicit - imported_names):
                    matches = context.bindings[context.module_id].get(name, set())
                    target = next(iter(matches)) if len(matches) == 1 and "" not in matches else f"unresolved:python:{name}"
                    node = next((node for node in ast.walk(context.tree) if isinstance(node, ast.Name) and node.id == "__all__"), context.tree)
                    result.append(Relationship(
                        module.parent_symbol_id, target, "EXPORTS", 0.85, False,
                        [context.evidence(node, "python-ast-export")],
                    ))
        return result


class TestResolver:
    def resolve(self, contexts: list[Context]) -> list[Relationship]:
        result = []
        if not contexts:
            return result
        symbols = contexts[0].by_id

        def is_test_path(path: str) -> bool:
            parts = Path(path).parts
            return any(part in {"test", "tests"} for part in parts[:-1]) or Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py")

        def normalize(name: str) -> str:
            return "".join(char for char in name.lower() if char.isalnum())

        targets: dict[str, list[Symbol]] = defaultdict(list)
        for symbol in symbols.values():
            if symbol.kind in {"class", "function"} and not is_test_path(symbol.path):
                targets[normalize(symbol.qualified_name.rsplit(".", 1)[-1])].append(symbol)
        for context in contexts:
            filename = Path(context.path).stem
            if filename.startswith("test_") or filename.endswith("_test"):
                stem = filename[5:] if filename.startswith("test_") else filename[:-5]
                matches = targets.get(normalize(stem), [])
                if stem:
                    evidence = context.by_id[context.module_id].evidence[0]
                    result.append(Relationship(
                        context.module_id,
                        matches[0].id if len(matches) == 1 else f"unresolved:python:{stem}",
                        "TESTS", 0.5 if len(matches) == 1 else 0.25, False,
                        [Evidence(evidence.path, evidence.line, evidence.column, evidence.extract,
                                  "python-test-filename")],
                    ))
            for node, symbol in context.declarations.items():
                name = node.name
                lowered = name.lower()
                if not (name.startswith(("test_", "Test")) or name.endswith("Test")):
                    continue
                stem = name[4:] if lowered.startswith("test") else name[:-4]
                stem = stem.strip("_")
                if not stem:
                    continue
                matches = targets.get(normalize(stem), [])
                target = matches[0].id if len(matches) == 1 else f"unresolved:python:{stem}"
                result.append(Relationship(
                    symbol.id, target, "TESTS", 0.6 if len(matches) == 1 else 0.3, False,
                    [context.evidence(node, "python-test-name")],
                ))
                seen = {target}
                for reference in ast.walk(node):
                    if not isinstance(reference, ast.Name) or not isinstance(reference.ctx, ast.Load):
                        continue
                    resolved = context.resolve(reference, context.scope.get(reference, symbol.id))
                    candidate = symbols.get(resolved)
                    if candidate and candidate.kind in {"class", "function"} and not is_test_path(candidate.path) and resolved not in seen:
                        seen.add(resolved)
                        result.append(Relationship(
                            symbol.id, resolved, "TESTS", 0.8, False,
                            [context.evidence(reference, "python-test-reference")],
                        ))
        return result


def resolve_relationships(
    symbols: list[Symbol], parsed: list[tuple[str, ParseResult]],
    imports: list[tuple[Import, Relationship]],
) -> list[Relationship]:
    by_id = {symbol.id: symbol for symbol in symbols}
    by_path: dict[str, list[Symbol]] = defaultdict(list)
    children: dict[tuple[str, str], list[Symbol]] = defaultdict(list)
    imports_by_path: dict[str, list[tuple[Import, Relationship]]] = defaultdict(list)
    for symbol in symbols:
        by_path[symbol.path].append(symbol)
        if symbol.parent_symbol_id:
            children[(symbol.parent_symbol_id, symbol.qualified_name.rsplit(".", 1)[-1])].append(symbol)
    for item in imports:
        imports_by_path[item[0].evidence.path].append(item)
    contexts = [
        Context(path, result, by_path[path], by_id, children, imports_by_path[path])
        for path, result in parsed if isinstance(result.syntax_tree, ast.Module)
        and any(symbol.kind == "module" and symbol.language == "Python" for symbol in result.symbols)
    ]
    resolvers: tuple[RelationshipResolver, ...] = (
        InheritanceResolver(), DecoratorResolver(), RegistrationResolver(), TestResolver(), ExportResolver(),
    )
    return [relationship for resolver in resolvers for relationship in resolver.resolve(contexts)]
