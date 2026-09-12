"""Dynamic Target Runner and Adapter Loader for JudgeKit.

Supports loading target adapters from:
1. Python module path (e.g. `docground.tests.evals.judge_adapter:DocGroundTargetAdapter`)
2. Direct file path (e.g. `/path/to/my_adapter.py:MyAdapterClass`)
3. Pre-instantiated adapter objects or functions
"""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from judgekit.schemas import TestCase
from judgekit.target_protocol import BaseTargetAdapter, TargetOutput


def load_target_adapter(target_spec: str) -> BaseTargetAdapter:
    """Dynamically load and instantiate a target adapter from a string spec.

    Format:
        "module.path:ClassName" or "path/to/file.py:ClassName"
    """
    if ":" not in target_spec:
        raise ValueError(
            f"Invalid target spec '{target_spec}'. Expected format 'module_or_path:ClassName'"
        )

    module_or_path, class_name = target_spec.split(":", 1)
    module_or_path = module_or_path.strip()
    class_name = class_name.strip()

    cls: Optional[Type[Any]] = None

    # Check if module_or_path points to an existing file
    file_path = Path(module_or_path)
    if file_path.exists() and file_path.suffix == ".py":
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec from file path: {file_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[file_path.stem] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, class_name, None)
    else:
        # Import as regular python package/module
        mod = importlib.import_module(module_or_path)
        cls = getattr(mod, class_name, None)

    if cls is None:
        raise AttributeError(f"Class '{class_name}' not found in '{module_or_path}'")

    # Instantiate adapter
    instance = cls()
    return instance


class TargetRunnerBridge:
    """Bridges a BaseTargetAdapter to JudgeKit's RAGClientProtocol."""

    def __init__(self, adapter: BaseTargetAdapter, cases_map: Optional[Dict[str, TestCase]] = None):
        self.adapter = adapter
        self.cases_map = cases_map or {}

    async def aquery(self, query: str) -> TargetOutput:
        test_case = self.cases_map.get(query.strip().lower())
        metadata: Dict[str, Any] = {}
        if test_case:
            metadata = {
                "id": test_case.id,
                "category": test_case.category,
                "expected_behavior": test_case.expected_behavior,
                "reference_answer": test_case.reference_answer,
                "reference_contexts": test_case.reference_contexts,
            }
        return await self.adapter.run_query(query, metadata=metadata)
