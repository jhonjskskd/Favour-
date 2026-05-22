import requests

class SerperLeadEngine:
    def __init__(self):
        """Initializes the Serper search gateway with your API credentials."""
        self.api_key = "a564e2bd340fc24dbba7be5dc3db199fb1c5cbbf"
        self.url = "https://google.serper.dev/search"
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    def discover_leads(self, niche):
        """
        Mines 10 high-potential instructor profiles. 
        Uses site-specific targeting to ensure we only get individual creators.
        """
        print(f"📡 Mining leads for niche: {niche}")
        
        # This query is specifically targeted to find individual instructor profiles on Udemy
        query = f"site:udemy.com/user/ instructor {niche}"
        payload = {"q": query, "num": 10}
        
        try:
            response = requests.post(self.url, headers=self.headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])
                
                leads = []
                for res in results:
                    # We extract only the essential data needed for the next steps
                    lead = {
                        "instructor_name": res.get("title", "Creator").split('|')[0].strip(),
                        "profile_url": res.get("link", ""),
                        "market_niche": niche,
                        "status": "RAW_DISCOVERY" # Marker for the next engine to process
                    }
                    leads.append(lead)
                
                print(f"✅ Successfully harvested {len(leads)} leads.")
                return leads
            else:
                print(f"⚠️ Serper API returned error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Miner Critical Error: {str(e)}")
            return []
