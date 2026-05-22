# =============================================================================
# MODULE 3: d_copywriter_engine.py — "The Brain"
# =============================================================================
# ROLE IN PIPELINE:
#   Receives a single qualified lead dict from b_filter_engine.py and generates
#   a complete, personalised outreach package: an email subject, email body,
#   and a pre-filled WhatsApp deep-link. Its output is consumed immediately by
#   e_telegram_dispatcher.py, which ships the package to your Telegram bot.
#
# DATA FLOW:
#   Input  → One lead dict:
#             {"instructor_name": "Jane Smith",
#              "profile_url":     "https://www.udemy.com/user/janesmith/",
#              "market_niche":    "python programming"}
#
#   Output → One pitch dict:
#             {"email_subject":  "...",
#              "email_body":     "...",
#              "whatsapp_link":  "https://wa.me/?text=..."}
#
# DESIGN PHILOSOPHY:
#   The messages are written to feel 1-to-1, not broadcast. They reference
#   the instructor's actual niche and name, and they lead with empathy
#   (acknowledging the instructor's effort) before any pitch. This is the
#   difference between a 2% open rate and a 20% one.
# =============================================================================

import urllib.parse
import logging
import random

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class CopywriterEngine:
    """
    The Brain — transforms a bare lead dictionary into a ready-to-send,
    multi-channel outreach package.

    Templates use Python f-string substitution for name/niche personalisation.
    Multiple subject and body variants are stored so that when processing
    a batch of 30+ leads, the messages don't all look identical — which
    would trigger spam filters and reduce reply rates.
    """

    # -----------------------------------------------------------------------
    # MESSAGE TEMPLATES
    # -----------------------------------------------------------------------
    # Each template is a tuple: (subject, body).
    # {first_name} → first word of instructor_name (more personal than full name)
    # {niche}      → market_niche from the lead dict
    # {profile_url}→ their Udemy profile link
    # -----------------------------------------------------------------------

    EMAIL_TEMPLATES = [
        {
            "subject": "Quick idea for your {niche} course, {first_name}",
            "body": (
                "Hi {first_name},\n\n"
                "I came across your {niche} work on Udemy and genuinely impressed "
                "by the depth you bring to it. Building a course from scratch — "
                "the content, the reviews, the algorithm — takes serious commitment.\n\n"
                "I'm reaching out because I work with independent instructors like you "
                "to help grow course revenue without spending more time on content creation. "
                "Most of the instructors I work with see meaningful results within the "
                "first 30 days.\n\n"
                "Would you be open to a quick 15-minute conversation this week? "
                "No pitch decks, just a genuine chat about where you're at and "
                "whether what I do could actually help.\n\n"
                "Either way, keep building — the {niche} space needs more "
                "educators like you.\n\n"
                "Best,\n[Your Name]\n\nP.S. Your profile: {profile_url}"
            )
        },
        {
            "subject": "{first_name}, saw your {niche} course — had a thought",
            "body": (
                "Hey {first_name},\n\n"
                "I spend a lot of time looking at Udemy instructors in the {niche} "
                "space, and your profile caught my attention.\n\n"
                "I help course creators turn their existing content into a more "
                "consistent revenue stream — without recording a single new video. "
                "It's the kind of thing that makes a real difference when you're "
                "doing this alongside a full-time job or other projects.\n\n"
                "I'd love to share what's been working for other {niche} instructors. "
                "Would a short call this week work for you?\n\n"
                "Cheers,\n[Your Name]\n\n{profile_url}"
            )
        },
        {
            "subject": "Helping {niche} instructors grow — wanted to connect",
            "body": (
                "Hi {first_name},\n\n"
                "Found your {niche} course on Udemy while researching the space. "
                "The fact that you're putting in the work to create structured "
                "curriculum in this niche says a lot.\n\n"
                "I partner with independent instructors to handle the growth side "
                "of their course business — things like positioning, external traffic, "
                "and student retention — so they can focus on what they're good at: "
                "teaching.\n\n"
                "If you're open to it, I'd love to share a few specific ideas "
                "for your {niche} course. Takes 15 minutes and there's zero obligation.\n\n"
                "Let me know!\n[Your Name]\n\nProfile: {profile_url}"
            )
        },
    ]

    WHATSAPP_TEMPLATES = [
        (
            "Hi {first_name}! 👋 I came across your {niche} course on Udemy and "
            "really liked what you're building. I help independent instructors grow "
            "their course revenue — mind if I share a quick idea with you? "
            "Takes 5 minutes: {profile_url}"
        ),
        (
            "Hey {first_name}, found your {niche} content on Udemy — impressive work. "
            "I specialise in helping solo instructors scale without burning out. "
            "Would love to connect briefly if you're open to it! {profile_url}"
        ),
        (
            "Hi {first_name} 🙌 Your {niche} course caught my eye on Udemy. "
            "I work with instructors like you to grow income from existing content. "
            "Got 10 mins this week for a quick chat? {profile_url}"
        ),
    ]

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _get_first_name(self, full_name: str) -> str:
        """
        Extracts the first word of the instructor's name for a warmer,
        more personal greeting. Falls back to the full name if splitting fails.

        'Jane Smith'  → 'Jane'
        'John'        → 'John'
        'J. Williams' → 'J.'  (acceptable — still personalised)
        """
        parts = full_name.strip().split()
        return parts[0] if parts else full_name

    def _format_niche(self, niche: str) -> str:
        """
        Converts the raw niche string into title case for use in email copy.
        'python programming' → 'Python Programming'
        """
        return niche.strip().title()

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def build_custom_pitches(self, lead: dict) -> dict:
        """
        The main method. Takes a single validated lead and returns a complete
        outreach package ready for dispatch.

        Template selection uses random.choice() so that a batch of 30 leads
        doesn't produce 30 identical messages — an important deliverability
        safeguard for the email channel and a naturalness signal for WhatsApp.

        Args:
            lead (dict): A qualified lead from FilterEngine.filter_leads().
                         Required keys: instructor_name, profile_url, market_niche

        Returns:
            dict: {
                "email_subject":  str,   — ready for a mail client Subject field
                "email_body":     str,   — ready for a mail client Body field
                "whatsapp_link":  str,   — clickable wa.me deep-link URL
            }

        Raises:
            KeyError: If required lead fields are missing (caught by orchestrator).
        """
        full_name   = lead["instructor_name"]
        profile_url = lead["profile_url"]
        raw_niche   = lead["market_niche"]

        first_name  = self._get_first_name(full_name)
        niche       = self._format_niche(raw_niche)

        # ── Select random email template ───────────────────────────────────
        template = random.choice(self.EMAIL_TEMPLATES)

        substitutions = {
            "first_name":   first_name,
            "niche":        niche,
            "profile_url":  profile_url,
        }

        email_subject = template["subject"].format(**substitutions)
        email_body    = template["body"].format(**substitutions)

        # ── Build WhatsApp deep-link ───────────────────────────────────────
        # wa.me/?text=<URL-encoded message> opens WhatsApp with the text
        # pre-filled in the message composer. The user still needs to press
        # Send — this is by design (keeps the human in the loop for compliance).
        #
        # urllib.parse.quote() handles all special characters:
        #   spaces → %20, & → %26, ? → %3F, etc.
        whatsapp_message = random.choice(self.WHATSAPP_TEMPLATES).format(
            **substitutions
        )
        encoded_message = urllib.parse.quote(whatsapp_message, safe="")
        whatsapp_link   = f"https://wa.me/?text={encoded_message}"

        pitch = {
            "email_subject": email_subject,
            "email_body":    email_body,
            "whatsapp_link": whatsapp_link,
        }

        logger.info(
            f"[Copywriter] Pitch built for: {full_name} | Niche: {niche}"
        )
        return pitch
