# =============================================================================
# MODULE 4: e_telegram_dispatcher.py — "The Shipper"
# =============================================================================
# ROLE IN PIPELINE:
#   The final delivery stage. Receives a lead dict + pitch dict from the
#   orchestrator (api/index.py) and sends a beautifully formatted Telegram
#   message to your private bot chat. This is how you consume the output of
#   the entire pipeline — one clean card per lead, delivered to your phone.
#
# INTERFACE WITH CopywriterEngine:
#   The CopywriterEngine produces a `pitch` dict:
#       {"email_subject": ..., "email_body": ..., "whatsapp_link": ...}
#
#   The TelegramDispatcher consumes that dict alongside the original `lead`
#   dict to build a rich Telegram message card that surfaces:
#       - Who the lead is (name, niche, profile URL)
#       - The ready-to-send email subject line
#       - A single-click WhatsApp deep-link button
#
#   This means you can act on every lead in under 10 seconds — tap the
#   WhatsApp link, review the pre-written message, and send.
#
# SECURITY NOTE:
#   Bot token and chat ID are stored as class-level constants here for
#   simplicity. In production, move them to environment variables and
#   read them with os.environ.get("TELEGRAM_BOT_TOKEN") etc.
# =============================================================================

import requests
import logging
import os

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class TelegramDispatcher:
    """
    The Shipper — formats lead + pitch data into a Telegram message card and
    dispatches it to a configured bot chat using the Telegram Bot API.

    Uses `sendMessage` with `parse_mode=Markdown` for rich text formatting
    and `inline_keyboard` buttons for one-tap WhatsApp access.
    """

    # ── Bot configuration ──────────────────────────────────────────────────
    # Pull from environment variables if set, otherwise use the provided values.
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8673029559:AAHq_b6Wb1_1P922pUq3s8X_4_o3G1qgC8g")
    CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "7052934254")

    # Telegram Bot API base URL
    API_BASE  = "https://api.telegram.org"

    # Network timeout — keep tight for serverless environment
    REQUEST_TIMEOUT = 8

    def __init__(self):
        # Build the sendMessage endpoint URL once at init time
        self.send_url = (
            f"{self.API_BASE}/bot{self.BOT_TOKEN}/sendMessage"
        )

    # ------------------------------------------------------------------
    # PRIVATE HELPER
    # ------------------------------------------------------------------

    def _build_message_payload(self, lead: dict, pitch: dict) -> dict:
        """
        Assembles the full Telegram API payload dictionary.

        MESSAGE CARD STRUCTURE:
        ┌─────────────────────────────────────────┐
        │ 🎯 NEW LEAD: *John Doe*                 │
        │ 📚 Niche: Python Programming            │
        │ 🔗 Profile: https://udemy.com/user/...  │
        │                                         │
        │ ✉️ Email Subject:                       │
        │ Quick idea for your Python course, John │
        │                                         │
        │ [ 📲 Open WhatsApp Pitch ]  (button)    │
        └─────────────────────────────────────────┘

        Markdown notes:
          *text*  → bold
          `text`  → monospace (used for the email subject for visual separation)
          Plain hyperlinks are auto-detected by Telegram

        The inline keyboard creates a tap-to-open button directly beneath
        the message, linking to the WhatsApp deep-link from CopywriterEngine.

        Args:
            lead  (dict): From FilterEngine — instructor_name, profile_url, market_niche
            pitch (dict): From CopywriterEngine — email_subject, email_body, whatsapp_link

        Returns:
            dict: A complete payload ready to POST to Telegram's sendMessage endpoint.
        """
        name        = lead.get("instructor_name", "Unknown")
        niche       = lead.get("market_niche", "Unknown").title()
        profile_url = lead.get("profile_url", "N/A")
        subject     = pitch.get("email_subject", "N/A")
        wa_link     = pitch.get("whatsapp_link", "")

        # ── Build Markdown message text ────────────────────────────────────
        # Escape special Markdown characters in dynamic fields to prevent
        # the Telegram API from misinterpreting instructor names or URLs.
        def md_safe(text: str) -> str:
            """Escape Telegram Markdown v1 special chars in user-supplied strings."""
            for char in ["_", "*", "[", "]", "(", ")", "~", "`"]:
                text = text.replace(char, f"\\{char}")
            return text

        message_text = (
            f"🎯 *NEW LEAD DETECTED*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Name:* {md_safe(name)}\n"
            f"📚 *Niche:* {md_safe(niche)}\n"
            f"🔗 *Profile:* {profile_url}\n\n"
            f"✉️ *Email Subject Line:*\n"
            f"`{md_safe(subject)}`\n\n"
            f"💡 _Tap the button below to open WhatsApp with the pitch pre-loaded._"
        )

        # ── Inline keyboard: WhatsApp button ──────────────────────────────
        # inline_keyboard is a 2D array: each inner list is one row of buttons.
        # We use a single button row with two buttons: WhatsApp + Udemy Profile.
        inline_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "📲 Open WhatsApp Pitch",
                        "url":  wa_link
                    }
                ],
                [
                    {
                        "text": "👤 View Udemy Profile",
                        "url":  profile_url
                    }
                ]
            ]
        }

        return {
            "chat_id":      self.CHAT_ID,
            "text":         message_text,
            "parse_mode":   "Markdown",
            "reply_markup": inline_keyboard,
            # Disable link previews — they clutter the card when the Udemy
            # URL expands into a full embed
            "disable_web_page_preview": True
        }

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def send_lead_card(self, lead: dict, pitch: dict) -> bool:
        """
        Sends a formatted lead card to the configured Telegram chat.

        Error handling strategy:
          - Network errors (timeout, DNS failure, connection reset) → log + return False
          - Telegram API errors (bad token, invalid chat_id) → log details + return False
          - Unexpected exceptions → log + return False
          - Success → log confirmation + return True

        The boolean return value allows the orchestrator (api/index.py) to
        accurately count how many dispatches succeeded vs. failed without
        ever raising an exception that would halt the pipeline loop.

        Args:
            lead  (dict): Qualified lead from FilterEngine
            pitch (dict): Pitch package from CopywriterEngine

        Returns:
            bool: True on successful delivery, False on any failure.
        """
        instructor_name = lead.get("instructor_name", "Unknown")

        try:
            payload = self._build_message_payload(lead, pitch)

            response = requests.post(
                self.send_url,
                json=payload,
                timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()

            result = response.json()

            if result.get("ok"):
                logger.info(
                    f"[Dispatcher] ✅ Sent lead card for: {instructor_name}"
                )
                return True
            else:
                # Telegram returned HTTP 200 but ok=False — unusual but possible
                # (e.g., chat_id mismatch or bot not started)
                logger.error(
                    f"[Dispatcher] Telegram API returned ok=False for "
                    f"'{instructor_name}': {result.get('description', 'No description')}"
                )
                return False

        except requests.exceptions.Timeout:
            logger.error(
                f"[Dispatcher] TIMEOUT sending card for '{instructor_name}'. "
                "Telegram API unreachable within "
                f"{self.REQUEST_TIMEOUT}s. Lead skipped."
            )
            return False

        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"[Dispatcher] HTTP error for '{instructor_name}': {http_err}. "
                "Check BOT_TOKEN and CHAT_ID."
            )
            return False

        except requests.exceptions.RequestException as req_err:
            logger.error(
                f"[Dispatcher] Network error for '{instructor_name}': {req_err}"
            )
            return False

        except Exception as unexpected_err:
            logger.error(
                f"[Dispatcher] Unexpected error for '{instructor_name}': "
                f"{unexpected_err}"
            )
            return False
