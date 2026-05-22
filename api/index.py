from a_serper_engine import SerperLeadEngine
from b_filter_engine import FilterEngine
from d_copywriter_engine import CopywriterEngine
from e_telegram_dispatcher import TelegramDispatcher

def handler(request):
    # 1. Initialize Components
    miner = SerperLeadEngine()
    filter = FilterEngine()
    brain = CopywriterEngine()
    shipper = TelegramDispatcher()
    
    # 2. Run the Factory
    leads = miner.discover_leads("python")
    clean_leads = filter.filter_batch(leads)
    
    # 3. Process and Dispatch
    for lead in clean_leads:
        pitch = brain.build_custom_pitches(lead)
        shipper.send_lead_card(lead, pitch)
        
    return {"status": "Complete", "leads_processed": len(clean_leads)}

