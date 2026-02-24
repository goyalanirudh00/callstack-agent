"""
AI Agent for Call Stack Dynamic Testing
========================================
The agent that ties it all together:
1. Instruments target code
2. Runs it with various inputs
3. Captures call stack snapshots
4. Analyzes the stacks
5. Generates tests and recommendations

This agent can work standalone or be extended to use an LLM
(like Claude) for smarter analysis and test generation.
"""

import json
import os
from pathlib import Path
from typing import Callable, Optional

from .instrumenter import CallStackInstrumenter, StackSnapshot
from .analyzer import CallStackAnalyzer, AnalysisResult
from .test_generator import TestGenerator


class CallStackAgent:
    """
    AI Agent for dynamic testing using call stack analysis.

    Workflow:
        agent = CallStackAgent("my_module")
        agent.instrument(["register", "create_user", "validate_email"])
        agent.run(lambda: my_module.register("Alice", "alice@example.com"))
        agent.run(lambda: my_module.register("Bob", "invalid"))
        report = agent.analyze()
        tests = agent.generate_tests()
        agent.save_baseline()
    """

    def __init__(self, module_name: str, output_dir: str = "./callstack_output"):
        self.module_name = module_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.instrumenter = CallStackInstrumenter()
        self.all_snapshots: list[StackSnapshot] = []
        self.run_results: list[dict] = []
        self.baseline_signatures: Optional[set[tuple[str, ...]]] = None

    def instrument(self, functions: Optional[list[str]] = None, files: Optional[list[str]] = None):
        """
        Configure which functions/files to instrument.
        Pass nothing to capture all user-code functions.
        """
        if functions:
            for f in functions:
                self.instrumenter.add_target(f)
        if files:
            for f in files:
                self.instrumenter.add_target_file(f)
        if not functions and not files:
            self.instrumenter.capture_all()

        print(f"[Agent] Instrumented: functions={functions or 'ALL'}, files={files or 'ALL'}")

    def run(self, func: Callable, description: str = "", expect_exception: bool = False) -> dict:
        """
        Run a function with call stack instrumentation.

        Args:
            func: A callable to execute (e.g., lambda: my_func(args))
            description: Human-readable description of this test run
            expect_exception: If True, exceptions are caught and recorded

        Returns:
            Dict with run results including captured snapshots
        """
        self.instrumenter.clear()
        result = {
            'description': description,
            'success': False,
            'return_value': None,
            'exception': None,
            'snapshots_captured': 0,
        }

        try:
            with self.instrumenter:
                ret = func()
                result['return_value'] = repr(ret) if ret is not None else None
                result['success'] = True
        except Exception as e:
            result['exception'] = f"{type(e).__name__}: {e}"
            if not expect_exception:
                print(f"[Agent] Exception during run: {e}")
            result['success'] = expect_exception

        snapshots = self.instrumenter.get_snapshots()
        result['snapshots_captured'] = len(snapshots)
        self.all_snapshots.extend(snapshots)
        self.run_results.append(result)

        print(f"[Agent] Run '{description}': captured {len(snapshots)} stack snapshots")
        return result

    def analyze(self) -> str:
        """
        Analyze all captured call stacks and return a report.
        """
        if not self.all_snapshots:
            return "[Agent] No snapshots to analyze. Run some code first."

        analyzer = CallStackAnalyzer(self.all_snapshots)

        # If we have a baseline, check for signature changes
        if self.baseline_signatures:
            sig_results = analyzer.check_new_stack_signatures(self.baseline_signatures)
            for r in sig_results:
                if r.status != 'pass':
                    print(f"[Agent] REGRESSION: {r.message}")

        report = analyzer.generate_report()
        report_path = self.output_dir / "analysis_report.txt"
        report_path.write_text(report)
        print(f"[Agent] Report saved to {report_path}")

        return report

    def generate_tests(self, output_file: Optional[str] = None) -> str:
        """
        Generate pytest test file from captured call stacks.
        """
        if not self.all_snapshots:
            return "[Agent] No snapshots to generate tests from."

        generator = TestGenerator(self.all_snapshots, self.module_name)
        test_code = generator.generate_all()

        if output_file is None:
            output_file = f"test_{self.module_name}_generated.py"

        test_path = self.output_dir / output_file
        test_path.write_text(test_code)
        print(f"[Agent] Generated tests saved to {test_path}")

        return test_code

    def save_baseline(self, filename: str = "baseline_signatures.json"):
        """Save current stack signatures as baseline for future regression detection."""
        sigs = {
            s.signature
            for s in self.all_snapshots
            if s.trigger_event == 'call'
        }
        data = {
            'signatures': [list(s) for s in sigs],
            'total_snapshots': len(self.all_snapshots),
            'module': self.module_name,
        }

        path = self.output_dir / filename
        path.write_text(json.dumps(data, indent=2))
        print(f"[Agent] Baseline saved to {path} ({len(sigs)} signatures)")

    def load_baseline(self, filename: str = "baseline_signatures.json"):
        """Load baseline signatures for regression checking."""
        path = self.output_dir / filename
        if not path.exists():
            print(f"[Agent] No baseline found at {path}")
            return

        data = json.loads(path.read_text())
        self.baseline_signatures = {tuple(s) for s in data['signatures']}
        print(f"[Agent] Loaded baseline: {len(self.baseline_signatures)} signatures")

    def get_function_profiles(self) -> dict:
        """Get detailed profiles of all traced functions."""
        analyzer = CallStackAnalyzer(self.all_snapshots)
        return analyzer.get_function_profiles()

    def get_prompt_context(self) -> str:
        """
        Generate context that can be sent to an LLM (like Claude)
        for smarter analysis and test generation.

        This gives the LLM the full picture of:
        - What functions were called
        - The exact call stacks observed
        - Arguments and return values
        - Any anomalies detected
        """
        analyzer = CallStackAnalyzer(self.all_snapshots)
        profiles = analyzer.get_function_profiles()
        results = analyzer.run_all()

        context = []
        context.append("# Call Stack Analysis Context")
        context.append(f"Module: {self.module_name}")
        context.append(f"Total stack snapshots: {len(self.all_snapshots)}")
        context.append("")

        context.append("## Function Profiles")
        for func, p in profiles.items():
            context.append(f"\n### {func}")
            context.append(f"- Called {p['call_count']} times")
            context.append(f"- Called by: {p['unique_callers']}")
            context.append(f"- Average stack depth: {p['avg_depth']:.1f}")
            context.append(f"- Unique stack paths: {p['unique_signatures']}")
            if p['args_seen']:
                context.append(f"- Sample args: {p['args_seen'][0]}")
            if p['return_values']:
                context.append(f"- Sample return: {p['return_values'][0]}")
            if p['exceptions']:
                context.append(f"- Exceptions: {p['exceptions']}")

        context.append("\n## Observed Stack Signatures")
        for snap in self.all_snapshots:
            if snap.trigger_event == 'call':
                chain = ' → '.join(reversed(snap.caller_chain))
                context.append(f"  {chain}")

        context.append("\n## Analysis Results")
        for r in results:
            icon = {'pass': '✓', 'warn': '⚠', 'fail': '✗'}[r.status]
            context.append(f"  {icon} {r.check_name}: {r.message}")

        return "\n".join(context)

    def print_stacks(self):
        """Print all captured stacks in a readable format."""
        for i, snap in enumerate(self.all_snapshots):
            if snap.trigger_event != 'call':
                continue
            print(f"\n--- Stack #{i} ({snap.trigger_event} {snap.trigger_function}) ---")
            for depth, frame in enumerate(snap.frames):
                indent = "  " * depth
                args_str = ", ".join(f"{k}={v}" for k, v in frame.locals.items() if k != 'self')
                print(f"{indent}[{depth}] {frame.function}({args_str}) @ {frame.filename}:{frame.lineno}")
