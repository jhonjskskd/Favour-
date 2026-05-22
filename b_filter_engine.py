import re

class FilterEngine:
    def __init__(self):
        """
        Initializes the Filter with a blacklist of 'Corporate' keywords.
        This ensures we only pitch to individuals, not companies.
        """
        self.corporate_keywords = [
            "Academy", "Group", "Solutions", "Institute", "Team", 
            "Lab", "Media", "Learning", "Consulting", "Studio", 
            "Software", "University", "Corporation", "Inc", "LLC", "Academy"
        ]

    def is_individual_creator(self, lead):
        """
        Deep-scans the name and URL for 'corporate' markers.
        Returns True if the lead is an individual, False if it is a company.
        """
        name = lead.get("instructor_name", "").lower()
        url = lead.get("profile_url", "").lower()
        
        # 1. Filter: Keyword Scan
        # Checks if the name contains any corporate buzzwords
        for word in self.corporate_keywords:
            if word.lower() in name:
                print(f"🚫 Filtered out Corporate entity: {name}")
                return False
        
        # 2. Filter: URL Structure Scan
        # If the URL contains 'company' or generic marketing markers, skip it
        if "company" in url or "business" in url:
            print(f"🚫 Filtered out Business-branded URL: {url}")
            return False
            
        # 3. Filter: Name Complexity
        # If the name is unusually long, it's often a company description
        if len(name.split()) > 5:
            print(f"🚫 Filtered out long corporate title: {name}")
            return False

        return True

    def filter_batch(self, leads):
        """Processes a list of leads and returns only the high-quality individuals."""
        high_quality_leads = [lead for lead in leads if self.is_individual_creator(lead)]
        print(f"✅ Filter Complete: {len(high_quality_leads)} individual creators kept.")
        return high_quality_leads

