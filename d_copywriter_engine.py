import urllib.parse

class CopywriterEngine:
    def __init__(self):
        """Initializes the Copywriter with high-converting outreach templates."""
        pass

    def build_custom_pitches(self, lead):
        """
        Takes a clean lead and returns a personalized Email and WhatsApp pitch.
        """
        name = lead.get("instructor_name", "there")
        niche = lead.get("market_niche", "your field")
        url = lead.get("profile_url", "")
        
        # 1. The Professional Email Pitch
        email_subject = f"Question about your {niche} course on Udemy"
        email_body = (
            f"Hi {name},\n\n"
            f"I was just going through your instructor profile on Udemy and was really impressed "
            f"by the depth of your {niche} content. It's clear you've put a lot of work into it.\n\n"
            f"I'm reaching out because I specialize in helping instructors like you scale their "
            f"reach and engagement. I'd love to share a few specific ideas on how to optimize "
            f"your existing presence.\n\n"
            f"Would you be open to a quick chat?\n\n"
            f"Best regards,\n[Your Name]"
        )

        # 2. The Conversational WhatsApp Pitch
        # This is kept short and punchy for high mobile response rates
        wa_text = (
            f"Hi {name}! I found your {niche} profile on Udemy and loved your teaching style. "
            f"I've got a couple of quick ideas to help you boost your course reach. "
            f"Are you open to a quick chat?"
        )
        
        # URL encode for the WhatsApp link
        wa_link = f"https://wa.me/?text={urllib.parse.quote(wa_text)}"
        
        print(f"🧠 Copywriter: Generated pitch for {name}")
        
        return {
            "email_subject": email_subject,
            "email_body": email_body,
            "whatsapp_link": wa_link,
            "status": "PITCH_READY"
        }

