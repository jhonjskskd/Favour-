# =============================================================================
# MODULE 2: b_filter_engine.py — "The Quality Guard"
# =============================================================================
# ROLE IN PIPELINE:
#   Receives the raw leads list from a_serper_engine.py and acts as a semantic
#   gate. Its sole job is to discard corporate/institutional entities and pass
#   through only genuine individual instructors — the "striving solopreneur"
#   persona our outreach is designed for.
#
# DATA FLOW:
#   Input  → Raw leads from SerperLeadEngine.mine_leads()
#             [{"instructor_name": "...", "profile_url": "...", "market_niche": "..."}]
#
#   Output → Filtered subset of the same dicts, now guaranteed to represent
#             real individual creators. This list flows into d_copywriter_engine.py.
#
# WHY THIS MATTERS:
#   Without this filter, messages like "Hi Jane! I noticed you teach Python..."
#   would land in the inbox of "Python Software Academy LLC", making the entire
#   outreach campaign look unprofessional and spammy. This module protects both
#   conversion rates AND sender reputation.
# =============================================================================

import logging
import re

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class FilterEngine:
    """
    The Quality Guard — applies semantic heuristics to distinguish individual
    human instructors from corporate/institutional accounts.

    The filtering logic operates on two fields per lead:
      1. `instructor_name` — checked for corporate keywords and word count
      2. `profile_url`     — checked for corporate URL path segments

    All checks are case-insensitive to catch "academy", "ACADEMY", "Academy".
    """

    # -----------------------------------------------------------------------
    # CORPORATE KEYWORD BLOCKLIST
    # -----------------------------------------------------------------------
    # These terms reliably indicate a non-individual entity. When ANY of these
    # appear in either the instructor's name or their Udemy profile URL slug,
    # the lead is disqualified.
    #
    # Design principle: cast a wide net — it is better to drop a borderline
    # lead than to send a personalised "Hi [Name]!" to a faceless institution.
    # -----------------------------------------------------------------------
    CORPORATE_KEYWORDS = [
        "academy",     "group",        "solutions",   "institute",
        "team",        "lab",          "media",       "learning",
        "consulting",  "studio",       "software",    "university",
        "corporation", "inc",          "llc",         "school",
        "training",    "technologies", "tech",        "digital",
        "hub",         "centre",       "center",      "official",
        "global",      "network",      "systems",     "services",
        "education",   "edu",          "foundation",  "association",
        "community",   "platform",     "co.",         "ltd",
    ]

    # URL path segments that specifically signal a commercial/company account
    # on Udemy (separate from the name-based check so we can log them apart)
    CORPORATE_URL_SEGMENTS = ["company", "business", "organization", "official"]

    # A name with 5+ words is almost certainly an organization title,
    # not a human name (e.g., "National Institute of Technology Training Group")
    MAX_NAME_WORD_COUNT = 4

    # Minimum name length — filters out garbled/empty scrape artifacts
    MIN_NAME_LENGTH = 3

    def __init__(self):
        # Pre-compile the name-check pattern at instantiation time so it
        # is only built once per pipeline run, not once per lead — important
        # for performance when processing hundreds of leads.
        #
        # Pattern explanation:
        #   \b         → word boundary (prevents "inc" matching "ince")
        #   (?:a|b|c)  → non-capturing group of all corporate keywords
        #   \b         → closing word boundary
        #   re.I       → case-insensitive matching
        keyword_pattern = r"\b(?:" + "|".join(
            re.escape(kw) for kw in self.CORPORATE_KEYWORDS
        ) + r")\b"

        self._corporate_name_re = re.compile(keyword_pattern, re.IGNORECASE)

        # Simpler pattern for URL segment checking (no word boundary needed
        # since URL path segments are already separated by "/" or "-")
        url_pattern = "|".join(
            re.escape(seg) for seg in self.CORPORATE_URL_SEGMENTS
        )
        self._corporate_url_re = re.compile(url_pattern, re.IGNORECASE)

    # ------------------------------------------------------------------
    # CORE FILTERING METHOD
    # ------------------------------------------------------------------

    def is_individual_creator(self, lead: dict) -> bool:
        """
        The single most important method in this module. Returns True ONLY
        when a lead passes ALL of the following checks:

        CHECK 1 — Name length (word count)
            A real person's name is 1–4 words. More than that almost always
            means it's an institution name.

        CHECK 2 — Minimum name plausibility
            Rejects blank strings, single characters, or garbled scrape output.

        CHECK 3 — Corporate keyword in name
            Uses a precompiled regex to catch terms like "Academy", "LLC", etc.
            anywhere in the name string.

        CHECK 4 — Corporate keyword in URL
            The Udemy profile slug (the part after /user/) often mirrors the
            account name — catches edge cases missed by name-checking alone.

        CHECK 5 — Corporate URL segment
            Specifically blocks profile URLs containing /company/ or /business/
            path segments which Udemy uses for institutional accounts.

        Args:
            lead (dict): A single lead dict from the Miner, with keys:
                         instructor_name, profile_url, market_niche

        Returns:
            bool: True = keep this lead | False = discard this lead
        """
        name = lead.get("instructor_name", "").strip()
        url  = lead.get("profile_url", "").strip().lower()

        # ── CHECK 1: Word count ─────────────────────────────────────────────
        word_count = len(name.split())
        if word_count > self.MAX_NAME_WORD_COUNT:
            logger.debug(
                f"[Filter] REJECTED (too many words: {word_count}): '{name}'"
            )
            return False

        # ── CHECK 2: Minimum name plausibility ─────────────────────────────
        if len(name) < self.MIN_NAME_LENGTH:
            logger.debug(f"[Filter] REJECTED (name too short): '{name}'")
            return False

        # ── CHECK 3: Corporate keyword in name ─────────────────────────────
        if self._corporate_name_re.search(name):
            matched = self._corporate_name_re.search(name).group()
            logger.debug(
                f"[Filter] REJECTED (corporate keyword '{matched}' in name): "
                f"'{name}'"
            )
            return False

        # ── CHECK 4: Corporate keyword in URL ──────────────────────────────
        # Extract just the slug portion (everything after /user/) for a
        # tighter, more accurate match against the name-derived URL segment
        url_slug = url.split("/user/")[-1].replace("/", " ").replace("-", " ")
        if self._corporate_name_re.search(url_slug):
            logger.debug(
                f"[Filter] REJECTED (corporate keyword in URL slug): '{url}'"
            )
            return False

        # ── CHECK 5: Corporate URL path segment ────────────────────────────
        if self._corporate_url_re.search(url):
            logger.debug(
                f"[Filter] REJECTED (corporate URL segment): '{url}'"
            )
            return False

        # Passed all checks — this looks like a real individual instructor
        return True

    # ------------------------------------------------------------------
    # BATCH PROCESSING METHOD
    # ------------------------------------------------------------------

    def filter_leads(self, raw_leads: list) -> list:
        """
        Applies is_individual_creator() to an entire list of raw leads and
        returns only those that pass. This is the method called by the
        orchestrator in api/index.py.

        Args:
            raw_leads (list): Output from SerperLeadEngine.mine_leads()

        Returns:
            list: A filtered, production-quality subset of the input leads.
                  Safe to pass directly to CopywriterEngine.build_custom_pitches().
        """
        if not raw_leads:
            logger.warning("[Filter] Received empty leads list. Nothing to filter.")
            return []

        qualified = []
        rejected_count = 0

        for lead in raw_leads:
            if self.is_individual_creator(lead):
                qualified.append(lead)
            else:
                rejected_count += 1

        logger.info(
            f"[Filter] Complete. "
            f"Input: {len(raw_leads)} | "
            f"Qualified: {len(qualified)} | "
            f"Rejected: {rejected_count}"
        )
        return qualified
