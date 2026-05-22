# =============================================================================
# MODULE 1: a_serper_engine.py — "The Miner"
# =============================================================================
# ROLE IN PIPELINE:
#   This is the raw data source — the very first step. It connects to the
#   Serper.dev Google Search API and mines Udemy for individual instructor
#   profile URLs. The output of this module is a raw list of lead dicts that
#   flows directly into b_filter_engine.py for quality screening.
#
# DATA OUTPUT SHAPE:
#   [
#       {
#           "instructor_name": "John Doe",
#           "profile_url":     "https://www.udemy.com/user/johndoe/",
#           "market_niche":    "python programming"
#       },
#       ...
#   ]
# =============================================================================

import requests
import logging
import os

# ---------------------------------------------------------------------------
# Module-level logger. Using __name__ ensures log messages are clearly tagged
# as originating from this file in any aggregated log stream (e.g., Vercel).
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class SerperLeadEngine:
    """
    The Miner — queries Google Search via Serper.dev to find Udemy instructor
    profile pages (not course pages) for a given niche keyword.

    The key trick is the hardcoded `site:udemy.com/user/` prefix in the query,
    which forces Google to return ONLY user-profile URLs, skipping the far more
    numerous course listing pages. This dramatically improves lead relevance
    from the very first step of the pipeline.
    """

    # Serper.dev v1 search endpoint
    SERPER_API_URL = "https://google.serper.dev/search"

    # How many Google results to request per niche (max 100 on Serper)
    RESULTS_PER_NICHE = 30

    # Request timeout in seconds — keeps the serverless function well within
    # Vercel's 10-second cold-start execution window
    REQUEST_TIMEOUT = 8

    def __init__(self, api_key: str):
        """
        Args:
            api_key (str): Your Serper.dev API key. Pass it in from the
                           orchestrator (api/index.py) via an environment
                           variable — never hardcode secrets in source files.
        """
        if not api_key:
            raise ValueError(
                "SerperLeadEngine requires a valid API key. "
                "Set the SERPER_API_KEY environment variable."
            )
        self.api_key = api_key

        # Reusing a single requests.Session across calls provides connection
        # pooling, which reduces latency on repeated requests within one
        # serverless invocation.
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-KEY":    self.api_key,
            "Content-Type": "application/json"
        })

    # ------------------------------------------------------------------
    # PRIVATE HELPER
    # ------------------------------------------------------------------

    def _parse_results(self, raw_results: list, niche: str) -> list:
        """
        Transforms raw Serper API result objects into clean lead dictionaries.

        Serper returns an "organic" list where each item has at minimum:
          - "title"   : the Google result title (usually the instructor's name)
          - "link"    : the full URL of the result
          - "snippet" : a short blurb (unused here, available for future use)

        We extract the instructor name by cleaning up the title field, since
        Udemy profile page titles follow the pattern:
            "John Doe | Udemy Instructor"  →  we take the part before " | "

        Args:
            raw_results (list): The "organic" list from Serper's JSON response.
            niche (str):        The search niche, stored on each lead for
                                downstream use by the CopywriterEngine.

        Returns:
            list: A list of clean lead dictionaries.
        """
        leads = []

        for item in raw_results:
            raw_title = item.get("title", "")
            profile_url = item.get("link", "")

            # Guard: skip any result that isn't actually a /user/ profile URL
            # (Serper occasionally bleeds in tangential results)
            if "udemy.com/user/" not in profile_url:
                continue

            # Extract the instructor's name from the page title.
            # Udemy titles look like: "John Doe | Udemy" or "John Doe - Udemy"
            # We split on common separators and take the first segment.
            name_raw = raw_title.split("|")[0].split(" - ")[0].strip()

            # Skip results with no usable name
            if not name_raw:
                continue

            leads.append({
                "instructor_name": name_raw,
                "profile_url":     profile_url,
                "market_niche":    niche
            })

        return leads

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def mine_leads(self, niches: list) -> list:
        """
        Main entry point. Iterates over a list of niche keywords, fires one
        Serper API request per niche, and collects all instructor leads into
        a single flat list.

        The hardcoded query pattern `site:udemy.com/user/ instructor [niche]`
        is the core intelligence of this module. Breaking it down:
          - `site:udemy.com/user/`  → Google restricts results to this URL path
          - `instructor`            → biases results toward profile pages
          - `[niche]`               → filters for relevance to the target market

        Args:
            niches (list): e.g. ["python programming", "digital marketing",
                                  "guitar lessons", "forex trading"]

        Returns:
            list: All discovered leads across every niche. Empty list on total
                  failure (never raises, so the pipeline can continue).
        """
        all_leads = []

        for niche in niches:
            # ----------------------------------------------------------------
            # Build the precision-targeted Google search query.
            # This single line is why we get profile URLs, not course pages.
            # ----------------------------------------------------------------
            query = f"site:udemy.com/user/ instructor {niche}"

            payload = {
                "q":   query,
                "num": self.RESULTS_PER_NICHE
            }

            logger.info(f"[Miner] Querying Serper for niche: '{niche}' ...")

            try:
                response = self.session.post(
                    self.SERPER_API_URL,
                    json=payload,
                    timeout=self.REQUEST_TIMEOUT
                )

                # Raise an HTTPError for 4xx / 5xx status codes so they fall
                # into our except block rather than silently producing bad data
                response.raise_for_status()

                data = response.json()
                organic_results = data.get("organic", [])

                niche_leads = self._parse_results(organic_results, niche)
                logger.info(
                    f"[Miner] Found {len(niche_leads)} raw leads for '{niche}'"
                )
                all_leads.extend(niche_leads)

            except requests.exceptions.Timeout:
                # Network is too slow — log and continue to the next niche
                # rather than killing the entire pipeline run.
                logger.error(
                    f"[Miner] TIMEOUT on niche '{niche}'. "
                    "Serper API did not respond within "
                    f"{self.REQUEST_TIMEOUT}s. Skipping."
                )

            except requests.exceptions.HTTPError as http_err:
                # Covers 401 Unauthorized (bad key), 429 Rate Limit, etc.
                logger.error(
                    f"[Miner] HTTP error for niche '{niche}': {http_err}. "
                    "Check your SERPER_API_KEY."
                )

            except requests.exceptions.RequestException as req_err:
                # Catch-all for DNS failures, connection resets, etc.
                logger.error(
                    f"[Miner] Network error for niche '{niche}': {req_err}"
                )

            except Exception as unexpected_err:
                # Defensive catch — ensures one bad niche never kills the run
                logger.error(
                    f"[Miner] Unexpected error for niche '{niche}': "
                    f"{unexpected_err}"
                )

        logger.info(
            f"[Miner] Mining complete. Total raw leads collected: "
            f"{len(all_leads)}"
        )
        return all_leads
