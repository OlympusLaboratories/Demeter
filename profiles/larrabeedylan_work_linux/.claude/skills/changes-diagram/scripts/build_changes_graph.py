#!/usr/bin/env python3
import argparse
import ast
import difflib
import json
import posixpath
import re
import subprocess
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

PY_ROOT = ""

TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".d.ts")
LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".go": "go",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "ts",
    ".jsx": "ts",
    ".mjs": "ts",
    ".cjs": "ts",
    ".mts": "ts",
    ".cts": "ts",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".hcl": "terraform",
}

GO_IMPORT_BLOCK = re.compile(r"\bimport\s*\((.*?)\)", re.S)
GO_IMPORT_SINGLE = re.compile(r"^\s*import\s+(?:[\w.]+\s+)?\"([^\"]+)\"", re.M)
QUOTED = re.compile(r"\"([^\"]+)\"")
TS_SPECIFIER = re.compile(r"""(?:\bfrom|\bimport|\brequire)\s*\(?\s*['"]([^'"]+)['"]""")
TF_MODULE_BLOCK = re.compile(r"\bmodule\s+\"([^\"]+)\"\s*\{")
TF_SOURCE = re.compile(r"\bsource\s*=\s*\"([^\"]+)\"")
TF_RESOURCE = re.compile(r"\bresource\s+\"([^\"]+)\"\s+\"([^\"]+)\"")
TF_DATA = re.compile(r"\bdata\s+\"([^\"]+)\"\s+\"([^\"]+)\"")
PY_FROM_IMPORT = re.compile(r"^\s*from\s+([.\w]+)\s+import\s+([^\n#]+)", re.M)
PY_PLAIN_IMPORT = re.compile(r"^\s*import\s+([.\w][.\w, ]*)", re.M)
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|testing|spec)(/|$)"
    r"|(^|/)test_[^/]+\.py$"
    r"|_test\.(py|go|ts|tsx|js|jsx)$"
    r"|\.(test|spec)\.[tj]sx?$"
)


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=True
    ).stdout


def git_try(repo, *args):
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, errors="replace"
    )
    return proc.stdout if proc.returncode == 0 else None


def module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    if PY_ROOT:
        if not path.startswith(PY_ROOT + "/"):
            return None
        path = path[len(PY_ROOT) + 1 :]
    return path[:-3].replace("/", ".").removesuffix(".__init__")


def module_path(mod: str) -> str:
    rel = f"{mod.replace('.', '/')}.py"
    return f"{PY_ROOT}/{rel}" if PY_ROOT else rel


def py_pathspec() -> str:
    return f"{PY_ROOT}/*.py" if PY_ROOT else "*.py"


