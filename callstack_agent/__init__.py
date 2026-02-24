"""
Call Stack Agent - Dynamic Testing Using Call Stack Analysis
============================================================

An AI agent that instruments code, captures full call stack snapshots
at runtime, analyzes them for anomalies, and generates tests.

Key distinction: This works on the CALL STACK (the live stack of active
frames at a specific moment) — NOT the call graph (a summary of all
caller-callee relationships).

Usage:
    from callstack_agent import CallStackAgent

    agent = CallStackAgent("my_module")
    agent.instrument(["my_func", "helper_func"])
    agent.run(lambda: my_module.my_func("input"))
    print(agent.analyze())
    agent.generate_tests()
"""

from .instrumenter import CallStackInstrumenter, StackSnapshot, FrameInfo
from .analyzer import CallStackAnalyzer, AnalysisResult
from .test_generator import TestGenerator
from .agent import CallStackAgent

__all__ = [
    "CallStackAgent",
    "CallStackInstrumenter",
    "CallStackAnalyzer",
    "TestGenerator",
    "StackSnapshot",
    "FrameInfo",
    "AnalysisResult",
]
