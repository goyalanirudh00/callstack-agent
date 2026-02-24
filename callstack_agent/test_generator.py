"""
Test Generator
==============
Generates pytest test cases from call stack snapshots.

Uses the actual observed stacks (not call graphs) to generate tests that:
- Reproduce observed execution paths
- Verify caller context requirements
- Test exception propagation paths
- Check frame state preconditions
- Detect regressions via stack signature comparison
"""

from typing import Optional
from collections import defaultdict

from .instrumenter import StackSnapshot
from .analyzer import CallStackAnalyzer


class TestGenerator:
    """
    Generates pytest test code from call stack analysis.
    """

    def __init__(self, snapshots: list[StackSnapshot], module_name: str = "target_module"):
        self.snapshots = snapshots
        self.module_name = module_name
        self.analyzer = CallStackAnalyzer(snapshots)
        self.profiles = self.analyzer.get_function_profiles()

    def generate_all(self) -> str:
        """Generate a complete test file."""
        sections = []
        sections.append(self._generate_header())
        sections.append(self._generate_happy_path_tests())
        sections.append(self._generate_exception_tests())
        sections.append(self._generate_stack_signature_tests())
        sections.append(self._generate_caller_context_tests())
        sections.append(self._generate_frame_state_tests())
        return "\n\n".join(sections)

    def _generate_header(self) -> str:
        return f'''"""
Auto-generated tests from call stack analysis.
Generated from {len(self.snapshots)} stack snapshots.

These tests verify:
- Function behavior matches observed inputs/outputs
- Call stack signatures remain consistent
- Caller context requirements are maintained
- Exception paths propagate correctly
"""

import pytest
from unittest.mock import patch, MagicMock, call
import sys
import {self.module_name} as target
from callstack_agent.instrumenter import CallStackInstrumenter
'''

    def _generate_happy_path_tests(self) -> str:
        """Generate tests from observed call + return pairs."""
        lines = []
        lines.append("# ============================================")
        lines.append("# Happy Path Tests (from observed executions)")
        lines.append("# ============================================")
        lines.append("")

        # Match call snapshots with their return snapshots
        for func, profile in self.profiles.items():
            if func.startswith('<') or func in ('__init__', '__repr__'):
                continue

            if profile['call_count'] == 0:
                continue

            # Find call snapshots with args and matching returns
            call_snaps = [
                s for s in self.snapshots
                if s.trigger_function == func and s.trigger_event == 'call'
            ]
            return_snaps = [
                s for s in self.snapshots
                if s.trigger_function == func and s.trigger_event == 'return'
            ]

            if not call_snaps:
                continue

            lines.append(f"class Test_{func}:")
            lines.append(f'    """Tests for {func} based on {len(call_snaps)} observed calls."""')
            lines.append("")

            # Generate a test from the first observed call
            snap = call_snaps[0]
            args = snap.frames[0].locals if snap.frames else {}

            lines.append(f"    def test_{func}_observed_call(self):")
            lines.append(f"        \"\"\"Reproduce observed call with captured arguments.\"\"\"")

            # Build the call with observed args
            arg_assignments = []
            call_args = []
            for k, v in args.items():
                if k == 'self':
                    continue
                arg_assignments.append(f"        {k} = {v}")
                call_args.append(k)

            lines.extend(arg_assignments)

            if return_snaps:
                ret_val = return_snaps[0].return_value
                lines.append(f"        result = target.{func}({', '.join(call_args)})")
                lines.append(f"        # Observed return value: {ret_val}")
                lines.append(f"        assert result is not None  # TODO: add specific assertion")
            else:
                lines.append(f"        target.{func}({', '.join(call_args)})")
                lines.append(f"        # No return value observed")

            lines.append("")

            # If called from multiple contexts, generate a test for each
            if len(profile['unique_callers']) > 1:
                lines.append(f"    def test_{func}_called_from_multiple_contexts(self):")
                lines.append(f"        \"\"\"")
                lines.append(f"        {func} is called from {len(profile['unique_callers'])} different contexts:")
                for caller in profile['unique_callers']:
                    lines.append(f"        - {caller}")
                lines.append(f"        Verify behavior is consistent regardless of caller.")
                lines.append(f"        \"\"\"")
                lines.append(f"        # TODO: Call {func} through each caller path and verify same result")
                lines.append(f"        pass")
                lines.append("")

        return "\n".join(lines)

    def _generate_exception_tests(self) -> str:
        """Generate tests for observed exception paths."""
        lines = []
        lines.append("# ============================================")
        lines.append("# Exception Path Tests")
        lines.append("# ============================================")
        lines.append("")

        exception_snaps = [s for s in self.snapshots if s.trigger_event == 'exception']

        if not exception_snaps:
            lines.append("# No exceptions were observed during tracing")
            return "\n".join(lines)

        # Group by function
        by_func = defaultdict(list)
        for snap in exception_snaps:
            by_func[snap.trigger_function].append(snap)

        for func, snaps in by_func.items():
            if func.startswith('<'):
                continue

            snap = snaps[0]
            exc_type = snap.exception.split(':')[0] if snap.exception else 'Exception'
            stack_path = ' → '.join(reversed(snap.caller_chain))

            lines.append(f"class Test_{func}_exceptions:")
            lines.append(f"    def test_{func}_raises_{exc_type.lower()}(self):")
            lines.append(f"        \"\"\"")
            lines.append(f"        Observed exception path:")
            lines.append(f"        {stack_path}")
            lines.append(f"        Exception: {snap.exception}")
            lines.append(f"        \"\"\"")

            # Get the args that caused the exception
            if snap.frames:
                args = snap.frames[0].locals
                for k, v in args.items():
                    if k != 'self':
                        lines.append(f"        {k} = {v}")

            lines.append(f"        with pytest.raises({exc_type}):")
            call_args = [k for k in (snap.frames[0].locals if snap.frames else {}) if k != 'self']
            lines.append(f"            target.{func}({', '.join(call_args)})")
            lines.append("")

            # Test that exception propagates through the right stack
            lines.append(f"    def test_{func}_exception_propagation(self):")
            lines.append(f"        \"\"\"Verify exception propagates through: {stack_path}\"\"\"")
            lines.append(f"        instrumenter = CallStackInstrumenter()")
            lines.append(f"        instrumenter.add_target('{func}')")

            # Find the top-level caller
            if len(snap.frames) > 1:
                root_caller = snap.frames[-1].function
                if not root_caller.startswith('<'):
                    lines.append(f"        with instrumenter:")
                    lines.append(f"            try:")
                    root_args = snap.frames[-1].locals
                    root_call_args = [k for k in root_args if k != 'self']
                    lines.append(f"                target.{root_caller}({', '.join(root_call_args)})")
                    lines.append(f"            except {exc_type}:")
                    lines.append(f"                pass")
                    lines.append(f"        exc_stacks = instrumenter.get_exception_stacks()")
                    lines.append(f"        assert len(exc_stacks) > 0, 'Exception should have been captured'")
                    lines.append(f"        assert exc_stacks[0].has_caller('{func}')")

            lines.append("")

        return "\n".join(lines)

    def _generate_stack_signature_tests(self) -> str:
        """Generate regression tests that verify stack signatures don't change."""
        lines = []
        lines.append("# ============================================")
        lines.append("# Stack Signature Regression Tests")
        lines.append("# ============================================")
        lines.append("")

        sigs = self.analyzer.get_unique_signatures()
        call_sigs = {s.signature for s in self.snapshots if s.trigger_event == 'call'}

        lines.append("# Baseline stack signatures captured during this run.")
        lines.append("# If these change after a refactor, it means the execution")
        lines.append("# path has changed — which may or may not be intentional.")
        lines.append("")
        lines.append("BASELINE_SIGNATURES = {")
        for sig in sorted(call_sigs, key=lambda s: s[0] if s else ''):
            lines.append(f"    {sig},")
        lines.append("}")
        lines.append("")

        lines.append("class Test_stack_signatures:")
        lines.append("    def test_no_new_signatures(self):")
        lines.append("        \"\"\"Verify no unexpected new stack paths appear.\"\"\"")
        lines.append("        instrumenter = CallStackInstrumenter()")
        lines.append("        instrumenter.capture_all()")
        lines.append("        with instrumenter:")
        lines.append("            # TODO: Run the same operations as the baseline")
        lines.append("            pass")
        lines.append("        current_sigs = instrumenter.get_unique_signatures()")
        lines.append("        new_sigs = current_sigs - BASELINE_SIGNATURES")
        lines.append("        assert not new_sigs, (")
        lines.append("            f'New stack signatures detected: {new_sigs}. '")
        lines.append("            'This may indicate an unintended change in execution path.'")
        lines.append("        )")
        lines.append("")

        lines.append("    def test_no_missing_signatures(self):")
        lines.append("        \"\"\"Verify no expected stack paths have disappeared.\"\"\"")
        lines.append("        instrumenter = CallStackInstrumenter()")
        lines.append("        instrumenter.capture_all()")
        lines.append("        with instrumenter:")
        lines.append("            # TODO: Run the same operations as the baseline")
        lines.append("            pass")
        lines.append("        current_sigs = instrumenter.get_unique_signatures()")
        lines.append("        missing = BASELINE_SIGNATURES - current_sigs")
        lines.append("        assert not missing, (")
        lines.append("            f'Missing stack signatures: {missing}. '")
        lines.append("            'Expected execution paths are no longer being hit.'")
        lines.append("        )")
        lines.append("")

        return "\n".join(lines)

    def _generate_caller_context_tests(self) -> str:
        """Generate tests that verify functions are called from expected contexts."""
        lines = []
        lines.append("# ============================================")
        lines.append("# Caller Context Verification Tests")
        lines.append("# ============================================")
        lines.append("")

        # Find functions with specific caller patterns
        for func, profile in self.profiles.items():
            if func.startswith('<') or not profile['unique_callers']:
                continue

            callers = profile['unique_callers']
            if len(callers) == 1:
                caller = callers[0]
                if caller.startswith('<'):
                    continue

                lines.append(f"def test_{func}_always_called_from_{caller}():")
                lines.append(f"    \"\"\"")
                lines.append(f"    In all observed executions, '{func}' was always called by '{caller}'.")
                lines.append(f"    This test verifies that invariant is maintained.")
                lines.append(f"    \"\"\"")
                lines.append(f"    instrumenter = CallStackInstrumenter()")
                lines.append(f"    instrumenter.add_target('{func}')")
                lines.append(f"    with instrumenter:")
                lines.append(f"        # TODO: Run the code that exercises {func}")
                lines.append(f"        pass")
                lines.append(f"    for snap in instrumenter.get_call_stacks():")
                lines.append(f"        if snap.trigger_function == '{func}':")
                lines.append(f"            assert snap.has_caller('{caller}'), (")
                lines.append(f"                f'{func} called without {caller} in stack: '")
                lines.append(f"                f'{{snap.caller_chain}}'")
                lines.append(f"            )")
                lines.append("")

        return "\n".join(lines)

    def _generate_frame_state_tests(self) -> str:
        """Generate tests that verify preconditions via caller frame state."""
        lines = []
        lines.append("# ============================================")
        lines.append("# Frame State Precondition Tests")
        lines.append("# ============================================")
        lines.append("")

        # Find functions where caller state had consistent patterns
        for func, profile in self.profiles.items():
            if func.startswith('<') or not profile['args_seen']:
                continue

            # Check if certain args were always present
            all_keys = set()
            for args in profile['args_seen']:
                all_keys.update(args.keys())

            consistent_keys = {
                k for k in all_keys
                if all(k in args for args in profile['args_seen'])
                and k != 'self'
            }

            if consistent_keys:
                lines.append(f"def test_{func}_always_receives_required_args():")
                lines.append(f"    \"\"\"")
                lines.append(f"    {func} was always called with these args: {consistent_keys}")
                lines.append(f"    Verify they are always present.")
                lines.append(f"    \"\"\"")
                lines.append(f"    instrumenter = CallStackInstrumenter()")
                lines.append(f"    instrumenter.add_target('{func}')")
                lines.append(f"    with instrumenter:")
                lines.append(f"        # TODO: Run the code")
                lines.append(f"        pass")
                lines.append(f"    for snap in instrumenter.get_call_stacks():")
                lines.append(f"        if snap.trigger_function == '{func}' and snap.frames:")
                lines.append(f"            frame_locals = snap.frames[0].locals")
                for key in sorted(consistent_keys):
                    lines.append(f"            assert '{key}' in frame_locals, \"Missing required arg: {key}\"")
                lines.append("")

        return "\n".join(lines)
