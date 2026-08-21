from scraper.services.maydan_service import scrape_meydan
from scraper.services.SPC_scraper import scrape_SPC_activities
from scraper.services.Ajman_scraper import scrape_AFZ_activities
from scraper.services.SHAMS_scraper import scrape_SHAMS_activities
from scraper.services.IFZA_scraper import scrape_IFZA_activities
from scraper.services.DWTC_scraper import scrape_DWTC_activities
from scraper.services.SRTIP_scraper import SRTIPScraper
from scraper.services.RAKEZ_scraper import RAKEZScraper
from scraper.services.ANCF_scraper import ANCFScraper


WEBSITES = {

    "RAKEZ": {
        "scraper": lambda: RAKEZScraper().scrape(),
        "jurisdiction": "RAKEZ"
    },

    "MEYDAN": {
        "scraper": scrape_meydan,
        "jurisdiction": "Meydan"
    },

    "ANCF": {
        "scraper": lambda: ANCFScraper().scrape(),
        "jurisdiction": "ANVC"
    },

    "IFZA": {
        "scraper": scrape_IFZA_activities,
        "jurisdiction": "IFZA"
    },

    "SHAMS": {
        "scraper": scrape_SHAMS_activities,
        "jurisdiction": "SHAMS"
    },

    "SPC": {
        "scraper": scrape_SPC_activities,
        "jurisdiction": "SPC"
    },

    "AFZ": {
        "scraper": scrape_AFZ_activities,
        "jurisdiction": "AFZ"
    },

    "SRTIP": {
        "scraper": lambda: SRTIPScraper().scrape(),
        "jurisdiction": "SRTIP"
    },

    "DWTC": {
        "scraper": scrape_DWTC_activities,
        "jurisdiction": "DWTC"
    },

}