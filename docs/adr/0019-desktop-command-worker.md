# ADR-0019 - Run desktop commands in a dedicated process

- **Date:** 2026-11-18
- **Status:** Accepted for Phase 4C.

## Context

The command panel needs the same arguments, reports, and cancellation behavior as the console CLI. The Windows desktop launcher has no attached console. Commands need their own working directory and output streams, and managed exports need time to remove temporary files on interruption. [Local automation decision](0016-local-automation.md)

## Decision

Start a Python worker with the existing `spawn` and `freeze_support` entry points. The worker invokes the CLI parser with a shared `JobContext` and owns its working directory and streams. A one-way pipe delivers text and throttled render progress. A process event carries cancellation requests. With `--progress`, the CLI still writes its documented progress output. Its Windows console entry point retains the existing signal handling.

Use the existing desktop worker thread to wait on the pipe and reap the child process. Share the window's processing controls so that only one foreground job can run from the window at a time. When closing the window, request cancellation and keep the event loop running until cleanup finishes.

## Consequences

Each command starts with fresh process state and uses the saved project and the engine's existing resource limits. The Windows desktop executable can start its own command worker with the bundled runtime. Command output and recall history are bounded and kept in the window for the session. The panel accepts AstroMosaic arguments and uses the console CLI's exit codes. [Panel workflow and acceptance](../phase-4c.md)
