import requests

class TelegramDispatcher:
    def __init__(self):
        self.bot_token = "8673029559:AAHq_b6Wb1_1P922pUq3s8X_4_o3G1qgC8g"
        self.chat_id = "7052934254"

    def send_lead_card(self, lead, pitch):
        """Dispatches the lead and pitch to your Telegram."""
        message = (
            f"🎯 *New Lead Ready!*\n\n"
            f"👤 *Name:* {lead['instructor_name']}\n"
            f"🔗 [Profile Link]({lead['profile_url']})\n\n"
            f"✉️ *Email Pitch:* \n`{pitch['email_body']}`\n\n"
            f"⚡ [CLICK TO LAUNCH WHATSAPP]({pitch['whatsapp_link']})"
        )
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        try:
            requests.post(url, json=payload)
            print(f"🚀 Dispatched lead: {lead['instructor_name']}")
        except Exception as e:
            print(f"❌ Dispatch Error: {e}")
                  
