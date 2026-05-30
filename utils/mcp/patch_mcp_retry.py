"""
Monkey-patch the openai-agents SDK to handle asyncio.CancelledError in MCP tool calls.

Version: v7.7 (2026-03-26)
Tested:  23 unit tests + 6 sequential e2e tests + 3 parallel e2e tests — ALL PASS

===========================================================================
PROBLEM
===========================================================================

When an MCP server returns HTTP 502/524/520 or the network drops, the anyio
cancel scope fires and raises asyncio.CancelledError (a BaseException, NOT an
Exception).  The openai-agents SDK only catches Exception, so CancelledError
crashes the entire agent run.

This is especially destructive during parallel tool calls: the SDK runs
multiple MCP tools via asyncio.gather in execute_function_tool_calls.  When
one tool's cancel scope fires, the CancelledError propagates through gather
and cancels ALL sibling tasks — including tools that were succeeding.

===========================================================================
ROOT CAUSE DEEP DIVE (why this took 15+ iterations to fix)
===========================================================================

The core difficulty is anyio's CancelScope internals:

  1. CANCEL SCOPES ARE TASK-BOUND.  When server.connect() enters cancel
     scopes (via AsyncExitStack → streamablehttp_client → anyio task group),
     each scope records _host_task = asyncio.current_task() at __enter__
     time.  CancelScope.__exit__ MUST run in the same task as __enter__ —
     otherwise: RuntimeError("Attempted to exit cancel scope in a different
     task").  This means cleanup() can only be called from the task that
     originally called connect().

  2. CANCEL SCOPES PERSIST UNTIL EXITED.  _deliver_cancellation() iterates
     scope._tasks (which includes _host_task), calls task.cancel(), and
     re-schedules itself via call_soon as long as _tasks is non-empty.
     The ONLY way to stop this cycle is CancelScope.__exit__(), which calls
     _tasks.discard(host_task).  If exit never runs, the scope fires
     task.cancel() on the host task FOREVER — at every await point.

  3. GC-TRIGGERED CANCEL SCOPE FIRING.  When old exit_stacks are garbage
     collected, Python finalizes their async generators (streamablehttp_client
     etc.), which triggers cancel scope __exit__ paths.  If the GC runs in
     the context of the main task, these cancel scopes fire
     _deliver_cancellation on the main task, cascading through any active
     asyncio.gather and cancelling all children.

  4. STALE SESSION IN LAMBDAS.  The SDK's call_tool() captures
     `session = self.session` BEFORE passing a lambda to _run_with_retries.
     After reconnect creates a new session, the lambda still references the
     OLD dead session — the retry fails again with the same error.

  5. PARALLEL RECONNECT STORMS.  When 5 parallel tool calls all fail, all 5
     tasks simultaneously try to cleanup + reconnect the same server, racing
     on the session object and cancel scopes.

Failed approaches along the way:
  - asyncio.shield(cleanup()): Creates inner task → cancel scopes entered by
    original task can't exit in shield's task → persistent cancel loop.
  - asyncio.create_task(connect()): Cancel scopes entered in temporary task
    can't be exited later from the main task → same cross-task problem.
  - Skip cleanup entirely (orphan exit_stack + fresh connect): Works for
    parallel tasks but fails for sequential reconnects — old cancel scopes
    from the killed connection persistently cancel the main task at every
    await point because __exit__ was never called.
  - asyncio.wait_for with timeout: Cancels the inner task on timeout,
    defeating the purpose.

===========================================================================
SOLUTION: DUAL SAME-TASK / DIFFERENT-TASK RECONNECT STRATEGY
===========================================================================

The key insight is that reconnect needs TWO different strategies depending
on which asyncio.Task is attempting it:

  SAME-TASK (sequential / main task):
    The current task IS the one that originally called server.connect().
    Cancel scopes can be properly exited.  We call server.cleanup() (which
    calls exit_stack.aclose(), running all cancel scope __exit__ methods),
    drain residual cancellations, then server.connect() directly.

  DIFFERENT-TASK (parallel / asyncio.gather child):
    The current task is NOT the original — it's a gather child.  Calling
    cleanup() would try to __exit__ cancel scopes entered by the main task
    → RuntimeError.  Instead, we orphan the old exit_stack (keeping a
    strong reference to prevent GC-triggered cancel scope firing), create
    a fresh AsyncExitStack, and connect through it.  Old cancel scopes
    target the main task, not our gather-child task, so we won't get
    cancelled.

  _connect_tasks (WeakKeyDictionary) tracks which task called connect()
  for each server, enabling the same-task vs different-task decision.

===========================================================================
PATCHES (7 total, applied at runtime, no SDK file changes)
===========================================================================

  (connect_track) _patch_connect_track_task:
     Wraps server.connect() to record asyncio.current_task() in
     _connect_tasks[server].  Used by _shielded_reconnect to decide
     between same-task cleanup and different-task orphaning.

  0. _patch_call_tool_late_binding:
     Replace the SDK's captured `session` local variable in call_tool and
     list_tools lambdas with `self.session` (late binding) so that after
     reconnect, retries use the fresh session instead of the dead one.

  1. _patch_run_with_retries:
     Catch CancelledError, drain cancellations via task.uncancel(), and
     retry with exponential backoff + session reconnect.  Uses a per-server
     reconnect lock so parallel tasks don't race — only the first task
     reconnects, the rest wait and reuse the new session.  A session
     generation counter prevents redundant reconnects.

  2. _patch_invoke_mcp_tool:
     Convert CancelledError (both anyio and gather-propagated) to a regular
     Exception so the SDK's invoke_func error handler catches it and returns
     the error to the LLM via failure_error_function.

  3. _patch_to_function_tool:
     Wrap each invoke_func closure to also catch CancelledError from
     sibling-task cancellation.  Each tool independently returns an error
     to the LLM instead of crashing the gather.

  4. _patch_execute_tool_plan:
     Top-level safety net — catch CancelledError escaping from the outer
     asyncio.gather in _execute_tool_plan (which runs
     execute_function_tool_calls alongside execute_computer_actions etc.).
     Returns error results for all function tool runs so the LLM can retry.

  5. _patch_list_tools:
     Auto-reconnect when self.session is None.  After retries exhaust, the
     session stays dead.  On the next turn the SDK calls list_tools() which
     raises UserError("Server not initialized").  This patch catches that
     and attempts reconnect (using the same dual same-task/different-task
     strategy) before giving up.

===========================================================================
KEY INTERNAL STATE
===========================================================================

  _reconnect_locks:       Per-server asyncio.Lock — serializes reconnection
  _session_generations:   Per-server counter — prevents redundant reconnects
  _orphaned_exit_stacks:  Strong refs to old exit_stacks — prevents GC from
                          triggering cancel scopes on the main task
  _connect_tasks:         Maps server → asyncio.Task that called connect()

===========================================================================
USAGE
===========================================================================

  Import and call apply_mcp_retry_patch() once at startup, before any MCP
  calls.  The patch is idempotent (safe to call multiple times).

    from utils.mcp.patch_mcp_retry import apply_mcp_retry_patch
    apply_mcp_retry_patch()

===========================================================================
VERSION HISTORY
===========================================================================

  v1-v3:   Basic CancelledError catch + retry in _run_with_retries.
  v4-v5:   Added invoke_mcp_tool and to_function_tool patches for parallel
           tool call protection.
  v6:      Added _execute_tool_plan safety net.
  v7.0:    Added list_tools auto-reconnect.
  v7.1:    Discovered asyncio.shield creates cross-task cancel scope issue.
  v7.2:    Same-task cleanup (no shield/create_task), retry cleanup 5x.
  v7.3:    Stable — 23 unit + 6 e2e tests pass (sequential only).
  v7.4:    Late-binding session fix for call_tool/list_tools lambdas.
           Discovered cascade cancellation in parallel asyncio.gather.
  v7.5:    Per-server reconnect lock + session generation counter.
  v7.6:    Skip cleanup, orphan exit_stack + fresh connect.  Fixed parallel
           tests but broke sequential (persistent cancel scopes).
  v7.7:    Dual same-task/different-task reconnect strategy.  Track connect
           task via _connect_tasks.  Prevent GC via _orphaned_exit_stacks.
           ALL 32 tests pass (23 unit + 6 sequential e2e + 3 parallel e2e).
"""

