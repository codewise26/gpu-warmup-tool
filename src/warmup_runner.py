"""Warm-Up Runner for executing sequential warm-up iterations."""

import time
from datetime import datetime, timezone

from .models import (
    AppConfig,
    ProgressEvent,
    ProgressEventType,
    SessionResult,
    WarmUpReport,
)
from .progress import ProgressEmitter
from .web_messaging_client import WebMessagingClient, WebMessagingError

def compute_exit_code(report: WarmUpReport) -> int:
    """Compute the exit code from a WarmUpReport.

    Args:
        report: The completed warm-up report.

    Returns:
        0 if all sessions succeeded, 1 if any failed.
    """
    return 0 if report.failures == 0 else 1


class WarmUpRunner:
    """Executes sequential warm-up iterations against a Genesys Cloud deployment.

    Creates a new WebMessagingClient per iteration for session isolation,
    records results, and emits progress events.
    """

    def __init__(self, config: AppConfig, progress_emitter: ProgressEmitter):
        """Initialize with resolved config and progress emitter.

        Args:
            config: The resolved AppConfig with deployment_id, region, etc.
            progress_emitter: The ProgressEmitter for publishing events.
        """
        self.config = config
        self.progress_emitter = progress_emitter

    async def run(self) -> WarmUpReport:
        """Execute all warm-up iterations sequentially.

        For each iteration:
        1. Create a new WebMessagingClient
        2. Connect, send join, wait for welcome
        3. Send warm-up message, then on each agent reply send escalation message
        4. Repeat until agent replies with the configured disconnect message
        5. Disconnect, then proceed to the next iteration
        6. Record SessionResult (success/failure, duration, error)
        7. Emit session_completed progress event

        Returns:
            WarmUpReport with aggregated results.
        """
        deployment_id = self.config.deployment_id
        region = self.config.region
        message = self.config.message
        count = self.config.count

        # Emit warmup_started event
        self.progress_emitter.emit(ProgressEvent(
            event_type=ProgressEventType.WARMUP_STARTED,
            total=count,
            message=f"Starting warm-up: deployment_id={deployment_id}, region={region}, "
                    f"message=\"{message}\", count={count}",
        ))

        session_results: list[SessionResult] = []
        total_start = time.monotonic()

        for i in range(1, count + 1):
            result = await self._run_single_session(i)
            session_results.append(result)

            # Emit session_completed event
            self.progress_emitter.emit(ProgressEvent(
                event_type=ProgressEventType.SESSION_COMPLETED,
                iteration=i,
                total=count,
                success=result.success,
                duration_seconds=result.duration_seconds,
                message=f"Session {i}/{count}: {'OK' if result.success else 'FAILED'} "
                        f"({result.duration_seconds:.1f}s)"
                        + (f" - {result.error}" if result.error else ""),
                session_result=result,
            ))

        total_duration = time.monotonic() - total_start
        successes = sum(1 for r in session_results if r.success)
        failures = count - successes

        report = WarmUpReport(
            deployment_id=deployment_id,
            region=region,
            message=message,
            total_iterations=count,
            successes=successes,
            failures=failures,
            total_duration_seconds=round(total_duration, 2),
            session_results=session_results,
            timestamp=datetime.now(timezone.utc),
        )

        # Emit warmup_completed event
        self.progress_emitter.emit(ProgressEvent(
            event_type=ProgressEventType.WARMUP_COMPLETED,
            total=count,
            message=f"Warm-up complete: {successes}/{count} succeeded, "
                    f"{failures} failed, {total_duration:.1f}s total",
        ))

        return report

    async def _run_single_session(self, iteration: int) -> SessionResult:
        """Execute a single warm-up session.

        Args:
            iteration: The 1-based iteration number.

        Returns:
            SessionResult with success/failure, duration, and error details.
        """
        client = WebMessagingClient(
            region=self.config.region,
            deployment_id=self.config.deployment_id,
            timeout=self.config.timeout,
            origin=self.config.origin,
        )

        start = time.monotonic()
        try:
            await client.connect()
            await client.send_join()
            await client.wait_for_welcome()
            await client.send_message(self.config.message)

            ttfr_start = time.monotonic()
            ttfr: float | None = None

            while True:
                response = await client.receive_response()
                if ttfr is None:
                    ttfr = time.monotonic() - ttfr_start

                if response.strip() == self.config.disconnect_message:
                    break

                await client.send_message(self.config.escalation_message)

            duration = time.monotonic() - start
            return SessionResult(
                iteration=iteration,
                success=True,
                time_to_first_response_seconds=round(ttfr, 2),
                duration_seconds=round(duration, 2),
            )
        except TimeoutError as e:
            duration = time.monotonic() - start
            return SessionResult(
                iteration=iteration,
                success=False,
                duration_seconds=round(duration, 2),
                error=str(e),
            )
        except WebMessagingError as e:
            duration = time.monotonic() - start
            return SessionResult(
                iteration=iteration,
                success=False,
                duration_seconds=round(duration, 2),
                error=str(e),
            )
        except Exception as e:
            duration = time.monotonic() - start
            return SessionResult(
                iteration=iteration,
                success=False,
                duration_seconds=round(duration, 2),
                error=f"Unexpected error: {e}",
            )
        finally:
            await client.disconnect()
