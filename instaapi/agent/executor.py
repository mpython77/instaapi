"""
Safe Code Executor (Sandbox)
============================
Executes AI-generated Python code in a restricted environment.

Security:
    - Only whitelisted imports allowed
    - No subprocess, os.system, eval, exec of arbitrary code
    - Timeout enforcement (default 30s)
    - Isolated namespace (no access to real globals)
    - stdout/stderr captured
"""

import io
import sys
import time
import logging
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("instaapi.agent.executor")

# Whitelisted modules that agent code can import
ALLOWED_IMPORTS = {
    "json", "csv", "math", "re", "datetime", "time",
    "os", "os.path", "pathlib",
    "collections", "itertools", "functools",
    "typing",
    # Networking (for image downloads)
    "urllib", "urllib.request",
    # Data export
    "openpyxl",
    # InstaAPI
    "instaapi",
}

# Blocked patterns in code — immediate rejection
BLOCKED_PATTERNS = [
    "subprocess",
    "os.system",
    "os.popen",
    "os.exec",
    "os.spawn",
    "__import__(",     # direct __import__() call
    "importlib",
    "compile(",
    "globals()",
    "locals()",
    "breakpoint()",
    "os.remove",
    "os.rmdir",
    "os.unlink",
    "shutil.rmtree",
    "shutil.move",
    "open(/",          # absolute path open
    "open('C:",        # Windows absolute
    "open(\"C:",
    "socket.",
    "http.server",
    "xmlrpc",
    "pickle.loads",
    "marshal.loads",
    "ctypes",
    "sys.exit",
    "quit()",
    "exit()",
]


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool = False
    output: str = ""
    error: str = ""
    return_value: Any = None
    duration: float = 0.0
    variables: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            parts = []
            if self.output:
                parts.append(self.output)
            if self.return_value is not None:
                parts.append(f"→ {self.return_value}")
            return "\n".join(parts) if parts else "Executed successfully"
        return f"Error: {self.error}"


