"""
Call Stack Instrumenter
=======================
Captures full call stack snapshots at runtime during function execution.
This is the core engine - it captures the STACK (not the graph).

Each snapshot is the complete chain of active frames at a specific moment.
"""

import sys
import time
import threading
from typing import Any, Callable, Optional
from dataclasses import dataclass, field


@dataclass
class FrameInfo:
    """A single frame in the call stack."""
    function: str
    filename: str
    lineno: int
    locals: dict[str, str]
    module: str = ""

    def signature(self) -> str:
        return f"{self.module}.{self.function}" if self.module else self.function


@dataclass
class StackSnapshot:
    """A complete call stack captured at a specific moment."""
    frames: list[FrameInfo]
    timestamp: float
    trigger_function: str
    trigger_event: str  # 'call', 'return', 'exception'
    return_value: Optional[str] = None
    exception: Optional[str] = None
    thread_id: Optional[int] = None

    @property
    def depth(self) -> int:
        return len(self.frames)

    @property
    def signature(self) -> tuple[str, ...]:
        """The stack signature - tuple of function names from top to bottom."""
        return tuple(f.function for f in self.frames)

    @property
    def caller_chain(self) -> list[str]:
        """List of function names from the trigger function up to the root."""
        return [f.function for f in self.frames]

    def frame_at(self, depth: int) -> Optional[FrameInfo]:
        """Get frame at a specific depth (0 = trigger function)."""
        if 0 <= depth < len(self.frames):
            return self.frames[depth]
        return None

    def find_frame(self, function_name: str) -> Optional[FrameInfo]:
        """Find a frame by function name in the stack."""
        for f in self.frames:
            if f.function == function_name:
                return f
        return None

    def has_caller(self, function_name: str) -> bool:
        """Check if a function is anywhere in the caller chain."""
        return any(f.function == function_name for f in self.frames)


class CallStackInstrumenter:
    """
    Instruments code execution and captures full call stack snapshots.

    Usage:
        instrumenter = CallStackInstrumenter()
        instrumenter.add_target("my_function")

        with instrumenter:
            my_code()

        snapshots = instrumenter.get_snapshots()
    """

    def __init__(
        self,
        target_functions: Optional[list[str]] = None,
        target_files: Optional[list[str]] = None,
        capture_locals: bool = True,
        max_depth: int = 50,
    ):
        self.target_functions: set[str] = set(target_functions or [])
        self.target_files: set[str] = set(target_files or [])
        self.capture_locals = capture_locals
        self.max_depth = max_depth
        self.snapshots: list[StackSnapshot] = []
        self._lock = threading.Lock()
        self._active = False
        self._exclude_files: set[str] = {__file__}

    def add_target(self, function_name: str):
        """Add a function name to capture stacks for."""
        self.target_functions.add(function_name)

    def add_target_file(self, filepath: str):
        """Add a file - all functions in this file will be targets."""
        self.target_files.add(filepath)

    def capture_all(self):
        """Capture stacks for ALL user functions (no filtering)."""
        self.target_functions.clear()
        self.target_files.clear()

    def _should_trace(self, frame) -> bool:
        """Determine if this frame should trigger a stack capture."""
        filename = frame.f_code.co_filename
        func_name = frame.f_code.co_name

        # Skip our own code
        if filename in self._exclude_files:
            return False

        # Skip internal/library functions
        if func_name.startswith('<'):
            return False

        # If no targets specified, capture everything from user code
        if not self.target_functions and not self.target_files:
            # Heuristic: skip standard library and site-packages
            if 'site-packages' in filename or '/lib/python' in filename:
                return False
            return True

        # Check if function or file matches targets
        if func_name in self.target_functions:
            return True
        if any(filename.endswith(tf) for tf in self.target_files):
            return True

        return False

    def _capture_frame(self, frame) -> FrameInfo:
        """Capture info from a single frame."""
        local_vars = {}
        if self.capture_locals:
            for k, v in frame.f_locals.items():
                try:
                    local_vars[k] = repr(v)[:200]  # Truncate long reprs
                except Exception:
                    local_vars[k] = "<unrepresentable>"

        return FrameInfo(
            function=frame.f_code.co_name,
            filename=frame.f_code.co_filename,
            lineno=frame.f_lineno,
            locals=local_vars,
            module=frame.f_globals.get('__name__', ''),
        )

    def _capture_full_stack(self, frame, event: str, arg=None) -> StackSnapshot:
        """Capture the ENTIRE call stack from the given frame up to root."""
        frames = []
        current = frame
        depth = 0

        while current and depth < self.max_depth:
            if current.f_code.co_filename not in self._exclude_files:
                frames.append(self._capture_frame(current))
            current = current.f_back
            depth += 1

        return_value = None
        exception = None

        if event == 'return':
            try:
                return_value = repr(arg)[:200]
            except Exception:
                return_value = "<unrepresentable>"
        elif event == 'exception':
            try:
                exception = f"{arg[0].__name__}: {arg[1]}"
            except Exception:
                exception = str(arg)

        return StackSnapshot(
            frames=frames,
            timestamp=time.time(),
            trigger_function=frame.f_code.co_name,
            trigger_event=event,
            return_value=return_value,
            exception=exception,
            thread_id=threading.get_ident(),
        )

    def _trace_function(self, frame, event, arg):
        """The sys.settrace callback."""
        if not self._active:
            return None

        if event in ('call', 'return', 'exception'):
            if self._should_trace(frame):
                snapshot = self._capture_full_stack(frame, event, arg)
                with self._lock:
                    self.snapshots.append(snapshot)

        return self._trace_function

    def start(self):
        """Start capturing call stacks."""
        self._active = True
        sys.settrace(self._trace_function)

    def stop(self):
        """Stop capturing call stacks."""
        self._active = False
        sys.settrace(None)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def get_snapshots(self) -> list[StackSnapshot]:
        """Return all captured snapshots."""
        return list(self.snapshots)

    def get_snapshots_for(self, function_name: str) -> list[StackSnapshot]:
        """Return snapshots where the given function was the trigger."""
        return [s for s in self.snapshots if s.trigger_function == function_name]

    def get_unique_signatures(self) -> set[tuple[str, ...]]:
        """Return all unique stack signatures observed."""
        return {s.signature for s in self.snapshots}

    def get_call_stacks(self) -> list[StackSnapshot]:
        """Return only 'call' event snapshots."""
        return [s for s in self.snapshots if s.trigger_event == 'call']

    def get_exception_stacks(self) -> list[StackSnapshot]:
        """Return only 'exception' event snapshots."""
        return [s for s in self.snapshots if s.trigger_event == 'exception']

    def clear(self):
        """Clear all captured snapshots."""
        self.snapshots.clear()

    def summary(self) -> dict:
        """Return a summary of captured data."""
        call_snaps = self.get_call_stacks()
        return {
            'total_snapshots': len(self.snapshots),
            'call_events': len(call_snaps),
            'return_events': len([s for s in self.snapshots if s.trigger_event == 'return']),
            'exception_events': len(self.get_exception_stacks()),
            'unique_signatures': len(self.get_unique_signatures()),
            'functions_traced': list({s.trigger_function for s in self.snapshots}),
            'max_depth': max((s.depth for s in self.snapshots), default=0),
        }
