# =============================================================================
# MODULE 5: api/index.py — "The Manager" (Vercel Serverless Entry Point)
# =============================================================================
# ROLE IN PIPELINE:
#   This is the master orchestrator — the single file Vercel invokes when
#   your deployment URL is triggered (via browser, cron job, or webhook).
#   It imports all four engine classes, runs them in sequence, and returns
#   a JSON summary of the entire pipeline's results.
#
# VERCEL RUNTIME:
#   Vercel's Python runtime expects a top-level `handler` function with the
#   signature:  handler(request) → Response-like object
#   We use the BaseHTTPRequestHandler pattern for compatibility.
#
# EXECUTION FLOW:
#   1. Trigger URL hit  → Vercel spins up this function
#   2. SerperLeadEngine mines Google for instructor profiles (30+ results)
#   3. FilterEngine discards corporate/institutional accounts
#   4. For each qualified lead:
#        a. CopywriterEngine builds a personalised pitch package
#        b. TelegramDispatcher sends the formatted card to your Telegram bot
#        c. try/except around each lead — one failure never stops the others
#   5. JSON summary returned to the browser
#
# COLD START OPTIMISATION:
#   - Modules are imported at the top (not inside the handler) so they are
#     cached across warm invocations on the same Vercel worker instance.
#   - No unnecessary disk I/O or sleep() calls.
#   - Tight HTTP timeouts (8s) in each engine ensure we finish within Vercel's
#     default 10s serverless limit. Set maxDuration: 30 in vercel.json for
#     larger niche lists (see vercel.json file in this repo).
# =============================================================================

import json
import os
import logging
import sys

# ---------------------------------------------------------------------------
# Add the project root to sys.path so that imports work correctly when Vercel
# runs this file from the /api subdirectory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from a_serper_engine    import SerperLeadEngine
from b_filter_engine    import FilterEngine
from d_copywriter_engine import CopywriterEngine
from e_telegram_dispatcher import TelegramDispatcher

# ---------------------------------------------------------------------------
# Configure root logger — output goes to Vercel's runtime log stream,
# visible in your Vercel dashboard under Functions > Logs.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


# ===========================================================================
# ★  CONFIGURATION — Edit these niches to target your desired markets
# ===========================================================================
# Add as many niches as you want. Each niche = one Serper API call.
# With RESULTS_PER_NICHE=30 and 4 niches → up to 120 raw leads before filter.
TARGET_NICHES = [
    "python programming",
    "digital marketing",
    "graphic design",
    "personal finance",
    "guitar lessons",
    "forex trading",
    "web development",
    "video editing",
]
# ===========================================================================


