# Call Stack Dynamic Testing Agent

An AI agent that performs **dynamic testing using call stack analysis** 

## Call Stack vs Call Graph

| | Call Stack | Call Graph |
|---|---|---|
| **What** | Live stack of active frames at a specific moment | Summary of all caller→callee relationships |
| **Shows** | Exact chain of callers + their local state at that instant | Which functions call which |

This project works with **call stacks** — the full chain of active frames at each function call.

## Quick Start

```bash
cd callstack-agent
python examples/run_demo.py
```

## Usage

```python
from callstack_agent import CallStackAgent

agent = CallStackAgent("my_module")
agent.instrument(["my_func", "helper", "validate"])
agent.run(lambda: my_module.my_func("input"), description="happy path")
agent.run(lambda: my_module.my_func(None), description="null input", expect_exception=True)

report = agent.analyze()
agent.generate_tests()
agent.save_baseline()
```

## What the Agent Detects

- **Stack depth anomalies** — function at unusual depth
- **New stack signatures** — execution paths not seen before (regressions)
- **Caller context variations** — same function from different stacks
- **Frame state inconsistencies** — caller variables missing/unexpected
- **Exception propagation** — how exceptions travel up the stack
- **Missing required callers** — e.g. `save_to_db` without `validate` in stack

## Project Structure

```
callstack_agent/
  instrumenter.py   — captures call stacks via sys.settrace
  analyzer.py       — analyzes snapshots for anomalies
  test_generator.py — generates pytest tests from stack data
  agent.py          — orchestrator
examples/
  sample_app.py     — sample app to test
  run_demo.py       — full demo
```