import asyncio
import logging
import weakref

logger = logging.getLogger(__name__)

_patched = False

# Per-server reconnect lock and session generation counter.
# Only one task reconnects at a time; others wait and reuse the new session.
_reconnect_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_session_generations: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

# Hold strong references to orphaned exit_stacks so they are NEVER GC'd.
# When an exit_stack is GC'd, its async generators fire cancel scopes that
# call _deliver_cancellation(task.cancel) on the MAIN task, which cascades
# through asyncio.gather and cancels everything.  By preventing GC, the
# cancel scopes never fire.  The old sessions/transports stay open but idle.
_orphaned_exit_stacks: list = []

# Track which asyncio.Task originally called server.connect() for each server.
# Used to decide whether cleanup can be called (same-task) or must be skipped
# (different task, e.g. from asyncio.gather child).
_connect_tasks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _get_reconnect_lock(server) -> asyncio.Lock:
    """Get or create a reconnect lock for the given server instance."""
    lock = _reconnect_locks.get(server)
    if lock is None:
        lock = asyncio.Lock()
        _reconnect_locks[server] = lock
    return lock


def _get_session_generation(server) -> int:
    """Get current session generation counter for the server."""
    return _session_generations.get(server, 0)


def _increment_session_generation(server) -> int:
    """Increment and return new session generation."""
    gen = _session_generations.get(server, 0) + 1
    _session_generations[server] = gen
    return gen


