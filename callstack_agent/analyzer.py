"""
Call Stack Analyzer
===================
Analyzes captured call stack snapshots to find:
- Stack signature anomalies
- Frame state violations
- Context-dependent behavior
- Missing callers / unexpected callers
- Stack depth anomalies
- Precondition verification via caller frames
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from .instrumenter import StackSnapshot, FrameInfo


@dataclass
class AnalysisResult:
    """Result from a single analysis check."""
    check_name: str
    status: str  # 'pass', 'warn', 'fail'
    message: str
    details: Optional[dict] = None
    snapshot: Optional[StackSnapshot] = None


class CallStackAnalyzer:
    """
    Analyzes call stack snapshots for anomalies, patterns, and test opportunities.

    This works on the STACK level - examining the full chain of active frames
    at each captured moment, not just caller-callee pairs.
    """

    def __init__(self, snapshots: list[StackSnapshot]):
        self.snapshots = snapshots
        self.results: list[AnalysisResult] = []

    def run_all(self) -> list[AnalysisResult]:
        """Run all analysis checks."""
        self.results.clear()
        self.results.extend(self.check_stack_depth_anomalies())
        self.results.extend(self.check_new_stack_signatures())
        self.results.extend(self.check_caller_context_variations())
        self.results.extend(self.check_frame_state_consistency())
        self.results.extend(self.check_exception_propagation())
        self.results.extend(self.check_missing_callers())
        # Recursion-specific checks
        self.results.extend(self.check_recursion_depth())
        self.results.extend(self.check_argument_convergence())
        self.results.extend(self.check_base_case_reached())
        self.results.extend(self.check_memoization_opportunities())
        return self.results

    def check_stack_depth_anomalies(self, threshold_multiplier: float = 2.0) -> list[AnalysisResult]:
        """
        Detect when a function appears at an unusual stack depth.
        If a function normally runs at depth 3-4 but suddenly appears at depth 12,
        something unexpected is happening.
        """
        results = []
        depth_by_func: dict[str, list[int]] = defaultdict(list)

        for snap in self.snapshots:
            if snap.trigger_event == 'call':
                depth_by_func[snap.trigger_function].append(snap.depth)

        for func, depths in depth_by_func.items():
            if len(depths) < 2:
                continue

            avg_depth = sum(depths) / len(depths)
            max_depth = max(depths)
            min_depth = min(depths)

            if max_depth > avg_depth * threshold_multiplier:
                results.append(AnalysisResult(
                    check_name='stack_depth_anomaly',
                    status='warn',
                    message=(
                        f"Function '{func}' has unusual depth variation: "
                        f"avg={avg_depth:.1f}, max={max_depth}, min={min_depth}"
                    ),
                    details={
                        'function': func,
                        'avg_depth': avg_depth,
                        'max_depth': max_depth,
                        'min_depth': min_depth,
                        'all_depths': depths,
                    }
                ))

        if not results:
            results.append(AnalysisResult(
                check_name='stack_depth_anomaly',
                status='pass',
                message='No stack depth anomalies detected'
            ))

        return results

    def check_new_stack_signatures(
        self, baseline_signatures: Optional[set[tuple[str, ...]]] = None
    ) -> list[AnalysisResult]:
        """
        Compare current stack signatures against a baseline.
        New signatures that weren't seen before may indicate regressions or new code paths.
        """
        results = []
        current_sigs = {s.signature for s in self.snapshots if s.trigger_event == 'call'}

        if baseline_signatures is None:
            results.append(AnalysisResult(
                check_name='new_stack_signatures',
                status='pass',
                message=f'Found {len(current_sigs)} unique stack signatures (no baseline to compare)',
                details={'signatures': [list(s) for s in current_sigs]}
            ))
            return results

        new_sigs = current_sigs - baseline_signatures
        missing_sigs = baseline_signatures - current_sigs

        if new_sigs:
            results.append(AnalysisResult(
                check_name='new_stack_signatures',
                status='warn',
                message=f'{len(new_sigs)} new stack signature(s) not seen in baseline',
                details={'new_signatures': [list(s) for s in new_sigs]}
            ))

        if missing_sigs:
            results.append(AnalysisResult(
                check_name='missing_stack_signatures',
                status='warn',
                message=f'{len(missing_sigs)} baseline signature(s) no longer observed',
                details={'missing_signatures': [list(s) for s in missing_sigs]}
            ))

        if not new_sigs and not missing_sigs:
            results.append(AnalysisResult(
                check_name='new_stack_signatures',
                status='pass',
                message='All stack signatures match baseline'
            ))

        return results

    def check_caller_context_variations(self) -> list[AnalysisResult]:
        """
        Find functions that are called from different stack contexts.
        This reveals context-dependent behavior - the same function may
        behave differently depending on WHO called it.
        """
        results = []
        contexts_by_func: dict[str, list[tuple[str, ...]]] = defaultdict(list)

        for snap in self.snapshots:
            if snap.trigger_event == 'call':
                # The caller context is everything ABOVE the trigger function
                caller_context = tuple(f.function for f in snap.frames[1:])
                contexts_by_func[snap.trigger_function].append(caller_context)

        for func, contexts in contexts_by_func.items():
            unique_contexts = set(contexts)
            if len(unique_contexts) > 1:
                results.append(AnalysisResult(
                    check_name='caller_context_variation',
                    status='warn',
                    message=(
                        f"Function '{func}' called from {len(unique_contexts)} "
                        f"different stack contexts"
                    ),
                    details={
                        'function': func,
                        'contexts': [list(c) for c in unique_contexts],
                        'context_count': len(unique_contexts),
                    }
                ))

        if not results:
            results.append(AnalysisResult(
                check_name='caller_context_variation',
                status='pass',
                message='No context variations detected'
            ))

        return results

    def check_frame_state_consistency(self) -> list[AnalysisResult]:
        """
        Check that frame local variables are consistent across calls.
        For each function, look at the caller frames and check if their
        state is consistent when the function is invoked.
        """
        results = []
        caller_states: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

        for snap in self.snapshots:
            if snap.trigger_event == 'call' and len(snap.frames) > 1:
                trigger = snap.trigger_function
                caller_frame = snap.frames[1]  # immediate caller
                caller_states[trigger][caller_frame.function].append(caller_frame.locals)

        for func, callers in caller_states.items():
            for caller_name, states in callers.items():
                if len(states) < 2:
                    continue

                # Check which variables are present in all calls
                all_keys = set()
                for s in states:
                    all_keys.update(s.keys())

                for key in all_keys:
                    values = [s.get(key, '<missing>') for s in states]
                    unique_values = set(values)

                    # If a variable has many unique values, it's likely an argument (expected)
                    # If it has exactly 2 values where one is unusual, flag it
                    if '<missing>' in unique_values and len(unique_values) > 1:
                        results.append(AnalysisResult(
                            check_name='frame_state_inconsistency',
                            status='warn',
                            message=(
                                f"Variable '{key}' in '{caller_name}' is sometimes missing "
                                f"when calling '{func}'"
                            ),
                            details={
                                'function': func,
                                'caller': caller_name,
                                'variable': key,
                                'values_seen': list(unique_values),
                            }
                        ))

        if not results:
            results.append(AnalysisResult(
                check_name='frame_state_inconsistency',
                status='pass',
                message='Frame states are consistent across calls'
            ))

        return results

    def check_exception_propagation(self) -> list[AnalysisResult]:
        """
        Analyze exception stacks to see how exceptions propagate up the stack.
        Check if exceptions are caught at the right level.
        """
        results = []
        exception_snaps = [s for s in self.snapshots if s.trigger_event == 'exception']

        if not exception_snaps:
            results.append(AnalysisResult(
                check_name='exception_propagation',
                status='pass',
                message='No exceptions captured'
            ))
            return results

        for snap in exception_snaps:
            results.append(AnalysisResult(
                check_name='exception_propagation',
                status='warn',
                message=(
                    f"Exception in '{snap.trigger_function}': {snap.exception} | "
                    f"Stack: {' → '.join(reversed(snap.caller_chain))}"
                ),
                details={
                    'function': snap.trigger_function,
                    'exception': snap.exception,
                    'stack': snap.caller_chain,
                    'depth': snap.depth,
                },
                snapshot=snap,
            ))

        return results

    def check_missing_callers(self, expected_callers: Optional[dict[str, list[str]]] = None) -> list[AnalysisResult]:
        """
        Verify that certain functions are always called within expected caller contexts.
        For example: save_to_db should always have validate_email somewhere in its stack.

        expected_callers: {
            'save_to_db': ['validate_email'],  # validate_email must be in the stack
        }
        """
        results = []

        if not expected_callers:
            return results

        for snap in self.snapshots:
            if snap.trigger_event != 'call':
                continue

            func = snap.trigger_function
            if func not in expected_callers:
                continue

            required = expected_callers[func]
            callers_in_stack = set(snap.caller_chain)

            for req in required:
                if req not in callers_in_stack:
                    results.append(AnalysisResult(
                        check_name='missing_caller',
                        status='fail',
                        message=(
                            f"Function '{func}' called WITHOUT required caller "
                            f"'{req}' in the stack. "
                            f"Actual stack: {' → '.join(reversed(snap.caller_chain))}"
                        ),
                        details={
                            'function': func,
                            'missing_caller': req,
                            'actual_stack': snap.caller_chain,
                        },
                        snapshot=snap,
                    ))

        if not results:
            results.append(AnalysisResult(
                check_name='missing_caller',
                status='pass',
                message='All required callers present in stacks'
            ))

        return results

    # ==========================================================
    # RECURSION ANALYSIS
    # ==========================================================

    def _detect_recursive_functions(self) -> dict[str, list[StackSnapshot]]:
        """
        Detect which functions are recursive by checking if the same
        function name appears more than once in a single call stack.
        Returns {function_name: [snapshots where recursion was detected]}.
        """
        recursive: dict[str, list[StackSnapshot]] = defaultdict(list)

        for snap in self.snapshots:
            if snap.trigger_event != 'call':
                continue
            # Count how many times the trigger function appears in its own stack
            func = snap.trigger_function
            occurrences = sum(1 for f in snap.frames if f.function == func)
            if occurrences > 1:
                recursive[func].append(snap)

        return dict(recursive)

    def check_recursion_depth(self, max_safe_depth: int = 100) -> list[AnalysisResult]:
        """
        1. RECURSION DEPTH MONITOR
        For every recursive function, track the recursion depth at each
        invocation and flag if it exceeds safe bounds.

        Recursion depth = number of times the SAME function appears in one stack.
        """
        results = []
        recursive = self._detect_recursive_functions()

        if not recursive:
            results.append(AnalysisResult(
                check_name='recursion_depth',
                status='pass',
                message='No recursive functions detected'
            ))
            return results

        for func, snaps in recursive.items():
            # For each snapshot, count recursion depth
            depths = []
            for snap in snaps:
                depth = sum(1 for f in snap.frames if f.function == func)
                depths.append(depth)

            max_d = max(depths)
            avg_d = sum(depths) / len(depths)
            total_calls = len(snaps)

            status = 'fail' if max_d >= max_safe_depth else 'warn' if max_d > max_safe_depth // 2 else 'pass'

            results.append(AnalysisResult(
                check_name='recursion_depth',
                status=status,
                message=(
                    f"Recursive function '{func}': max depth={max_d}, "
                    f"avg depth={avg_d:.1f}, total recursive calls={total_calls}, "
                    f"safe limit={max_safe_depth}"
                ),
                details={
                    'function': func,
                    'max_depth': max_d,
                    'avg_depth': avg_d,
                    'all_depths': depths,
                    'total_recursive_calls': total_calls,
                    'safe_limit': max_safe_depth,
                    'exceeded': max_d >= max_safe_depth,
                }
            ))

        return results

    def check_argument_convergence(self) -> list[AnalysisResult]:
        """
        2. ARGUMENT CONVERGENCE CHECKER
        For recursive functions, capture arguments at each recursion level
        and verify they are converging toward the base case.

        Checks:
        - Numeric args: should be decreasing (or increasing toward a bound)
        - Collection args: should be getting shorter
        - If args are NOT converging, flag potential infinite recursion
        """
        results = []
        recursive = self._detect_recursive_functions()

        if not recursive:
            results.append(AnalysisResult(
                check_name='argument_convergence',
                status='pass',
                message='No recursive functions to check convergence'
            ))
            return results

        for func, snaps in recursive.items():
            # Group snapshots that belong to the same recursive call chain
            # by looking at snapshots with increasing depth
            for snap in snaps:
                # Extract args at each recursion level in THIS stack
                recursive_frames = [f for f in snap.frames if f.function == func]

                if len(recursive_frames) < 2:
                    continue

                # Check each argument across recursion levels
                # frames[0] = deepest (most recent call), frames[-1] = first call
                convergence_issues = []

                # Get arg names from the deepest frame
                arg_names = [k for k in recursive_frames[0].locals.keys() if k != 'self']

                for arg in arg_names:
                    values_by_depth = []
                    for frame in recursive_frames:
                        val_str = frame.locals.get(arg, None)
                        if val_str is None:
                            continue
                        values_by_depth.append(val_str)

                    if len(values_by_depth) < 2:
                        continue

                    # Try to parse as numbers and check convergence
                    try:
                        numeric_vals = [float(v) for v in values_by_depth]
                        # Values should be changing (moving toward base case)
                        # Check if monotonically decreasing or increasing
                        diffs = [numeric_vals[i] - numeric_vals[i+1] for i in range(len(numeric_vals)-1)]

                        if all(d == 0 for d in diffs):
                            convergence_issues.append(
                                f"arg '{arg}' is CONSTANT across recursion levels "
                                f"(value={numeric_vals[0]}) — infinite recursion risk"
                            )
                        elif not (all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)):
                            convergence_issues.append(
                                f"arg '{arg}' is NOT monotonic: {numeric_vals} — "
                                f"may not converge to base case"
                            )
                    except (ValueError, TypeError):
                        # Not numeric — check string length as proxy for collections
                        try:
                            lengths = [len(eval(v)) if v.startswith(('[', '(', '{')) else len(v)
                                       for v in values_by_depth]
                            if all(l == lengths[0] for l in lengths):
                                convergence_issues.append(
                                    f"arg '{arg}' collection size is CONSTANT "
                                    f"(size={lengths[0]}) — infinite recursion risk"
                                )
                        except Exception:
                            pass  # Can't evaluate, skip

                if convergence_issues:
                    for issue in convergence_issues:
                        results.append(AnalysisResult(
                            check_name='argument_convergence',
                            status='warn',
                            message=f"Recursion convergence issue in '{func}': {issue}",
                            details={
                                'function': func,
                                'issue': issue,
                                'recursion_depth': len(recursive_frames),
                            },
                            snapshot=snap,
                        ))

            # If no issues found for this function, report pass
            if not any(r.details and r.details.get('function') == func for r in results):
                results.append(AnalysisResult(
                    check_name='argument_convergence',
                    status='pass',
                    message=f"Recursive function '{func}': arguments converge correctly toward base case",
                    details={'function': func}
                ))

        if not results:
            results.append(AnalysisResult(
                check_name='argument_convergence',
                status='pass',
                message='No recursive functions to check convergence'
            ))

        return results

    def check_base_case_reached(self) -> list[AnalysisResult]:
        """
        3. BASE CASE VERIFICATION
        For recursive functions, verify that:
        - The base case is actually reached (a return without deeper recursion)
        - The base case returns the correct type of value
        - The deepest recursion frame is the base case frame

        Detection: A 'return' event for a recursive function where the stack
        does NOT contain another instance of the same function below it
        (i.e., it didn't recurse deeper — this IS the base case).
        """
        results = []
        recursive = self._detect_recursive_functions()

        if not recursive:
            results.append(AnalysisResult(
                check_name='base_case_reached',
                status='pass',
                message='No recursive functions to verify base cases'
            ))
            return results

        for func in recursive:
            # Find return snapshots for this function
            return_snaps = [
                s for s in self.snapshots
                if s.trigger_function == func and s.trigger_event == 'return'
            ]

            if not return_snaps:
                results.append(AnalysisResult(
                    check_name='base_case_reached',
                    status='fail',
                    message=f"Recursive function '{func}' has NO return events — may not terminate",
                    details={'function': func}
                ))
                continue

            # Find base case returns: returns where the function does NOT
            # appear elsewhere in the stack (it's the only instance)
            base_case_returns = []
            recursive_returns = []

            for snap in return_snaps:
                # Count occurrences of func in the stack (excluding the trigger itself)
                other_occurrences = sum(
                    1 for f in snap.frames[1:] if f.function == func
                )
                if other_occurrences == 0:
                    base_case_returns.append(snap)
                else:
                    recursive_returns.append(snap)

            if not base_case_returns:
                results.append(AnalysisResult(
                    check_name='base_case_reached',
                    status='fail',
                    message=(
                        f"Recursive function '{func}': NO base case return detected. "
                        f"All {len(return_snaps)} returns had deeper recursion in the stack."
                    ),
                    details={'function': func, 'total_returns': len(return_snaps)}
                ))
            else:
                # Collect base case return values
                base_values = [s.return_value for s in base_case_returns]
                unique_base_values = list(set(base_values))

                results.append(AnalysisResult(
                    check_name='base_case_reached',
                    status='pass',
                    message=(
                        f"Recursive function '{func}': base case reached "
                        f"{len(base_case_returns)} time(s). "
                        f"Base case return values: {unique_base_values}. "
                        f"Recursive returns: {len(recursive_returns)}"
                    ),
                    details={
                        'function': func,
                        'base_case_count': len(base_case_returns),
                        'recursive_return_count': len(recursive_returns),
                        'base_case_values': unique_base_values,
                        'base_case_args': [
                            s.frames[0].locals if s.frames else {}
                            for s in base_case_returns
                        ],
                    }
                ))

        return results

    def check_memoization_opportunities(self) -> list[AnalysisResult]:
        """
        4. MEMOIZATION OPPORTUNITY DETECTOR
        For recursive functions, capture arguments at every call and detect
        repeated subproblems (same arguments appearing multiple times).
        If duplicates are found, suggest memoization / dynamic programming.
        """
        results = []
        recursive = self._detect_recursive_functions()

        if not recursive:
            results.append(AnalysisResult(
                check_name='memoization_opportunity',
                status='pass',
                message='No recursive functions to check for memoization'
            ))
            return results

        for func in recursive:
            # Get ALL call snapshots for this function (recursive + non-recursive)
            all_calls = [
                s for s in self.snapshots
                if s.trigger_function == func and s.trigger_event == 'call'
            ]

            if not all_calls:
                continue

            # Extract argument signatures for each call
            arg_signatures = []
            for snap in all_calls:
                if snap.frames:
                    # Create a hashable key from the args (excluding 'self')
                    args = {k: v for k, v in snap.frames[0].locals.items() if k != 'self'}
                    arg_sig = tuple(sorted(args.items()))
                    arg_signatures.append(arg_sig)

            # Count duplicates
            arg_counts = Counter(arg_signatures)
            duplicates = {k: v for k, v in arg_counts.items() if v > 1}
            total_calls = len(arg_signatures)
            unique_calls = len(arg_counts)
            redundant_calls = sum(v - 1 for v in duplicates.values())

            if duplicates:
                # Calculate waste percentage
                waste_pct = (redundant_calls / total_calls * 100) if total_calls > 0 else 0

                # Format the duplicated args for display
                dup_display = []
                for args, count in sorted(duplicates.items(), key=lambda x: -x[1]):
                    args_str = ", ".join(f"{k}={v}" for k, v in args)
                    dup_display.append(f"({args_str}) called {count}x")

                results.append(AnalysisResult(
                    check_name='memoization_opportunity',
                    status='warn',
                    message=(
                        f"MEMOIZATION RECOMMENDED for '{func}': "
                        f"{redundant_calls}/{total_calls} calls are redundant "
                        f"({waste_pct:.0f}% wasted). "
                        f"{len(duplicates)} unique arg combinations are repeated. "
                        f"Adding @functools.lru_cache or manual memoization would "
                        f"reduce calls from {total_calls} to {unique_calls}."
                    ),
                    details={
                        'function': func,
                        'total_calls': total_calls,
                        'unique_calls': unique_calls,
                        'redundant_calls': redundant_calls,
                        'waste_percentage': waste_pct,
                        'duplicated_args': dup_display,
                        'savings': f"{total_calls} → {unique_calls} calls",
                    }
                ))
            else:
                results.append(AnalysisResult(
                    check_name='memoization_opportunity',
                    status='pass',
                    message=(
                        f"Recursive function '{func}': no repeated subproblems detected "
                        f"({unique_calls} unique argument combinations in {total_calls} calls). "
                        f"Memoization not needed."
                    ),
                    details={
                        'function': func,
                        'total_calls': total_calls,
                        'unique_calls': unique_calls,
                    }
                ))

        return results

    def get_unique_signatures(self) -> set[tuple[str, ...]]:
        """Return all unique stack signatures observed."""
        return {s.signature for s in self.snapshots}

    def get_function_profiles(self) -> dict[str, dict]:
        """
        Build a profile for each function based on observed call stacks.
        This is what the AI agent uses to understand function behavior.
        """
        profiles = {}

        for snap in self.snapshots:
            func = snap.trigger_function
            if func not in profiles:
                profiles[func] = {
                    'call_count': 0,
                    'return_count': 0,
                    'exception_count': 0,
                    'depths': [],
                    'callers': [],
                    'stack_signatures': [],
                    'args_seen': [],
                    'return_values': [],
                    'exceptions': [],
                }

            p = profiles[func]

            if snap.trigger_event == 'call':
                p['call_count'] += 1
                p['depths'].append(snap.depth)
                p['args_seen'].append(snap.frames[0].locals if snap.frames else {})
                if len(snap.frames) > 1:
                    p['callers'].append(snap.frames[1].function)
                p['stack_signatures'].append(list(snap.signature))

            elif snap.trigger_event == 'return':
                p['return_count'] += 1
                p['return_values'].append(snap.return_value)

            elif snap.trigger_event == 'exception':
                p['exception_count'] += 1
                p['exceptions'].append(snap.exception)

        # Summarize
        for func, p in profiles.items():
            p['unique_callers'] = list(set(p['callers']))
            p['unique_signatures'] = len(set(tuple(s) for s in p['stack_signatures']))
            p['avg_depth'] = sum(p['depths']) / len(p['depths']) if p['depths'] else 0

        return profiles

    def generate_report(self) -> str:
        """Generate a human-readable analysis report."""
        results = self.run_all()
        profiles = self.get_function_profiles()

        lines = []
        lines.append("=" * 60)
        lines.append("CALL STACK DYNAMIC ANALYSIS REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total snapshots: {len(self.snapshots)}")
        lines.append(f"Functions profiled: {len(profiles)}")
        lines.append(f"Analysis checks run: {len(results)}")
        lines.append(f"  Passed: {sum(1 for r in results if r.status == 'pass')}")
        lines.append(f"  Warnings: {sum(1 for r in results if r.status == 'warn')}")
        lines.append(f"  Failures: {sum(1 for r in results if r.status == 'fail')}")
        lines.append("")

        # Function profiles
        lines.append("FUNCTION PROFILES")
        lines.append("-" * 40)
        for func, p in profiles.items():
            lines.append(f"\n  {func}:")
            lines.append(f"    Calls: {p['call_count']}, Returns: {p['return_count']}, Exceptions: {p['exception_count']}")
            lines.append(f"    Avg depth: {p['avg_depth']:.1f}")
            lines.append(f"    Called by: {', '.join(p['unique_callers']) or 'N/A'}")
            lines.append(f"    Unique stack signatures: {p['unique_signatures']}")
        lines.append("")

        # Analysis results
        lines.append("ANALYSIS RESULTS")
        lines.append("-" * 40)

        # Separate recursion results from other results
        recursion_checks = {'recursion_depth', 'argument_convergence', 'base_case_reached', 'memoization_opportunity'}
        normal_results = [r for r in results if r.check_name not in recursion_checks]
        recursion_results = [r for r in results if r.check_name in recursion_checks]

        for r in normal_results:
            icon = {'pass': '✓', 'warn': '⚠', 'fail': '✗'}[r.status]
            lines.append(f"  {icon} [{r.check_name}] {r.message}")

        # Recursion analysis section
        lines.append("")
        lines.append("RECURSION ANALYSIS")
        lines.append("-" * 40)
        if recursion_results:
            for r in recursion_results:
                icon = {'pass': '✓', 'warn': '⚠', 'fail': '✗'}[r.status]
                lines.append(f"  {icon} [{r.check_name}] {r.message}")
        else:
            lines.append("  No recursive functions detected")
        lines.append("")

        return "\n".join(lines)
