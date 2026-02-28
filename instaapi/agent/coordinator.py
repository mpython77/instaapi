"""
Agent Coordinator
=================
Manage multiple agents working in parallel or sequence.
Agents can share state and wait for each other's results.

Usage:
    coordinator = AgentCoordinator(ig, provider="gemini", api_key="...")

    # Parallel execution
    results = coordinator.run_parallel([
        "Get Cristiano's follower count",
        "Get Messi's follower count",
        "Get Neymar's follower count",
    ])

    # Sequential with shared context
    results = coordinator.run_sequential([
        "Get Cristiano's profile",
        "Analyze his last 5 posts",
        "Save results to CSV",
    ])
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import InstaAgent, AgentResult
from .permissions import Permission

logger = logging.getLogger("instaapi.agent.coordinator")


@dataclass
class CoordinatorResult:
    """Result of coordinated multi-agent execution."""
    results: List[AgentResult] = field(default_factory=list)
    total_duration: float = 0.0
    total_tokens: int = 0
    total_steps: int = 0

    @property
    def success(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def all_answers(self) -> List[str]:
        return [r.answer for r in self.results]

    def __str__(self) -> str:
        lines = []
        for i, r in enumerate(self.results, 1):
            status = "✅" if r.success else "❌"
            lines.append(f"{status} Task {i}: {r.answer[:100]}")
        lines.append(f"\nTotal: {self.total_duration:.1f}s | {self.total_steps} steps | {self.total_tokens} tokens")
        return "\n".join(lines)


class AgentCoordinator:
    """
    Coordinate multiple AI agents working together.

    Features:
        - Parallel execution (ThreadPoolExecutor)
        - Sequential with shared context
        - Thread-safe shared state
        - Result aggregation
    """

    def __init__(
        self,
        ig,
        provider: str = "gemini",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        permission: Permission = Permission.FULL_ACCESS,
        max_workers: int = 3,
        verbose: bool = True,
    ):
        self._ig = ig
        self._provider = provider
        self._api_key = api_key
        self._model = model
        self._permission = permission
        self._max_workers = max_workers
        self._verbose = verbose
        self._shared_state: Dict[str, Any] = {}

    def _create_agent(self) -> InstaAgent:
        """Create a new agent instance."""
        return InstaAgent(
            ig=self._ig,
            provider=self._provider,
            api_key=self._api_key,
            model=self._model,
            permission=self._permission,
            verbose=self._verbose,
        )

    def run_parallel(self, tasks: List[str]) -> CoordinatorResult:
        """
        Run multiple tasks in parallel using separate agents.

        Args:
            tasks: List of natural language tasks

        Returns:
            CoordinatorResult with all results
        """
        start = time.time()

        if self._verbose:
            print(f"\nParallel execution: {len(tasks)} tasks")
            print("═" * 40)

        results: List[Optional[AgentResult]] = [None] * len(tasks)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_idx = {}

            for i, task in enumerate(tasks):
                agent = self._create_agent()
                future = executor.submit(agent.ask, task)
                future_to_idx[future] = i

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result(timeout=120)
                    results[idx] = result

                    if self._verbose:
                        status = "✅" if result.success else "❌"
                        print(f"  {status} Task {idx + 1}: done ({result.duration:.1f}s)")
                except Exception as e:
                    results[idx] = AgentResult(error=f"Error: {e}")
                    if self._verbose:
                        print(f"  Error: Task {idx + 1}: {e}")

        coord_result = CoordinatorResult(
            results=[r for r in results if r is not None],
            total_duration=time.time() - start,
        )
        coord_result.total_tokens = sum(r.tokens_used for r in coord_result.results)
        coord_result.total_steps = sum(r.steps for r in coord_result.results)

        if self._verbose:
            print(f"\n⏱️ Total time: {coord_result.total_duration:.1f}s")

        return coord_result

    def run_sequential(self, tasks: List[str]) -> CoordinatorResult:
        """
        Run tasks sequentially, sharing context between them.

        Each task sees the results of previous tasks.

        Args:
            tasks: List of ordered tasks

        Returns:
            CoordinatorResult
        """
        start = time.time()
        agent = self._create_agent()  # Single agent with shared history
        results = []

        if self._verbose:
            print(f"\nSequential execution: {len(tasks)} tasks")
            print("═" * 40)

        for i, task in enumerate(tasks):
            if self._verbose:
                print(f"\n  > Task {i + 1}/{len(tasks)}: {task[:60]}...")

            # Add context from shared state
            if self._shared_state:
                context = json.dumps(self._shared_state, ensure_ascii=False, default=str)
                task_with_context = (
                    f"{task}\n\n"
                    f"Previous results context:\n{context[:500]}"
                )
            else:
                task_with_context = task

            result = agent.ask(task_with_context)
            results.append(result)

            # Update shared state
            if result.success and result.answer:
                self._shared_state[f"task_{i + 1}"] = result.answer[:300]

            if self._verbose:
                status = "✅" if result.success else "❌"
                print(f"  {status} Completed ({result.duration:.1f}s)")


        coord_result = CoordinatorResult(
            results=results,
            total_duration=time.time() - start,
        )
        coord_result.total_tokens = sum(r.tokens_used for r in results)
        coord_result.total_steps = sum(r.steps for r in results)

        return coord_result

    def __repr__(self) -> str:
        return (
            f"<AgentCoordinator provider={self._provider} "
            f"workers={self._max_workers} "
            f"permission={self._permission.value}>"
        )