def _drain_cancellations(task: asyncio.Task | None = None) -> int:
    """Call task.uncancel() repeatedly until the cancelling counter reaches 0.

    anyio (or other code) may call task.cancel() multiple times.  Each call
    increments the counter, but a single uncancel() only decrements by 1.
    Returns the number of uncancel() calls made.
    """
    if task is None:
        task = asyncio.current_task()
    if task is None:
        return 0
    n = 0
    while task.cancelling() > 0:
        task.uncancel()
        n += 1
    return n


def _is_anyio_internal_cancel(exc: asyncio.CancelledError) -> bool:
    """Return True if this CancelledError was raised by an anyio cancel scope.

    anyio sets the message to "Cancelled via cancel scope <hex>" when a cancel
    scope fires (e.g. due to a child task failing with an exception like HTTP 502).
    This walks the __context__ chain just like anyio's own is_anyio_cancellation().
    """
    while True:
        if (
            exc.args
            and isinstance(exc.args[0], str)
            and exc.args[0].startswith("Cancelled via cancel scope ")
        ):
            return True
        if isinstance(exc.__context__, asyncio.CancelledError):
            exc = exc.__context__
            continue
        return False


async def _shielded_reconnect(server, original_error, gen_before=None) -> None:
    """Establish a fresh MCP session, replacing the dead one.

    Two strategies depending on context:

    SAME-TASK (sequential / main task): If the current task is the same one
    that originally called server.connect(), we can call server.cleanup()
    safely — the cancel scopes will __exit__ in the correct task.  Then we
    call server.connect() directly.

    DIFFERENT-TASK (parallel / gather child): If we're in a different task
    (e.g. an asyncio.gather child), calling cleanup() would try to __exit__
    cancel scopes entered in the main task → RuntimeError.  Instead, we
    orphan the old exit_stack (keeping a strong reference to prevent GC)
    and connect via a fresh exit_stack.

    PARALLEL SAFETY: A per-server reconnect lock serializes reconnection.
    """
    from contextlib import AsyncExitStack

    if gen_before is not None and _get_session_generation(server) > gen_before:
        logger.info("MCP server '%s' already reconnected by another task (gen)", server.name)
        return

    lock = _get_reconnect_lock(server)

    # Acquire the reconnect lock
    acquired = False
    for lock_attempt in range(20):
        _drain_cancellations()
        try:
            await lock.acquire()
            acquired = True
            break
        except asyncio.CancelledError:
            _drain_cancellations()
            for _ in range(5):
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    pass
                _drain_cancellations()
    if not acquired:
        for _ in range(100):
            _drain_cancellations()
            if gen_before is not None and _get_session_generation(server) > gen_before:
                logger.info("MCP server '%s' reconnected by another task (waited)", server.name)
                return
            try:
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                _drain_cancellations()
        logger.warning("Could not acquire reconnect lock for '%s'", server.name)
        return

    try:
        if gen_before is not None and _get_session_generation(server) > gen_before:
            logger.info("MCP server '%s' already reconnected by another task", server.name)
            return

        server.session = None
        current_task = asyncio.current_task()
        original_task = _connect_tasks.get(server)
        same_task = (original_task is None or original_task is current_task)

        if same_task:
            # SAME-TASK path: cleanup + connect directly.
            # Cancel scopes will __exit__ in the correct task.
            _drain_cancellations()
            try:
                await server.cleanup()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            _drain_cancellations()
            for _ in range(50):
                _drain_cancellations()
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    pass
            _drain_cancellations()

            # Connect directly in the same task
            max_connect_attempts = 5
            for attempt in range(1, max_connect_attempts + 1):
                _drain_cancellations()
                try:
                    await server.connect()
                    _drain_cancellations()
                    _connect_tasks[server] = current_task
                    _increment_session_generation(server)
                    logger.info("MCP server '%s' reconnected successfully (same-task)", server.name)
                    return
                except asyncio.CancelledError:
                    _drain_cancellations()
                    for _ in range(5):
                        try:
                            await asyncio.sleep(0.01)
                        except asyncio.CancelledError:
                            pass
                        _drain_cancellations()
                    if attempt < max_connect_attempts:
                        logger.warning(
                            "Connect attempt %d/%d for '%s' hit cancel, retrying",
                            attempt, max_connect_attempts, server.name,
                        )
                    else:
                        logger.error(
                            "Connect failed after %d attempts for '%s' (all cancelled)",
                            max_connect_attempts, server.name,
                        )
                except Exception as connect_err:
                    _drain_cancellations()
                    logger.error("Connect failed for '%s': %s", server.name, connect_err)
                    raise original_error from connect_err
        else:
            # DIFFERENT-TASK path: orphan old exit_stack, connect in fresh one.
            # Keep strong ref to prevent GC-triggered cancel scopes.
            old_exit_stack = server.exit_stack
            if old_exit_stack is not None:
                _orphaned_exit_stacks.append(old_exit_stack)
            server.exit_stack = AsyncExitStack()

            _drain_cancellations()
            for _ in range(10):
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    pass
                _drain_cancellations()

            # Connect directly.  Old cancel scopes target the MAIN task,
            # not our gather-child task, so we won't get cancelled here.
            max_connect_attempts = 5
            for attempt in range(1, max_connect_attempts + 1):
                _drain_cancellations()
                try:
                    await server.connect()
                    _drain_cancellations()
                    _connect_tasks[server] = current_task
                    _increment_session_generation(server)
                    logger.info("MCP server '%s' reconnected successfully (diff-task)", server.name)
                    return
                except asyncio.CancelledError:
                    _drain_cancellations()
                    for _ in range(5):
                        try:
                            await asyncio.sleep(0.01)
                        except asyncio.CancelledError:
                            pass
                        _drain_cancellations()
                    if attempt < max_connect_attempts:
                        logger.warning(
                            "Connect attempt %d/%d for '%s' hit cancel, retrying",
                            attempt, max_connect_attempts, server.name,
                        )
                    else:
                        logger.error(
                            "Connect failed after %d attempts for '%s' (all cancelled)",
                            max_connect_attempts, server.name,
                        )
                except Exception as connect_err:
                    _drain_cancellations()
                    logger.error("Connect failed for '%s': %s", server.name, connect_err)
                    raise original_error from connect_err
    finally:
        lock.release()


