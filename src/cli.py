"""CLI entry point for the GPU Warm-Up Tool.

Parses command-line arguments, loads configuration, runs the warm-up,
prints progress and results to the console, and exits with a non-zero
code if any sessions failed.
"""

import argparse
import asyncio
import sys
import threading

from .app_config import load_app_config, merge_config, validate_required_config
from .models import AppConfig, ProgressEvent, ProgressEventType
from .progress import ProgressEmitter
from .warmup_runner import WarmUpRunner, compute_exit_code


def _parse_args(argv=None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="GPU Warm-Up Tool — warm up Genesys Cloud GPU instances"
    )
    parser.add_argument(
        "--deployment-id",
        required=True,
        help="Genesys Cloud Web Messaging deployment ID",
    )
    parser.add_argument(
        "--region",
        required=True,
        help="Genesys Cloud region (e.g., mypurecloud.com)",
    )
    parser.add_argument(
        "--message",
        default=None,
        help='Warm-up message to send (default: "Warming up!")',
    )
    parser.add_argument(
        "--escalation-message",
        default=None,
        help='Escalation message sent after each agent reply (default: "I want to talk to human agent")',
    )
    parser.add_argument(
        "--disconnect-message",
        default=None,
        help='Agent reply that ends the iteration (default: "Disconnecting now")',
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of warm-up iterations (default: 1)",
    )
    parser.add_argument(
        "--origin",
        default=None,
        help='Origin header for WebSocket auth (default: "https://localhost")',
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Response timeout in seconds (default: 30)",
    )
    return parser.parse_args(argv)


def _validate_cli_args(args: argparse.Namespace) -> list[str]:
    """Validate CLI arguments beyond what argparse handles.

    Args:
        args: Parsed CLI arguments.

    Returns:
        List of validation error messages. Empty if all valid.
    """
    errors = []

    if not args.deployment_id or args.deployment_id.strip() == "":
        errors.append("deployment_id must be non-empty")
    if not args.region or args.region.strip() == "":
        errors.append("region must be non-empty")
    if args.message is not None and args.message.strip() == "":
        errors.append("message must be non-empty")
    if args.escalation_message is not None and args.escalation_message.strip() == "":
        errors.append("escalation_message must be non-empty")
    if args.disconnect_message is not None and args.disconnect_message.strip() == "":
        errors.append("disconnect_message must be non-empty")
    if args.count is not None and args.count < 1:
        errors.append("count must be a positive integer")
    if args.timeout is not None and args.timeout < 1:
        errors.append("timeout must be a positive integer")

    return errors


def _merge_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    """Merge CLI argument overrides into the base config.

    Args:
        config: Base AppConfig loaded from env/file.
        args: Parsed CLI arguments.

    Returns:
        New AppConfig with CLI overrides applied.
    """
    overrides = {}
    if args.deployment_id is not None:
        overrides["deployment_id"] = args.deployment_id
    if args.region is not None:
        overrides["region"] = args.region
    if args.message is not None:
        overrides["message"] = args.message
    if args.escalation_message is not None:
        overrides["escalation_message"] = args.escalation_message
    if args.disconnect_message is not None:
        overrides["disconnect_message"] = args.disconnect_message
    if args.count is not None:
        overrides["count"] = args.count
    if args.origin is not None:
        overrides["origin"] = args.origin
    if args.timeout is not None:
        overrides["timeout"] = args.timeout

    return merge_config(config, overrides)


def _print_report(report) -> None:
    """Print a formatted warm-up report summary to the console.

    Args:
        report: The WarmUpReport to display.
    """
    print("\n" + "=" * 60)
    print("WARM-UP REPORT")
    print("=" * 60)
    print(f"Deployment: {report.deployment_id}")
    print(f"Region: {report.region}")
    print(f"Message: \"{report.message}\"")
    print(f"Duration: {report.total_duration_seconds:.1f}s")
    print(f"Results: {report.successes}/{report.total_iterations} succeeded, "
          f"{report.failures} failed")
    print("-" * 60)

    for result in report.session_results:
        status = "✓ OK" if result.success else "✗ FAILED"
        ttfr_info = f", TTFR: {result.time_to_first_response_seconds:.2f}s" if result.time_to_first_response_seconds is not None else ""
        error_info = f" — {result.error}" if result.error else ""
        print(f"  Session {result.iteration}: {status} "
              f"(Total: {result.duration_seconds:.2f}s{ttfr_info}){error_info}")

    print("-" * 60)
    if report.failures == 0:
        print("✅ ALL SESSIONS SUCCEEDED")
    else:
        print(f"❌ {report.failures} SESSION(S) FAILED")
    print("=" * 60)


def main(argv=None) -> None:
    """CLI entry point. Parse args, load config, run warm-up, print report, exit.

    Args:
        argv: Optional argument list for testing (defaults to sys.argv[1:]).
    """
    args = _parse_args(argv)

    # Validate CLI args
    errors = _validate_cli_args(args)
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    # Load base config from env vars / config file
    config = load_app_config()

    # Merge CLI overrides (highest precedence)
    config = _merge_cli_overrides(config, args)

    # Validate required config
    missing = validate_required_config(config)
    if missing:
        print(
            f"Error: Missing required configuration: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Set up progress emitter
    emitter = ProgressEmitter()

    # Run warm-up
    runner = WarmUpRunner(config=config, progress_emitter=emitter)
    report = asyncio.run(runner.run())

    # Print the formatted report
    _print_report(report)

    # Exit with appropriate code
    sys.exit(compute_exit_code(report))


if __name__ == "__main__":
    main()
