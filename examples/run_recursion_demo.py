#!/usr/bin/env python3
"""
Demo: Recursion Analysis
========================
Tests all 4 recursion checks:
1. Recursion Depth Monitor
2. Argument Convergence Checker
3. Base Case Verification
4. Memoization Opportunity Detector
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from callstack_agent import CallStackAgent


# --- Recursive functions to test ---

def fibonacci(n):
    """Classic recursive fibonacci — has overlapping subproblems."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def factorial(n):
    """Simple recursion — no overlapping subproblems."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def binary_search(arr, target, low, high):
    """Recursive binary search — args converge toward base case."""
    if low > high:
        return -1
    mid = (low + high) // 2
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search(arr, target, mid + 1, high)
    else:
        return binary_search(arr, target, low, mid - 1)


def power(base, exp):
    """Recursive power — straightforward convergence."""
    if exp == 0:
        return 1
    if exp == 1:
        return base
    return base * power(base, exp - 1)


def flatten(lst):
    """Recursive list flattening — collection gets smaller."""
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def main():
    print("=" * 60)
    print("  RECURSION ANALYSIS DEMO")
    print("=" * 60)

    agent = CallStackAgent("recursion_demo", output_dir="./callstack_output")

    # Instrument all recursive functions
    agent.instrument(functions=[
        "fibonacci", "factorial", "binary_search",
        "power", "flatten",
    ])

    print("\n[1] Running fibonacci (has overlapping subproblems)...\n")
    agent.run(
        lambda: fibonacci(8),
        description="fibonacci(8) — should detect memoization opportunity"
    )

    print("\n[2] Running factorial (clean recursion)...\n")
    agent.run(
        lambda: factorial(10),
        description="factorial(10) — depth 10, args converge"
    )

    print("\n[3] Running binary search (converging args)...\n")
    arr = list(range(0, 100, 2))  # [0, 2, 4, ..., 98]
    agent.run(
        lambda: binary_search(arr, 42, 0, len(arr) - 1),
        description="binary_search — args converge to target"
    )
    agent.run(
        lambda: binary_search(arr, 99, 0, len(arr) - 1),
        description="binary_search — target not found"
    )

    print("\n[4] Running power (simple convergence)...\n")
    agent.run(
        lambda: power(2, 10),
        description="power(2, 10) — exp converges to 0"
    )

    print("\n[5] Running flatten (collection recursion)...\n")
    agent.run(
        lambda: flatten([1, [2, 3], [4, [5, 6]], [7, [8, [9]]]]),
        description="flatten nested list"
    )

    # Print captured stacks
    print("\n" + "=" * 60)
    print("  CAPTURED CALL STACKS")
    print("=" * 60)
    agent.print_stacks()

    # Analyze
    print("\n" + "=" * 60)
    print("  ANALYSIS REPORT")
    print("=" * 60)
    report = agent.analyze()
    print(report)

    # Save
    agent.generate_tests()
    agent.save_baseline()

    print("\nDone. Check ./callstack_output/ for generated files.")


if __name__ == "__main__":
    main()