def apply_mcp_retry_patch() -> None:
    """Apply the monkey-patch. Safe to call multiple times (idempotent)."""
    global _patched
    if _patched:
        return
    _patched = True

    _patch_connect_track_task()
    _patch_call_tool_late_binding()
    _patch_run_with_retries()
    _patch_invoke_mcp_tool()
    _patch_to_function_tool()
    _patch_execute_tool_plan()
    _patch_list_tools()
    logger.info("Applied MCP CancelledError retry patches (v7.7: same/diff task reconnect + reconnect lock + late-binding session + list_tools)")


def _patch_connect_track_task() -> None:
    """Patch connect() to record which asyncio.Task called it.

    This is used by _shielded_reconnect to determine whether cleanup can
    be called safely (same task) or must be skipped (different task).
    """
    from agents.mcp.server import _MCPServerWithClientSession

    original_connect = _MCPServerWithClientSession.connect

    async def _patched_connect(self):
        result = await original_connect(self)
        _connect_tasks[self] = asyncio.current_task()
        return result

    _MCPServerWithClientSession.connect = _patched_connect


def _patch_call_tool_late_binding() -> None:
    """Patch call_tool and list_tools to use late-binding session references.

    The SDK captures `session = self.session` BEFORE passing a lambda to
    `_run_with_retries`.  When _run_with_retries catches a CancelledError,
    reconnects (creating a new session), and retries, the lambda still
    references the OLD (dead) session.  The retry then fails again.

    This patch replaces call_tool and list_tools so the lambda uses
    `self.session` (late binding) instead of a captured local variable.
    After reconnect, `self.session` points to the new connection, so
    retries work correctly.
    """
    from agents.mcp.server import _MCPServerWithClientSession
    import httpx
    from agents.exceptions import UserError

    async def _patched_call_tool(self, tool_name, arguments=None, meta=None):
        """call_tool with late-binding session reference."""
        if not self.session:
            raise UserError("Server not initialized. Make sure you call `connect()` first.")

        try:
            self._validate_required_parameters(tool_name=tool_name, arguments=arguments)
            if meta is None:
                # Late binding: self.session is evaluated on each retry
                return await self._run_with_retries(
                    lambda: self.session.call_tool(tool_name, arguments)
                )
            return await self._run_with_retries(
                lambda: self.session.call_tool(tool_name, arguments, meta=meta)
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raise UserError(
                f"Failed to call tool '{tool_name}' on MCP server '{self.name}': "
                f"HTTP error {status_code}"
            ) from e
        except httpx.ConnectError as e:
            raise UserError(
                f"Failed to call tool '{tool_name}' on MCP server '{self.name}': "
                f"Connection lost. The server may have disconnected."
            ) from e

    _MCPServerWithClientSession.call_tool = _patched_call_tool

    # Also fix list_tools' lambda
    original_list_tools_base = _MCPServerWithClientSession.list_tools

    async def _patched_list_tools_late_binding(self, run_context=None, agent=None):
        """list_tools with late-binding session reference."""
        if not self.session:
            raise UserError("Server not initialized. Make sure you call `connect()` first.")

        try:
            if self.cache_tools_list and not self._cache_dirty and self._tools_list:
                tools = self._tools_list
            else:
                # Late binding: self.session is evaluated on each retry
                result = await self._run_with_retries(
                    lambda: self.session.list_tools()
                )
                self._tools_list = result.tools
                self._cache_dirty = False
                tools = self._tools_list

            filtered_tools = tools
            if self.tool_filter is not None:
                filtered_tools = await self._apply_tool_filter(
                    filtered_tools, run_context, agent
                )
            return filtered_tools
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raise UserError(
                f"Failed to list tools from MCP server '{self.name}': HTTP error {status_code}"
            ) from e
        except httpx.ConnectError as e:
            raise UserError(
                f"Failed to list tools from MCP server '{self.name}': Connection lost. "
                f"The server may have disconnected."
            ) from e

    _MCPServerWithClientSession.list_tools = _patched_list_tools_late_binding


def _patch_run_with_retries() -> None:
    """Patch _MCPServerWithClientSession._run_with_retries to handle CancelledError.

    Parallel safety: When multiple tasks hit CE simultaneously (e.g. one
    task's failure causes asyncio.gather to cancel siblings), each task
    enters this handler.  _shielded_reconnect uses a per-server lock so
    only ONE task does cleanup+connect.  The others wait for the lock and
    then find the session already reconnected, skipping cleanup+connect.
    All tasks then retry their call on the new session.
    """
    from agents.mcp.server import _MCPServerWithClientSession

    async def _patched_run_with_retries(self, func):
        attempts = 0
        while True:
            # Capture session generation BEFORE the call.  If reconnect happens
            # (by us or another parallel task), generation increments.  We can
            # then tell _shielded_reconnect to skip if already reconnected.
            gen_before = _get_session_generation(self)
            try:
                return await func()
            except asyncio.CancelledError as e:
                if not _is_anyio_internal_cancel(e):
                    # Real external cancellation — propagate immediately
                    raise

                # anyio cancel scope fired (e.g. 502 killed the HTTP stream)
                # or gather cancelled us because a sibling raised.
                # Drain ALL pending cancellations so subsequent awaits work.
                _drain_cancellations()

                attempts += 1
                if self.max_retry_attempts != -1 and attempts > self.max_retry_attempts:
                    logger.error(
                        "MCP tool call cancelled internally after %d retries, giving up",
                        attempts,
                    )
                    raise
                backoff = self.retry_backoff_seconds_base * (2 ** (attempts - 1))
                logger.warning(
                    "MCP tool call cancelled internally (attempt %d/%d), "
                    "reconnecting in %.1fs …  [%s]",
                    attempts,
                    self.max_retry_attempts + 1,
                    backoff,
                    e.args[0] if e.args else "",
                )
                # Sleep is best-effort — if cancelled by gather, just skip it.
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    _drain_cancellations()
                    logger.warning(
                        "Sleep interrupted by gather cancellation, continuing retry"
                    )
                # Reconnect uses a per-server lock: first task does cleanup+connect,
                # subsequent tasks wait then find session already reconnected.
                try:
                    await _shielded_reconnect(self, e, gen_before)
                except asyncio.CancelledError:
                    _drain_cancellations()
                    logger.warning("Reconnect interrupted by cancel, will retry")
                # After reconnect (or if another task reconnected for us),
                # loop back to retry func() on the new session.
            except Exception:
                attempts += 1
                if self.max_retry_attempts != -1 and attempts > self.max_retry_attempts:
                    raise
                backoff = self.retry_backoff_seconds_base * (2 ** (attempts - 1))
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    _drain_cancellations()

    _MCPServerWithClientSession._run_with_retries = _patched_run_with_retries


def _patch_invoke_mcp_tool() -> None:
    """Patch MCPUtil.invoke_mcp_tool to convert anyio CancelledError to Exception.

    If CancelledError escapes _run_with_retries (e.g. after exhausting retries),
    it would bypass the SDK's invoke_func error handler (which only catches
    Exception). By converting to a regular Exception here, the existing
    failure_error_function surfaces the error to the LLM as a soft tool error.
    """
    from agents.mcp.util import MCPUtil

    original_invoke = MCPUtil.invoke_mcp_tool

    @classmethod
    async def _patched_invoke_mcp_tool(cls, server, tool, context, input_json, *, meta=None):
        try:
            return await original_invoke.__func__(
                cls, server, tool, context, input_json, meta=meta
            )
        except asyncio.CancelledError as e:
            # Drain all pending cancellations so future awaits don't re-raise.
            # We catch BOTH anyio cancels and gather-propagated cancels here.
            # This is safe because invoke_mcp_tool runs inside invoke_func,
            # which catches Exception and returns error to LLM.
            _drain_cancellations()
            is_anyio = _is_anyio_internal_cancel(e)
            logger.error(
                "MCP tool %s on server '%s' failed with CancelledError "
                "(anyio=%s), converting to Exception",
                tool.name,
                server.name,
                is_anyio,
            )
            # Raise as regular Exception so invoke_func's except Exception
            # handler catches it and returns error string to the LLM.
            raise Exception(
                f"MCP tool {tool.name} on server '{server.name}' failed: "
                f"connection cancelled (likely transient server error). "
                f"Please try again."
            ) from e

    MCPUtil.invoke_mcp_tool = _patched_invoke_mcp_tool


def _patch_to_function_tool() -> None:
    """Patch MCPUtil.to_function_tool so each invoke_func also catches CancelledError.

    When anyio cancel scope fires, the parent asyncio Task is cancelled, which
    cancels ALL children in asyncio.gather — including tools that didn't fail.
    The SDK's invoke_func only catches Exception, so CancelledError from sibling
    cancellation escapes and crashes the gather.

    This wraps to_function_tool so each generated invoke_func also handles anyio
    CancelledError: drain the cancellation, and return an error string via
    failure_error_function. Each tool independently reports its error to the LLM,
    which can then retry only the failed tool calls.
    """
    from agents.mcp.util import MCPUtil
    from agents.tool import default_tool_error_function

    original_to_function_tool = MCPUtil.to_function_tool

    @classmethod
    def _patched_to_function_tool(cls, tool, server, convert_schemas_to_strict,
                                  agent=None, failure_error_function=default_tool_error_function):
        func_tool = original_to_function_tool.__func__(
            cls, tool, server, convert_schemas_to_strict,
            agent, failure_error_function=failure_error_function,
        )

        original_on_invoke = func_tool.on_invoke_tool
        effective_failure_error_function = server._get_failure_error_function(
            failure_error_function
        )

        async def _wrapped_invoke(ctx, input_json):
            try:
                return await original_on_invoke(ctx, input_json)
            except asyncio.CancelledError as e:
                # Catch ALL CancelledError — both anyio and gather-propagated.
                # This runs inside run_single_tool's invoke_function_tool call.
                # Any CE here should be converted to an error string for the LLM,
                # not propagated (which would crash the gather).
                _drain_cancellations()
                logger.warning(
                    "MCP tool %s hit CancelledError (anyio=%s, sibling cancel), "
                    "returning error to LLM",
                    tool.name,
                    _is_anyio_internal_cancel(e),
                )
                # Use the same error function the SDK uses for Exception
                err_fn = effective_failure_error_function or default_tool_error_function
                return err_fn(
                    ctx,
                    Exception(
                        f"Tool call cancelled due to transient MCP server error "
                        f"(connection reset). Please try this tool call again."
                    ),
                )

        func_tool.on_invoke_tool = _wrapped_invoke
        return func_tool

    MCPUtil.to_function_tool = _patched_to_function_tool


def _patch_execute_tool_plan() -> None:
    """Patch _execute_tool_plan to catch CancelledError from the outer gather.

    _execute_tool_plan runs asyncio.gather with 5 coroutines:
      execute_function_tool_calls, execute_computer_actions, execute_shell_calls,
      execute_apply_patch_calls, execute_local_shell_calls.

    When anyio cancel scopes propagate CancelledError beyond our inner patches
    (e.g. through hooks, guardrails, or the MCP session's background tasks),
    the CE can escape to this outer gather and crash the entire agent run.

    This patch wraps _execute_tool_plan so that if CE escapes the outer gather,
    we drain cancellations and return error results for all function tool runs.
    The LLM sees the error and can retry the failed tool calls.
    """
    from agents.run_internal import tool_planning, turn_resolution
    from agents.run_internal.tool_execution import (
        FunctionToolResult,
        ToolCallOutputItem,
        ItemHelpers,
    )

    original_fn = tool_planning._execute_tool_plan

    async def _safe_execute_tool_plan(**kwargs):
        try:
            return await original_fn(**kwargs)
        except asyncio.CancelledError:
            _drain_cancellations()
            plan = kwargs.get("plan")
            agent = kwargs.get("agent")
            tool_runs = plan.function_runs if plan else []
            logger.error(
                "_execute_tool_plan gather hit CancelledError "
                "(%d function tool runs), returning errors to LLM",
                len(tool_runs),
            )
            error_msg = (
                "An error occurred while running the tool. The MCP server "
                "connection was interrupted. Please try again."
            )
            error_results = []
            for tool_run in tool_runs:
                run_item = ToolCallOutputItem(
                    output=error_msg,
                    raw_item=ItemHelpers.tool_call_output_item(
                        tool_run.tool_call, error_msg
                    ),
                    agent=agent,
                )
                error_results.append(
                    FunctionToolResult(
                        tool=tool_run.function_tool,
                        output=error_msg,
                        run_item=run_item,
                    )
                )
            # Return the 7-tuple that _execute_tool_plan normally returns:
            # (function_results, input_guardrails, output_guardrails,
            #  computer_results, shell_results, apply_patch_results,
            #  local_shell_results)
            return error_results, [], [], [], [], [], []

    # Replace in all modules that imported the function
    tool_planning._execute_tool_plan = _safe_execute_tool_plan
    turn_resolution._execute_tool_plan = _safe_execute_tool_plan

def _patch_list_tools() -> None:
    """Patch _MCPServerWithClientSession.list_tools to auto-reconnect on stale session.

    After all retry attempts fail, self.session is None (cleanup succeeded but
    connect failed).  On the next agent turn the SDK calls list_tools() which
    raises UserError("Server not initialized").  This crashes the run.

    This patch catches that guard condition and attempts to reconnect before
    retrying list_tools.  If reconnect fails, the original UserError propagates.
    """
    from agents.mcp.server import _MCPServerWithClientSession

    original_list_tools = _MCPServerWithClientSession.list_tools

    async def _patched_list_tools(self, run_context=None, agent=None):
        if self.session is not None:
            return await original_list_tools(self, run_context, agent)

        # Session is dead — try to reconnect before giving up.
        logger.warning(
            "MCP server '%s' session is None in list_tools, attempting reconnect",
            self.name,
        )
        try:
            from contextlib import AsyncExitStack as _AsyncExitStack

            _drain_cancellations()
            current_task = asyncio.current_task()
            original_task = _connect_tasks.get(self)
            same_task = (original_task is None or original_task is current_task)

            if same_task:
                # Same task: cleanup + connect directly
                try:
                    await self.cleanup()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                _drain_cancellations()
                for _ in range(50):
                    _drain_cancellations()
                    try:
                        await asyncio.sleep(0)
                    except asyncio.CancelledError:
                        pass
                _drain_cancellations()
                await self.connect()
            else:
                # Different task: orphan old exit_stack + fresh connect
                old_es = self.exit_stack
                if old_es is not None:
                    _orphaned_exit_stacks.append(old_es)
                self.exit_stack = _AsyncExitStack()
                _drain_cancellations()
                await self.connect()

            _drain_cancellations()
            logger.info(
                "MCP server '%s' reconnected in list_tools", self.name,
            )
        except asyncio.CancelledError:
            _drain_cancellations()
            logger.error(
                "Reconnect in list_tools cancelled for '%s'", self.name,
            )
        except Exception as e:
            logger.error(
                "Reconnect in list_tools failed for '%s': %s", self.name, e,
            )

        # Delegate to original — if session is still None, it raises UserError
        return await original_list_tools(self, run_context, agent)

    _MCPServerWithClientSession.list_tools = _patched_list_tools