def has_packages(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    for child in directory.iterdir():
        if child.is_dir() and (child / "__init__.py").is_file():
            return True
        if child.is_file() and child.suffix == ".py":
            return True
    return False


def pyproject_py_root(root: Path) -> str | None:
    manifest = root / "pyproject.toml"
    if tomllib is None or not manifest.is_file():
        return None
    try:
        data = tomllib.loads(manifest.read_text(errors="replace"))
    except Exception:
        return None
    tool = data.get("tool", {}) if isinstance(data, dict) else {}
    poetry = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    packages = poetry.get("packages") if isinstance(poetry, dict) else None
    if isinstance(packages, list):
        for entry in packages:
            if isinstance(entry, dict) and entry.get("from"):
                return str(entry["from"]).strip("/")
            if isinstance(entry, dict) and entry.get("include"):
                return ""
    setuptools = tool.get("setuptools", {}) if isinstance(tool, dict) else {}
    if isinstance(setuptools, dict):
        package_dir = setuptools.get("package-dir")
        if isinstance(package_dir, dict):
            for key in ("", "*"):
                if isinstance(package_dir.get(key), str):
                    return package_dir[key].strip("/")
        find = setuptools.get("packages")
        if isinstance(find, dict):
            where = find.get("find", {}).get("where") if isinstance(find.get("find"), dict) else None
            if isinstance(where, list) and where:
                return str(where[0]).strip("/").lstrip("./")
            if isinstance(where, str):
                return where.strip("/").lstrip("./")
        if isinstance(find, list) and find:
            return ""
    return None


def layout_py_root(root: Path) -> str:
    if has_packages(root / "src"):
        return "src"
    if (root / "python").is_dir():
        return "python"
    declared = pyproject_py_root(root)
    if declared is not None:
        return declared
    return ""


def package_root(root: Path, path: str) -> Path | None:
    current = (root / path).parent
    while current == root or root in current.parents:
        if (current / "pyproject.toml").is_file():
            return current
        if current == root:
            return None
        current = current.parent
    return None


def changed_py_root(root: Path, paths) -> str | None:
    counts: dict[str, int] = {}
    for path in paths:
        if not path.endswith(".py"):
            continue
        base = package_root(root, path)
        if base is None:
            continue
        rel = base.relative_to(root).as_posix()
        rel = "" if rel == "." else rel
        counts[rel] = counts.get(rel, 0) + 1
    if not counts:
        return None
    best = min(counts, key=lambda rel: (-counts[rel], rel))
    inner = layout_py_root(root / best if best else root)
    return "/".join(part for part in (best, inner) if part)


def detect_py_root(repo: str, paths) -> str:
    root = Path(repo)
    derived = changed_py_root(root, paths)
    return layout_py_root(root) if derived is None else derived


def derive_package(modules) -> str:
    names = sorted(modules)
    if not names:
        return ""
    common: list[str] = []
    for segments in zip(*[name.split(".") for name in names]):
        if len(set(segments)) > 1:
            break
        common.append(segments[0])
    if common and ".".join(common) in names:
        common.pop()
    return ".".join(common)


class ModuleInfo:
    """Functions, imports and calls of one module's source."""

    def __init__(self, mod: str, source: str | None):
        self.mod = mod
        self.source = source or ""
        self.lines = self.source.splitlines()
        self.functions: dict[str, dict] = {}
        self.imports: dict[str, str] = {}  # local name -> "pkg.mod.name" or "pkg.mod"
        if source is None:
            return
        try:
            tree = ast.parse(source)
        except SyntaxError:
            self.source = ""
            self.lines = []
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    self.imports[a.asname or a.name] = f"{node.module}.{a.name}"
            elif isinstance(node, ast.Import):
                for a in node.names:
                    self.imports[a.asname or a.name.split(".")[0]] = (
                        a.name if a.asname else a.name.split(".")[0]
                    )
        self._collect(tree.body, prefix="", cls=None)

    def _collect(self, body, prefix, cls):
        for node in body:
            if isinstance(node, ast.ClassDef):
                self._collect(node.body, prefix=f"{prefix}{node.name}.", cls=node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([d.lineno for d in node.decorator_list] + [node.lineno])
                qual = f"{prefix}{node.name}"
                self.functions[qual] = {
                    "qual": qual,
                    "start": start,
                    "end": node.end_lineno,
                    "cls": cls,
                    "calls": self._calls(node),
                    "doc": (ast.get_docstring(node) or "").split("\n")[0],
                    "signature": self._signature(node),
                }

    def _signature(self, node):
        seg = self.lines[node.lineno - 1 : node.body[0].lineno - 1]
        text = " ".join(s.strip() for s in seg)
        text = re.sub(r'\s*""".*$', "", text)
        return text.rstrip(":").strip()

    def _calls(self, fn):
        """Raw call targets: ('name', x) | ('attr', base, attr) | ('self', attr)."""
        found = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Name):
                found.append(("name", f.id))
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if f.value.id in ("self", "cls"):
                    found.append(("self", f.attr))
                else:
                    found.append(("attr", f.value.id, f.attr))
        # monkeypatch.setattr(mod, "name", ...) in tests targets "name" too
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setattr"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                found.append(("attr", node.args[0].id, node.args[1].value))
        return found

    def function_at(self, lineno: int) -> str | None:
        best = None
        for qual, f in self.functions.items():
            if f["start"] <= lineno <= f["end"]:
                if best is None or f["start"] >= self.functions[best]["start"]:
                    best = qual
        return best


def resolve(info: ModuleInfo, fn: dict, call, known_modules: set[str], package: str):
    """Resolve a raw call to 'module:qual', or None when outside the package."""
    kind = call[0]
    if kind == "self":
        if fn["cls"] and f"{fn['cls']}.{call[1]}" in info.functions:
            return f"{info.mod}:{fn['cls']}.{call[1]}"
        return None
    if kind == "name":
        name = call[1]
        if name in info.functions:
            return f"{info.mod}:{name}"
        target = info.imports.get(name)
        if target and target.startswith(package):
            mod, _, attr = target.rpartition(".")
            return f"{mod}:{attr}"
        return None
    _, base, attr = call
    target = info.imports.get(base)
    if target and target.startswith(package):
        # `import pkg.mod as alias` or `from pkg import mod`
        return f"{target}:{attr}"
    return None


def function_diff(old: ModuleInfo, new: ModuleInfo, qual: str) -> str:
    def seg(info):
        f = info.functions.get(qual)
        return info.lines[f["start"] - 1 : f["end"]] if f else []

    a, b = seg(old), seg(new)
    diff = list(difflib.unified_diff(a, b, lineterm="", n=3))
    return "\n".join(diff[2:]) if diff else "\n".join(" " + l for l in b)


def is_test(mod: str) -> bool:
    return ".tests." in mod or mod.rsplit(".", 1)[-1].endswith("_test")


def classes_of(info: ModuleInfo) -> set[str]:
    if not info.source:
        return set()
    try:
        tree = ast.parse(info.source)
    except SyntaxError:
        return set()
    return {n.name for n in tree.body if isinstance(n, ast.ClassDef)}


def call_graph(repo, base, changed_mods, package):
    nodes: dict[str, dict] = {}

    def node(mod, qual, status, info=None):
        key = f"{mod}:{qual}"
        if key not in nodes:
            fn = info.functions.get(qual) if info else None
            nodes[key] = {
                "id": key,
                "module": mod,
                "qual": qual,
                "status": status,
                "added": 0,
                "removed": 0,
                "test": is_test(mod),
                "doc": fn["doc"] if fn else "",
                "signature": fn["signature"] if fn else "",
                "line": fn["start"] if fn else None,
                "diff": "",
            }
        return nodes[key]

    module_level = {}
    for mod, (old, new) in changed_mods.items():
        sm = difflib.SequenceMatcher(a=old.lines, b=new.lines, autojunk=False)
        touched = set()
        ml = {"added": 0, "removed": 0}
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            for i in range(i1, i2):
                q = old.function_at(i + 1)
                if q:
                    touched.add(q)
                    node(mod, q, "modified")
                    nodes[f"{mod}:{q}"]["removed"] += 1
                else:
                    ml["removed"] += 1
            for j in range(j1, j2):
                q = new.function_at(j + 1)
                if q:
                    touched.add(q)
                    node(mod, q, "modified", new)
                    nodes[f"{mod}:{q}"]["added"] += 1
                else:
                    ml["added"] += 1
        module_level[mod] = ml
        for q in touched:
            n = nodes[f"{mod}:{q}"]
            in_old, in_new = q in old.functions, q in new.functions
            n["status"] = (
                "modified" if in_old and in_new else "added" if in_new else "removed"
            )
            src = new if in_new else old
            fn = src.functions[q]
            n.update(doc=fn["doc"], signature=fn["signature"], line=fn["start"])
            n["diff"] = function_diff(old, new, q)

    edges: dict[tuple, dict] = {}
    context_cache: dict[str, ModuleInfo] = {}

    def context_module(mod):
        if mod in changed_mods:
            return changed_mods[mod][1]
        if mod not in context_cache:
            p = Path(repo, module_path(mod))
            context_cache[mod] = ModuleInfo(mod, p.read_text(errors="replace") if p.exists() else None)
        return context_cache[mod]

    def add_edge(src, dst, side):
        e = edges.setdefault(
            (src, dst), {"source": src, "target": dst, "old": False, "new": False}
        )
        e[side] = True

    for key in list(nodes):
        mod, qual = key.split(":", 1)
        old, new = changed_mods[mod]
        for side, info in (("old", old), ("new", new)):
            fn = info.functions.get(qual)
            if not fn:
                continue
            for call in fn["calls"]:
                target = resolve(info, fn, call, set(changed_mods), package)
                if not target or target == key:
                    continue
                tmod, tqual = target.split(":", 1)
                if target not in nodes:
                    tinfo = context_module(tmod)
                    if tqual not in tinfo.functions and tqual not in classes_of(tinfo):
                        continue
                    node(tmod, tqual, "context", tinfo)
                    if tqual in classes_of(tinfo):
                        nodes[target]["kind"] = "class"
                add_edge(key, target, side)

    targets = {
        k: n for k, n in nodes.items() if n["status"] != "context" and not n["test"]
    }
    for mod, (old, new) in changed_mods.items():
        for side, info in (("old", old), ("new", new)):
            for qual, fn in info.functions.items():
                key = f"{mod}:{qual}"
                for call in fn["calls"]:
                    t = resolve(info, fn, call, set(changed_mods), package)
                    if t in targets and t != key:
                        if key not in nodes:
                            node(mod, qual, "context", info)
                        add_edge(key, t, side)
    names = sorted({n["qual"].split(".")[-1] for n in targets.values()})
    if names:
        patterns = [arg for n in names for arg in ("-e", n)]
        hits = git_try(repo, "grep", "-lw", *patterns, "--", py_pathspec()) or ""
        for path in hits.split():
            mod = module_name(path)
            if not mod or mod in changed_mods or not mod.startswith(package):
                continue
            info = context_module(mod)
            for qual, fn in info.functions.items():
                for call in fn["calls"]:
                    t = resolve(info, fn, call, set(), package)
                    if t in targets:
                        node(mod, qual, "context", info)
                        add_edge(f"{mod}:{qual}", t, "old")
                        add_edge(f"{mod}:{qual}", t, "new")

    candidates = {
        k
        for k, n in nodes.items()
        if not n["test"]
        and n["status"] != "removed"
        and any(e["old"] and e["target"] == k for e in edges.values())
        and not any(
            e["new"] and e["target"] == k and not nodes[e["source"]]["test"]
            for e in edges.values()
        )
    }
    users: dict[str, set[str]] = {}
    for key in list(candidates):
        short = nodes[key]["qual"].split(".")[-1]
        hits = git_try(repo, "grep", "-lw", short, "--", py_pathspec()) or ""
        users[key] = set()
        for path in hits.split():
            mod = module_name(path)
            if not mod or is_test(mod):
                continue
            info = context_module(mod)
            for qual, fn in info.functions.items():
                for call in fn["calls"]:
                    if resolve(info, fn, call, set(), package) == key:
                        users[key].add(f"{mod}:{qual}")
    orphaned: set[str] = set()
    changed = True
    while changed:
        changed = False
        for key in candidates - orphaned:
            if users[key] <= orphaned:
                orphaned.add(key)
                changed = True
    # A user that is itself a candidate only counts once it is orphaned; others
    # (not candidates) are live, so the fixpoint above is conservative.
    for key in candidates:
        nodes[key]["orphaned"] = key in orphaned

    # Propagate: a context callee whose only callers are orphaned functions is unused too.
    for key, n in nodes.items():
        if n["test"] or n["status"] == "removed" or key in candidates:
            continue
        short = n["qual"].split(".")[-1]
        callers_old = {
            e["source"] for e in edges.values() if e["old"] and e["target"] == key
        }
        if not callers_old or not callers_old & orphaned:
            continue
        hits = git_try(repo, "grep", "-lw", short, "--", py_pathspec()) or ""
        live = set()
        for path in hits.split():
            mod = module_name(path)
            if not mod or is_test(mod):
                continue
            info = context_module(mod)
            for qual, fn in info.functions.items():
                for call in fn["calls"]:
                    if resolve(info, fn, call, set(), package) == key:
                        live.add(f"{mod}:{qual}")
        if live and live <= orphaned:
            n["orphaned"] = True

    modules = {}
    for n in nodes.values():
        modules.setdefault(
            n["module"],
            {
                "id": n["module"],
                "path": module_path(n["module"]),
                "changed": n["module"] in changed_mods,
                "test": n["test"],
            },
        )
    for mod, ml in module_level.items():
        if mod in modules:
            modules[mod]["module_level"] = ml
        if mod in changed_mods:
            old, new = changed_mods[mod]
            shown = {n["qual"] for n in nodes.values() if n["module"] == mod}
            modules.setdefault(
                mod,
                {
                    "id": mod,
                    "path": module_path(mod),
                    "changed": True,
                    "test": is_test(mod),
                },
            )
            modules[mod]["hidden_unchanged"] = len(set(new.functions) - shown)
            modules[mod]["module_level"] = ml

    return nodes, edges, modules


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def language_of(path: str) -> str | None:
    suffix = posixpath.splitext(path)[1]
    return LANGUAGE_BY_SUFFIX.get(suffix)


def file_status(repo, base) -> dict[str, str]:
    out = git_try(repo, "diff", "--name-status", base) or ""
    status = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status[parts[-1]] = parts[0][:1]
    return status


def file_diff(repo, base, path) -> str:
    text = git_try(repo, "diff", "--unified=3", base, "--", path) or ""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("@@"):
            return "\n".join(lines[i:])
    return ""


def working_text(repo, path):
    p = Path(repo, path)
    if not p.is_file():
        return None
    try:
        return p.read_text(errors="replace")
    except OSError:
        return None


def go_module_prefix(repo) -> str:
    manifest = Path(repo, "go.mod")
    if not manifest.is_file():
        return ""
    for line in manifest.read_text(errors="replace").splitlines():
        if line.startswith("module "):
            return line.split(None, 1)[1].strip()
    return ""


def go_specifiers(text) -> list[str]:
    specs = []
    for block in GO_IMPORT_BLOCK.findall(text):
        specs.extend(QUOTED.findall(block))
    specs.extend(GO_IMPORT_SINGLE.findall(text))
    return specs


def go_edges(path, text, index):
    directories = index["go_dirs"]
    prefix = index["go_module"]
    found = set()
    for spec in go_specifiers(text):
        target_dir = None
        if prefix and spec == prefix:
            target_dir = "."
        elif prefix and spec.startswith(prefix + "/"):
            target_dir = spec[len(prefix) + 1 :]
        else:
            for directory in directories:
                if directory != "." and (spec == directory or spec.endswith("/" + directory)):
                    target_dir = directory
                    break
        if target_dir in directories:
            found.update(directories[target_dir])
    found.discard(path)
    return found


def ts_edges(path, text, index):
    paths = index["paths"]
    found = set()
    for spec in TS_SPECIFIER.findall(text):
        if not spec.startswith("."):
            continue
        base = posixpath.normpath(posixpath.join(posixpath.dirname(path), spec))
        candidates = [base]
        candidates += [base + ext for ext in TS_EXTENSIONS]
        candidates += [base + "/index" + ext for ext in TS_EXTENSIONS]
        for candidate in candidates:
            if candidate in paths and candidate != path:
                found.add(candidate)
                break
    return found


def terraform_edges(path, text, index):
    found = set()
    for match in TF_MODULE_BLOCK.finditer(text):
        window = text[match.end() : match.end() + 800]
        source = TF_SOURCE.search(window)
        if not source or not source.group(1).startswith("."):
            continue
        directory = posixpath.normpath(
            posixpath.join(posixpath.dirname(path), source.group(1))
        )
        found.update(index["tf_dirs"].get(directory, ()))
    for reference, owner in index["tf_declarations"].items():
        if owner == path:
            continue
        if re.search(r"(?<![\w.-])" + re.escape(reference) + r"(?![\w-])", text):
            found.add(owner)
    found.discard(path)
    return found


def python_edges(path, text, index):
    paths = index["paths"]
    found = set()
    dotted = set()
    for module, names in PY_FROM_IMPORT.findall(text):
        dotted.add(module.strip("."))
        for name in names.replace("(", " ").replace(")", " ").split(","):
            leaf = name.strip().split(" as ")[0].strip()
            if leaf and leaf != "*":
                dotted.add(module.strip(".") + "." + leaf)
    for group in PY_PLAIN_IMPORT.findall(text):
        for name in group.split(","):
            dotted.add(name.strip().split(" as ")[0].strip())
    for name in dotted:
        if not name:
            continue
        stem = name.replace(".", "/")
        for candidate in (stem + ".py", stem + "/__init__.py"):
            for known in paths:
                if known != path and (known == candidate or known.endswith("/" + candidate)):
                    found.add(known)
    return found


def build_index(repo, paths):
    go_dirs: dict[str, set[str]] = {}
    tf_dirs: dict[str, set[str]] = {}
    for path in paths:
        directory = posixpath.dirname(path) or "."
        if path.endswith(".go"):
            go_dirs.setdefault(directory, set()).add(path)
        if language_of(path) == "terraform":
            tf_dirs.setdefault(directory, set()).add(path)
    return {
        "paths": paths,
        "go_dirs": go_dirs,
        "go_module": go_module_prefix(repo),
        "tf_dirs": tf_dirs,
        "tf_declarations": {},
    }


def index_terraform_declarations(index, sides):
    declarations = index["tf_declarations"]
    for path, (old_text, new_text) in sides.items():
        if language_of(path) != "terraform":
            continue
        text = new_text or old_text or ""
        for kind, name in TF_RESOURCE.findall(text):
            declarations.setdefault(f"{kind}.{name}", path)
        for kind, name in TF_DATA.findall(text):
            declarations.setdefault(f"data.{kind}.{name}", path)
        for name in TF_MODULE_BLOCK.findall(text):
            declarations.setdefault(f"module.{name}", path)


EDGE_EXTRACTORS = {
    "go": go_edges,
    "ts": ts_edges,
    "terraform": terraform_edges,
    "python": python_edges,
}


def file_graph(repo, base, files):
    paths = {f["path"] for f in files}
    status = file_status(repo, base)
    sides = {}
    for f in files:
        path = f["path"]
        if f["binary"]:
            sides[path] = (None, None)
            continue
        sides[path] = (git_try(repo, "show", f"{base}:{path}"), working_text(repo, path))

    nodes: dict[str, dict] = {}
    for f in files:
        path = f["path"]
        letter = status.get(path, "M")
        nodes[path] = {
            "id": path,
            "module": posixpath.dirname(path) or ".",
            "qual": posixpath.basename(path),
            "status": {"A": "added", "D": "removed"}.get(letter, "modified"),
            "added": f["added"] or 0,
            "removed": f["removed"] or 0,
            "test": is_test_path(path),
            "doc": "binary file" if f["binary"] else "",
            "signature": path,
            "line": None,
            "diff": "" if f["binary"] else file_diff(repo, base, path),
        }
    if nodes and all(n["test"] for n in nodes.values()):
        for n in nodes.values():
            n["test"] = False
        for f in files:
            f["test"] = False

    index = build_index(repo, paths)
    index_terraform_declarations(index, sides)

    edges: dict[tuple, dict] = {}
    for path, texts in sides.items():
        extract = EDGE_EXTRACTORS.get(language_of(path) or "")
        if not extract:
            continue
        for side, text in zip(("old", "new"), texts):
            if not text:
                continue
            for target in extract(path, text, index):
                if target == path or target not in nodes:
                    continue
                e = edges.setdefault(
                    (path, target),
                    {"source": path, "target": target, "old": False, "new": False},
                )
                e[side] = True

    modules: dict[str, dict] = {}
    for n in nodes.values():
        group = modules.setdefault(
            n["module"],
            {"id": n["module"], "path": n["module"], "changed": True, "test": True},
        )
        group["test"] = group["test"] and n["test"]

    return nodes, edges, modules


def common_directory(paths) -> str:
    directories = [posixpath.dirname(p) for p in sorted(paths)]
    if not directories:
        return ""
    parts = [d.split("/") if d else [] for d in directories]
    common: list[str] = []
    for segments in zip(*parts):
        if len(set(segments)) > 1:
            break
        common.append(segments[0])
    return "/".join(common)


def main():
    ap = argparse.ArgumentParser(
        description="Build the JSON a change-diagram page renders: changed functions "
        "(or changed files, when the code is not Python), their edges and line counts. "
        "Compares <base> to the working tree."
    )
    ap.add_argument("repo")
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument(
        "--package",
        default=None,
        help="dotted module prefix nodes are limited to; derived from the changed "
        "modules when omitted, and empty means no filter",
    )
    ap.add_argument(
        "--py-root",
        default=None,
        help="directory Python module paths are relative to; derived from the changed "
        "files' nearest pyproject.toml when omitted, falling back to the repo layout",
    )
    args = ap.parse_args()
    repo, base = args.repo, args.base

    numstat = git(repo, "diff", "--numstat", base)
    files = []
    for line in numstat.splitlines():
        a, d, path = line.split("\t")
        files.append(
            {
                "path": path,
                "added": None if a == "-" else int(a),
                "removed": None if d == "-" else int(d),
                "binary": a == "-",
                "test": is_test_path(path),
            }
        )

    global PY_ROOT
    PY_ROOT = (
        args.py_root
        if args.py_root is not None
        else detect_py_root(repo, [f["path"] for f in files])
    ).strip("/")

    changed_mods = {}
    for f in files:
        mod = module_name(f["path"])
        if mod:
            old_src = git_try(repo, "show", f"{base}:{f['path']}")
            p = Path(repo, f["path"])
            new_src = p.read_text(errors="replace") if p.exists() else None
            changed_mods[mod] = (ModuleInfo(mod, old_src), ModuleInfo(mod, new_src))
            f["module"] = mod

    package = args.package if args.package is not None else derive_package(changed_mods)

    nodes, edges, modules = call_graph(repo, base, changed_mods, package)
    mode = "callgraph"
    if not nodes and files:
        nodes, edges, modules = file_graph(repo, base, files)
        mode = "files"
        package = common_directory(n["id"] for n in nodes.values())

    for e in edges.values():
        e["status"] = (
            "kept" if e["old"] and e["new"] else "added" if e["new"] else "removed"
        )

    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    out = {
        "title": args.title,
        "mode": mode,
        "branch": branch,
        "base": git(repo, "rev-parse", "--short", base).strip(),
        "package": package,
        "py_root": PY_ROOT,
        "files": files,
        "modules": list(modules.values()),
        "nodes": list(nodes.values()),
        "edges": [
            {k: e[k] for k in ("source", "target", "status")} for e in edges.values()
        ],
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(
        f"{len(out['nodes'])} nodes, {len(out['edges'])} edges, "
        f"{len(modules)} groups, mode={mode}"
    )


if __name__ == "__main__":
    main()
