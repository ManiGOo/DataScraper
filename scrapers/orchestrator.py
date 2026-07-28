import asyncio

class DiscoveryOrchestrator:
    def __init__(self):
        # We lazily import the specific scrapers to avoid circular dependencies and speed up init
        pass

    async def discover_leads(self, target_region: str, target_sector: str, max_results: int = 10, **kwargs):
        """
        Routes the discovery request to the appropriate regional scraper.
        Returns a list of dicts: [{'name': '...', 'domain': '...', 'website_url': '...', 'source_directory': '...', 'is_sme': True, 'estimated_revenue': '...'}]
        """
        target_region = target_region.lower()
        exclude_domains = kwargs.get('exclude_domains', set())
        
        if 'india' in target_region:
            if 'maps' in target_region:
                from scrapers.middle_east.maps_scraper import MiddleEastMapsScraper
                scraper = MiddleEastMapsScraper()
                return await scraper.discover(target_region, target_sector, max_results, exclude_domains=exclude_domains)
            else:
                from scrapers.india.indiamart_scraper import IndiaMartScraper
                scraper = IndiaMartScraper()
                return await scraper.discover(target_sector, max_results, exclude_domains=exclude_domains)
            
        elif any(country in target_region for country in ['uae', 'oman', 'qatar', 'israel', 'middle east']):
            from scrapers.middle_east.maps_scraper import MiddleEastMapsScraper
            scraper = MiddleEastMapsScraper()
            return await scraper.discover(target_region, target_sector, max_results, exclude_domains=exclude_domains)
            
        elif any(country in target_region for country in ['eu', 'europe', 'germany', 'uk', 'france', 'italy']):
            from scrapers.eu.directory_scraper import EUDirectoryScraper
            scraper = EUDirectoryScraper()
            return await scraper.discover(target_region, target_sector, max_results, exclude_domains=exclude_domains)
            
        else:
            # Fallback to a generic maps scraper if region is unknown
            from scrapers.middle_east.maps_scraper import MiddleEastMapsScraper
            scraper = MiddleEastMapsScraper()
            return await scraper.discover(target_region, target_sector, max_results, exclude_domains=exclude_domains)
