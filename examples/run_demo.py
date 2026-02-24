#!/usr/bin/env python3
"""
Demo: Call Stack Dynamic Testing Agent
=======================================
Run this to see the full agent workflow in action.

This demonstrates:
1. Instrumenting normal functions
2. Capturing call stacks (NOT call graphs)
3. Analyzing stack patterns
4. Generating tests from observed stacks
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.sample_app import (
    register, admin_register, update_user_email, reset
)
from callstack_agent import CallStackAgent


def main():
    print("=" * 60)
    print("  CALL STACK DYNAMIC TESTING AGENT - DEMO")
    print("=" * 60)
    print()

    # Reset the sample app state
    reset()

    # 1. Create the agent
    agent = CallStackAgent("examples.sample_app", output_dir="./callstack_output")

    # 2. Instrument target functions
    # We target ALL functions in our app — the agent will capture
    # the full call stack at each one
    agent.instrument(functions=[
        "register", "admin_register", "create_user", "create_admin",
        "validate_email", "validate_name", "validate_age",
        "save_to_db", "get_from_db", "send_notification", "format_message",
        "update_user_email",
    ])

    print("\n[PHASE 1] Running test scenarios and capturing call stacks...\n")

    # 3. Run various scenarios — the agent captures stacks during each
    agent.run(
        lambda: register("Alice", "alice@example.com", 30),
        description="Happy path: normal user registration"
    )

    agent.run(
        lambda: register("Bob", "bob@test.org", 25),
        description="Happy path: another user registration"
    )

    agent.run(
        lambda: admin_register("Carol", "carol@admin.com", 35, "secret-admin-key"),
        description="Happy path: admin registration"
    )

    agent.run(
        lambda: register("X", "x@test.com", 20),
        description="Error: name too short",
        expect_exception=True,
    )

    agent.run(
        lambda: register("Dave", "bad-email", 28),
        description="Error: invalid email",
        expect_exception=True,
    )

    agent.run(
        lambda: register("Eve", "eve@test.com", -5),
        description="Error: invalid age",
        expect_exception=True,
    )

    agent.run(
        lambda: admin_register("Frank", "frank@test.com", 15, "secret-admin-key"),
        description="Error: admin too young",
        expect_exception=True,
    )

    agent.run(
        lambda: update_user_email(1, "alice.new@example.com"),
        description="Update existing user email"
    )

    agent.run(
        lambda: update_user_email(999, "nobody@test.com"),
        description="Error: update non-existent user",
        expect_exception=True,
    )

    # 4. Print captured stacks
    print("\n[PHASE 2] Captured call stacks:\n")
    agent.print_stacks()

    # 5. Analyze
    print("\n\n[PHASE 3] Analyzing call stacks...\n")
    report = agent.analyze()
    print(report)

    # 6. Generate tests
    print("\n[PHASE 4] Generating tests...\n")
    test_code = agent.generate_tests()
    print(f"Generated test file preview (first 80 lines):")
    print("-" * 50)
    for line in test_code.split('\n')[:80]:
        print(line)
    print("...")

    # 7. Save baseline for future regression detection
    agent.save_baseline()

    # 8. Show LLM context (what you'd send to Claude for smarter analysis)
    print("\n\n[PHASE 5] LLM Context (send this to Claude for AI-powered analysis):\n")
    context = agent.get_prompt_context()
    print(context[:2000])
    print("...")

    print("\n" + "=" * 60)
    print("  OUTPUT FILES")
    print("=" * 60)
    print(f"  ./callstack_output/analysis_report.txt")
    print(f"  ./callstack_output/test_examples.sample_app_generated.py")
    print(f"  ./callstack_output/baseline_signatures.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