class SafeExecutor:
    """
    Sandbox for executing AI-generated code.

    Usage:
        executor = SafeExecutor(ig_instance)
        result = executor.run('''
            user = ig.users.get_by_username("cristiano")
            print(user.followers)
        ''')
    """

    def __init__(self, ig_instance=None, timeout: int = 30):
        self._ig = ig_instance
        self._timeout = timeout

    def validate(self, code: str) -> Optional[str]:
        """
        Validate code for security issues.

        Returns:
            None if safe, error message if dangerous
        """
        for pattern in BLOCKED_PATTERNS:
            if pattern in code:
                # Give actionable hint to the LLM
                hints = {
                    "globals()": "Use the `ig` variable directly — it's already in your namespace.",
                    "locals()": "Use the `ig` variable directly — it's already in your namespace.",
                    "subprocess": "Shell commands are not allowed. Use ig.* methods instead.",
                    "os.system": "Shell commands are not allowed. Use ig.* methods instead.",
                    "__import__(": "Use standard `import` statements. Only json, csv, re, math, datetime, time, os, pathlib are allowed.",
                    "compile(": "Dynamic code compilation is not allowed. Write code directly.",
                    "eval(": "Dynamic code evaluation is not allowed. Write code directly.",
                }
                hint = hints.get(pattern, "This pattern is blocked for security.")
                return f"Blocked pattern: '{pattern}'. {hint}"

        # Check imports
        lines = code.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                module = self._extract_module_name(stripped)
                if module and module not in ALLOWED_IMPORTS:
                    # Check if it's a sub-import of allowed module
                    base = module.split(".")[0]
                    if base not in ALLOWED_IMPORTS:
                        return f"Unauthorized import: '{module}'. Allowed: {', '.join(sorted(ALLOWED_IMPORTS))}"

        return None  # Safe

    def run(self, code: str) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            code: Python code to execute

        Returns:
            ExecutionResult with output, errors, variables
        """
        start = time.time()

        # 0. Auto-fix common LLM code issues (f-string quotes)
        code = self._fix_fstring_quotes(code)

        # 1. Validate
        error = self.validate(code)
        if error:
            return ExecutionResult(
                success=False,
                error=f"Security validation failed: {error}",
                duration=time.time() - start,
            )

        # 2. Prepare isolated namespace
        namespace = self._build_namespace()

        # 3. Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_out = io.StringIO()
        captured_err = io.StringIO()

        result = ExecutionResult()
        exception_holder = [None]

        def _execute():
            try:
                sys.stdout = captured_out
                sys.stderr = captured_err
                exec(code, namespace)
            except Exception as e:
                exception_holder[0] = e
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        # 4. Run with timeout
        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()
        thread.join(timeout=self._timeout)

        duration = time.time() - start

        if thread.is_alive():
            # Timeout — thread still running
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            return ExecutionResult(
                success=False,
                error=f"Timeout: Code did not finish in {self._timeout} seconds",
                duration=duration,
            )

        # 5. Collect results
        output = captured_out.getvalue()
        err_output = captured_err.getvalue()

        if exception_holder[0]:
            exc = exception_holder[0]
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            return ExecutionResult(
                success=False,
                output=output,
                error=f"{type(exc).__name__}: {exc}\n{tb}",
                duration=duration,
            )

        # Extract user-created variables (exclude builtins and our injected vars)
        injected_keys = {"ig", "Instagram", "json", "csv", "os", "re", "print",
                         "__builtins__", "datetime", "math", "Path", "time"}
        user_vars = {}
        for k, v in namespace.items():
            if k not in injected_keys and not k.startswith("_"):
                try:
                    # Only include serializable values
                    repr(v)
                    user_vars[k] = v
                except Exception:
                    pass

        # Try to get a "result" variable if the code defines one
        return_value = namespace.get("result") or namespace.get("output") or namespace.get("answer")

        return ExecutionResult(
            success=True,
            output=output + err_output,
            return_value=return_value,
            duration=duration,
            variables=user_vars,
        )

    def _build_namespace(self) -> Dict[str, Any]:
        """Build isolated namespace for code execution."""
        import json as _json
        import csv as _csv
        import re as _re
        import math as _math
        import os
        import os.path as _ospath
        from pathlib import Path as _Path
        from datetime import datetime as _datetime

        namespace = {
            "__builtins__": {
                # Safe builtins only
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "type": type,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "min": min,
                "max": max,
                "sum": sum,
                "abs": abs,
                "round": round,
                "any": any,
                "all": all,
                "repr": repr,
                "format": format,
                "id": id,
                "hash": hash,
                "callable": callable,
                "iter": iter,
                "next": next,
                "open": self._safe_open,
                "True": True,
                "False": False,
                "None": None,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "AttributeError": AttributeError,
                "StopIteration": StopIteration,
                "RuntimeError": RuntimeError,
                "ImportError": ImportError,
                "FileNotFoundError": FileNotFoundError,
                "PermissionError": PermissionError,
                "OSError": OSError,
                "__import__": self._safe_import,
            },
            # Pre-imported modules
            "json": _json,
            "csv": _csv,
            "re": _re,
            "math": _math,
            "os": type("SafeOS", (), {
                "path": _ospath,
                "getcwd": os.getcwd,
                "listdir": os.listdir,
                "makedirs": lambda *a, **kw: os.makedirs(*a, exist_ok=True, **kw),
                "sep": os.sep,
            })(),
            "Path": _Path,
            "datetime": _datetime,
            "time": time,
            # Absolute path of working directory — always available
            "__WORKDIR__": os.path.abspath(os.getcwd()),
        }

        # Pre-import openpyxl if available (Excel support)
        try:
            import openpyxl as _openpyxl
            namespace["openpyxl"] = _openpyxl
        except ImportError:
            pass  # openpyxl not installed — Excel export unavailable

        # Inject Instagram instance
        if self._ig:
            namespace["ig"] = self._ig

        # Inject user data cache and login status
        namespace["_cache"] = getattr(self, '_user_cache', {})
        namespace["_is_logged_in"] = getattr(self, '_is_logged_in', False)

        return namespace

    @staticmethod
    def _safe_open(path, mode="r", **kwargs):
        """Restricted open() — only allows read and write in current dir."""
        import os.path
        path_str = str(path)

        # Block absolute paths outside current working directory
        if os.path.isabs(path_str):
            raise PermissionError(f"Writing to absolute path is forbidden: {path_str}")

        # Block path traversal
        if ".." in path_str:
            raise PermissionError(f"Path traversal is forbidden: {path_str}")

        # Allow read mode always
        if mode in ("r", "rb"):
            return open(path, mode, **kwargs)

        # Allow write only for safe extensions
        safe_extensions = {
            ".csv", ".json", ".jsonl", ".txt", ".md", ".tsv",
            ".xlsx", ".xls",  # Excel
            ".jpg", ".jpeg", ".png", ".gif", ".webp",  # Images
            ".mp4", ".webm",  # Videos
        }
        ext = os.path.splitext(path_str)[1].lower()
        if ext not in safe_extensions:
            raise PermissionError(
                f"Writing to '{ext}' format is not allowed. "
                f"Allowed: {', '.join(sorted(safe_extensions))}"
            )

        # Binary mode for non-text files
        binary_exts = {".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm"}
        if ext in binary_exts and "b" not in mode:
            mode = "wb"

        return open(path, mode, **kwargs)

    @staticmethod
    def _safe_import(name, *args, **kwargs):
        """Restricted __import__ — only allows whitelisted modules."""
        base_module = name.split(".")[0]
        if base_module in ALLOWED_IMPORTS or name in ALLOWED_IMPORTS:
            return __import__(name, *args, **kwargs)
        raise ImportError(
            f"Import of '{name}' is not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMPORTS))}"
        )

    @staticmethod
    def _extract_module_name(import_line: str) -> Optional[str]:
        """Extract module name from import statement."""
        line = import_line.strip()
        if line.startswith("from "):
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
        elif line.startswith("import "):
            parts = line.replace(",", " ").split()
            if len(parts) >= 2:
                return parts[1]
        return None

    @staticmethod
    def _fix_fstring_quotes(code: str) -> str:
        """
        Auto-fix f-string nested quote issues (Python 3.10 compat).

        LLMs often generate:
            f"Name: {user.get("name", "N/A")}"
        which is invalid in Python 3.10. This fixes it to:
            f"Name: {user.get('name', 'N/A')}"
        """
        import re

        lines = code.split("\n")
        fixed_lines = []

        for line in lines:
            # Skip comments and non-f-string lines
            stripped = line.lstrip()
            if stripped.startswith("#") or "f\"" not in line and "f'" not in line:
                fixed_lines.append(line)
                continue

            # Fix nested double quotes inside f-string expressions
            # Pattern: inside { ... } in an f"..." string, replace " with '
            try:
                fixed = _fix_fstring_line(line)
                fixed_lines.append(fixed)
            except Exception:
                fixed_lines.append(line)

        return "\n".join(fixed_lines)


def _fix_fstring_line(line: str) -> str:
    """Fix a single line's f-string nested quotes."""
    import re

    result = []
    i = 0
    length = len(line)

    while i < length:
        # Detect f-string start: f" or f'
        if i < length - 1 and line[i] == 'f' and line[i + 1] in ('"', "'"):
            quote_char = line[i + 1]
            result.append('f')
            result.append(quote_char)
            i += 2

            # Process inside f-string
            while i < length and line[i] != quote_char:
                if line[i] == '\\':
                    result.append(line[i])
                    i += 1
                    if i < length:
                        result.append(line[i])
                        i += 1
                elif line[i] == '{':
                    # Inside expression — collect until matching }
                    brace_depth = 1
                    expr_start = i
                    i += 1
                    expr_chars = ['{']

                    while i < length and brace_depth > 0:
                        c = line[i]
                        if c == '{':
                            brace_depth += 1
                        elif c == '}':
                            brace_depth -= 1
                        expr_chars.append(c)
                        i += 1

                    expr = ''.join(expr_chars)

                    # Replace inner quotes: if f-string uses " then replace inner " with '
                    if quote_char == '"' and '"' in expr[1:-1]:
                        # Replace double quotes inside expression with single quotes
                        inner = expr[1:-1]  # strip { and }
                        fixed_inner = inner.replace('"', "'")
                        expr = '{' + fixed_inner + '}'
                    elif quote_char == "'" and "'" in expr[1:-1]:
                        inner = expr[1:-1]
                        fixed_inner = inner.replace("'", '"')
                        expr = '{' + fixed_inner + '}'

                    result.append(expr)
                else:
                    result.append(line[i])
                    i += 1

            # Closing quote
            if i < length:
                result.append(line[i])
                i += 1
        else:
            result.append(line[i])
            i += 1

    return ''.join(result)