def _run_pipeline() -> dict:
    """
    Core pipeline logic, separated from the HTTP handler so it can also be
    called directly (e.g., `python api/index.py` for local testing).

    Returns:
        dict: A summary containing counts and any pipeline-level errors.
    """

    # ── Step 0: Validate environment ──────────────────────────────────────
    serper_api_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_api_key:
        logger.warning(
            "[Orchestrator] SERPER_API_KEY not set. "
            "Set it in Vercel Dashboard > Settings > Environment Variables."
        )
        return {
            "status":  "error",
            "message": "SERPER_API_KEY environment variable is not set.",
            "leads_mined":      0,
            "leads_filtered":   0,
            "leads_dispatched": 0,
        }

    # ── Step 1: MINE ──────────────────────────────────────────────────────
    logger.info("[Orchestrator] === STAGE 1: MINING ===")
    miner  = SerperLeadEngine(api_key=serper_api_key)
    raw_leads = miner.mine_leads(niches=TARGET_NICHES)
    logger.info(f"[Orchestrator] Mined {len(raw_leads)} raw leads.")

    # ── Step 2: FILTER ────────────────────────────────────────────────────
    logger.info("[Orchestrator] === STAGE 2: FILTERING ===")
    guard          = FilterEngine()
    qualified_leads = guard.filter_leads(raw_leads)
    logger.info(f"[Orchestrator] {len(qualified_leads)} leads passed quality filter.")

    if not qualified_leads:
        logger.warning(
            "[Orchestrator] No qualified leads after filtering. "
            "Consider expanding niches or relaxing filter rules."
        )
        return {
            "status":           "completed",
            "leads_mined":      len(raw_leads),
            "leads_filtered":   0,
            "leads_dispatched": 0,
            "message":          "No individual instructors found after filtering."
        }

    # ── Step 3: GENERATE PITCHES + DISPATCH ───────────────────────────────
    logger.info("[Orchestrator] === STAGE 3: COPYWRITING + DISPATCH ===")
    copywriter  = CopywriterEngine()
    dispatcher  = TelegramDispatcher()

    dispatched_count  = 0
    failed_count      = 0

    for index, lead in enumerate(qualified_leads):
        instructor_name = lead.get("instructor_name", f"Lead #{index + 1}")

        # ──────────────────────────────────────────────────────────────────
        # THE QA GUARDRAIL
        # ──────────────────────────────────────────────────────────────────
        # This try/except wraps the ENTIRE per-lead processing block.
        # If the CopywriterEngine crashes (e.g., malformed lead data),
        # OR if the TelegramDispatcher times out — the error is logged,
        # that one lead is skipped, and we move on to lead #2 immediately.
        #
        # Without this, a single bad lead would kill the entire pipeline.
        # ──────────────────────────────────────────────────────────────────
        try:
            logger.info(
                f"[Orchestrator] Processing lead {index + 1}/{len(qualified_leads)}: "
                f"{instructor_name}"
            )

            # 3a: Generate pitch package for this lead
            pitch = copywriter.build_custom_pitches(lead)

            # 3b: Dispatch to Telegram
            success = dispatcher.send_lead_card(lead, pitch)

            if success:
                dispatched_count += 1
            else:
                failed_count += 1
                logger.warning(
                    f"[Orchestrator] Dispatch failed (non-exception) for: "
                    f"{instructor_name}"
                )

        except KeyError as key_err:
            # Missing required field in lead dict — data quality issue
            failed_count += 1
            logger.error(
                f"[Orchestrator] Lead #{index + 1} skipped — missing field: "
                f"{key_err}. Lead data: {lead}"
            )

        except Exception as unexpected_err:
            # Catch-all: log and continue regardless of what went wrong
            failed_count += 1
            logger.error(
                f"[Orchestrator] Lead #{index + 1} ({instructor_name}) "
                f"skipped due to unexpected error: {unexpected_err}"
            )

    logger.info(
        f"[Orchestrator] === PIPELINE COMPLETE === "
        f"Dispatched: {dispatched_count} | Failed: {failed_count}"
    )

    return {
        "status":           "completed",
        "leads_mined":      len(raw_leads),
        "leads_filtered":   len(qualified_leads),
        "leads_dispatched": dispatched_count,
        "leads_failed":     failed_count,
        "message": (
            f"Pipeline complete. "
            f"{dispatched_count} lead cards sent to Telegram "
            f"from {len(raw_leads)} raw results across "
            f"{len(TARGET_NICHES)} niches."
        )
    }


# ===========================================================================
# VERCEL HANDLER — This function is the Vercel Python runtime entry point.
# Vercel expects a class inheriting from BaseHTTPRequestHandler with a
# do_GET method, OR a simple callable. We use the simpler callable form
# which works with Vercel's @vercel/python builder.
# ===========================================================================

class handler:
    """
    Vercel Python Serverless Handler.

    Vercel detects this class and calls it with a BaseHTTPRequestHandler-style
    interface. The do_GET method handles GET requests to the function URL.

    To trigger the pipeline:
      GET https://<your-vercel-app>.vercel.app/api
    """

    def __init__(self, *args, **kwargs):
        from http.server import BaseHTTPRequestHandler
        # Pass through to parent if called in that context
        pass

    def do_GET(self):
        """Handle GET request — runs the full pipeline."""
        logger.info("[Orchestrator] Handler triggered via GET request.")

        summary = _run_pipeline()

        response_body = json.dumps(summary, indent=2).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


# ===========================================================================
# LOCAL TESTING ENTRY POINT
# Run `python api/index.py` from your project root to test the full pipeline
# locally before pushing to Vercel.
# ===========================================================================
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  UDEMY LEAD FACTORY — Local Test Run")
    print("="*60 + "\n")
    result = _run_pipeline()
    print("\n" + "="*60)
    print("  PIPELINE SUMMARY")
    print("="*60)
    print(json.dumps(result, indent=2))
