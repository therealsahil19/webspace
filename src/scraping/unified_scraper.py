"""
Unified data extraction interface for all SpaceX launch data sources.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Union
from pathlib import Path

from ..models.schemas import LaunchData, SourceData
from .ethical_scraper import EthicalScraper
from .spacex_scraper import SpaceXScraper
from .nasa_scraper import NASAScraper
from .wikipedia_scraper import WikipediaScraper
from .pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)


class UnifiedScraperError(Exception):
    """Base exception for unified scraper errors."""
    pass


class UnifiedScraper:
    """
    Unified interface for scraping SpaceX launch data from all sources.
    Coordinates multiple scrapers and provides a single interface for data extraction.
    """
    
    def __init__(self, ethical_scraper: Optional[EthicalScraper] = None):
        """
        Initialize the unified scraper.
        
        Args:
            ethical_scraper: EthicalScraper instance for rate limiting and headers
        """
        self.ethical_scraper = ethical_scraper or EthicalScraper()
        
        # Initialize individual scrapers
        self.spacex_scraper = SpaceXScraper(self.ethical_scraper)
        self.nasa_scraper = NASAScraper(self.ethical_scraper)
        self.wikipedia_scraper = WikipediaScraper(self.ethical_scraper)
        self.pdf_processor = PDFProcessor(self.ethical_scraper)
        
        logger.info("UnifiedScraper initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_all_scrapers()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all_scrapers()
    
    async def start_all_scrapers(self):
        """Start all individual scrapers."""
        try:
            await self.spacex_scraper.start_browser()
            await self.nasa_scraper.start_session()
            await self.wikipedia_scraper.start_session()
            await self.pdf_processor.start_session()
            logger.info("All scrapers started successfully")
        except Exception as e:
            logger.error(f"Error starting scrapers: {e}")
            raise UnifiedScraperError(f"Failed to start scrapers: {e}")
    
    async def close_all_scrapers(self):
        """Close all individual scrapers."""
        errors = []
        
        try:
            await self.spacex_scraper.close_browser()
        except Exception as e:
            errors.append(f"SpaceX scraper: {e}")
        
        try:
            await self.nasa_scraper.close_session()
        except Exception as e:
            errors.append(f"NASA scraper: {e}")
        
        try:
            await self.wikipedia_scraper.close_session()
        except Exception as e:
            errors.append(f"Wikipedia scraper: {e}")
        
        try:
            await self.pdf_processor.close_session()
        except Exception as e:
            errors.append(f"PDF processor: {e}")
        
        if errors:
            logger.warning(f"Errors closing scrapers: {'; '.join(errors)}")
        else:
            logger.info("All scrapers closed successfully")
    
    async def scrape_all_sources(self, 
                                include_sources: Optional[List[str]] = None,
                                exclude_sources: Optional[List[str]] = None) -> Dict[str, List[LaunchData]]:
        """
        Scrape launch data from all available sources.
        
        Args:
            include_sources: List of sources to include ('spacex', 'nasa', 'wikipedia')
            exclude_sources: List of sources to exclude
            
        Returns:
            Dictionary mapping source names to lists of LaunchData objects
            
        Raises:
            UnifiedScraperError: If scraping fails
        """
        available_sources = ['spacex', 'nasa', 'wikipedia']
        
        # Determine which sources to scrape
        if include_sources:
            sources_to_scrape = [s for s in include_sources if s in available_sources]
        else:
            sources_to_scrape = available_sources.copy()
        
        if exclude_sources:
            sources_to_scrape = [s for s in sources_to_scrape if s not in exclude_sources]
        
        if not sources_to_scrape:
            raise UnifiedScraperError("No valid sources specified for scraping")
        
        logger.info(f"Scraping sources: {sources_to_scrape}")
        
        results = {}
        
        # Scrape each source
        for source in sources_to_scrape:
            try:
                if source == 'spacex':
                    launches = await self.spacex_scraper.scrape_launches()
                    results['spacex'] = launches
                    logger.info(f"SpaceX: {len(launches)} launches")
                
                elif source == 'nasa':
                    launches = await self.nasa_scraper.scrape_launches()
                    results['nasa'] = launches
                    logger.info(f"NASA: {len(launches)} launches")
                
                elif source == 'wikipedia':
                    launches = await self.wikipedia_scraper.scrape_launches()
                    results['wikipedia'] = launches
                    logger.info(f"Wikipedia: {len(launches)} launches")
                
            except Exception as e:
                logger.error(f"Error scraping {source}: {e}")
                results[source] = []  # Empty list for failed sources
        
        total_launches = sum(len(launches) for launches in results.values())
        logger.info(f"Total launches scraped: {total_launches}")
        
        return results
    
    async def scrape_with_fallback(self, 
                                  primary_sources: Optional[List[str]] = None,
                                  fallback_sources: Optional[List[str]] = None,
                                  min_launches: int = 1) -> List[LaunchData]:
        """
        Scrape with fallback strategy - try primary sources first, then fallback sources.
        
        Args:
            primary_sources: Primary sources to try first
            fallback_sources: Fallback sources if primary sources fail
            min_launches: Minimum number of launches required to consider scraping successful
            
        Returns:
            List of LaunchData objects from successful sources
        """
        primary_sources = primary_sources or ['spacex']
        fallback_sources = fallback_sources or ['nasa', 'wikipedia']
        
        # Try primary sources first
        logger.info(f"Trying primary sources: {primary_sources}")
        primary_results = await self.scrape_all_sources(include_sources=primary_sources)
        
        # Check if primary sources provided enough data
        primary_launches = []
        for source, launches in primary_results.items():
            primary_launches.extend(launches)
        
        if len(primary_launches) >= min_launches:
            logger.info(f"Primary sources successful: {len(primary_launches)} launches")
            return self._deduplicate_launches(primary_launches)
        
        # Try fallback sources
        logger.info(f"Primary sources insufficient, trying fallback sources: {fallback_sources}")
        fallback_results = await self.scrape_all_sources(include_sources=fallback_sources)
        
        # Combine all results
        all_launches = primary_launches.copy()
        for source, launches in fallback_results.items():
            all_launches.extend(launches)
        
        unique_launches = self._deduplicate_launches(all_launches)
        logger.info(f"Combined results: {len(unique_launches)} unique launches")
        
        return unique_launches
    
    async def process_pdf_sources(self, 
                                 pdf_urls: Optional[List[str]] = None,
                                 pdf_files: Optional[List[Union[str, Path]]] = None) -> List[LaunchData]:
        """
        Process PDF sources for launch data.
        
        Args:
            pdf_urls: List of PDF URLs to process
            pdf_files: List of local PDF files to process
            
        Returns:
            List of LaunchData objects extracted from PDFs
        """
        all_launches = []
        
        # Process PDF URLs
        if pdf_urls:
            logger.info(f"Processing {len(pdf_urls)} PDF URLs")
            for pdf_url in pdf_urls:
                try:
                    launches = await self.pdf_processor.process_pdf_url(pdf_url)
                    all_launches.extend(launches)
                    logger.info(f"PDF URL {pdf_url}: {len(launches)} launches")
                except Exception as e:
                    logger.error(f"Error processing PDF URL {pdf_url}: {e}")
                    continue
        
        # Process local PDF files
        if pdf_files:
            logger.info(f"Processing {len(pdf_files)} local PDF files")
            for pdf_file in pdf_files:
                try:
                    launches = await self.pdf_processor.process_pdf_file(pdf_file)
                    all_launches.extend(launches)
                    logger.info(f"PDF file {pdf_file}: {len(launches)} launches")
                except Exception as e:
                    logger.error(f"Error processing PDF file {pdf_file}: {e}")
                    continue
        
        unique_launches = self._deduplicate_launches(all_launches)
        logger.info(f"Total unique launches from PDFs: {len(unique_launches)}")
        
        return unique_launches
    
    async def get_comprehensive_data(self, 
                                   include_pdfs: bool = False,
                                   pdf_urls: Optional[List[str]] = None,
                                   pdf_files: Optional[List[Union[str, Path]]] = None) -> Dict[str, Any]:
        """
        Get comprehensive launch data from all sources with metadata.
        
        Args:
            include_pdfs: Whether to include PDF processing
            pdf_urls: List of PDF URLs to process
            pdf_files: List of local PDF files to process
            
        Returns:
            Dictionary with launch data and metadata
        """
        start_time = datetime.now(timezone.utc)
        
        # Scrape web sources
        web_results = await self.scrape_all_sources()
        
        # Process PDFs if requested
        pdf_launches = []
        if include_pdfs and (pdf_urls or pdf_files):
            pdf_launches = await self.process_pdf_sources(pdf_urls, pdf_files)
        
        # Combine all launches
        all_launches = []
        for source, launches in web_results.items():
            all_launches.extend(launches)
        all_launches.extend(pdf_launches)
        
        # Deduplicate
        unique_launches = self._deduplicate_launches(all_launches)
        
        # Generate source data
        source_data = []
        for source in ['spacex', 'nasa', 'wikipedia']:
            if source in web_results:
                if source == 'spacex':
                    source_data.append(await self.spacex_scraper.get_source_data())
                elif source == 'nasa':
                    source_data.append(await self.nasa_scraper.get_source_data())
                elif source == 'wikipedia':
                    source_data.append(await self.wikipedia_scraper.get_source_data())
        
        # Add PDF source data if applicable
        if pdf_launches:
            pdf_source = await self.pdf_processor.get_source_data("PDF Sources")
            source_data.append(pdf_source)
        
        end_time = datetime.now(timezone.utc)
        
        return {
            'launches': unique_launches,
            'source_data': source_data,
            'metadata': {
                'total_launches': len(unique_launches),
                'sources_scraped': list(web_results.keys()) + (['pdf'] if pdf_launches else []),
                'scraping_duration': (end_time - start_time).total_seconds(),
                'scraped_at': end_time,
                'source_breakdown': {
                    source: len(launches) for source, launches in web_results.items()
                }
            }
        }
    
    def _deduplicate_launches(self, launches: List[LaunchData]) -> List[LaunchData]:
        """
        Remove duplicate launches based on slug and mission name similarity.
        
        Args:
            launches: List of LaunchData objects
            
        Returns:
            List of unique LaunchData objects
        """
        if not launches:
            return []
        
        # First pass: remove exact slug duplicates
        seen_slugs = set()
        slug_unique = []
        
        for launch in launches:
            if launch.slug not in seen_slugs:
                slug_unique.append(launch)
                seen_slugs.add(launch.slug)
        
        # Second pass: remove similar mission names
        # This is a simple implementation - could be made more sophisticated
        unique_launches = []
        seen_missions = set()
        
        for launch in slug_unique:
            # Normalize mission name for comparison
            normalized_name = self._normalize_mission_name(launch.mission_name)
            
            if normalized_name not in seen_missions:
                unique_launches.append(launch)
                seen_missions.add(normalized_name)
            else:
                # If we have a duplicate, keep the one with more information
                existing_launch = next(
                    l for l in unique_launches 
                    if self._normalize_mission_name(l.mission_name) == normalized_name
                )
                
                if self._launch_has_more_info(launch, existing_launch):
                    # Replace existing with new one
                    index = unique_launches.index(existing_launch)
                    unique_launches[index] = launch
        
        logger.debug(f"Deduplicated {len(launches)} launches to {len(unique_launches)} unique launches")
        return unique_launches
    
    def _normalize_mission_name(self, mission_name: str) -> str:
        """Normalize mission name for comparison."""
        # Convert to lowercase, remove extra spaces and special characters
        normalized = mission_name.lower().strip()
        normalized = ' '.join(normalized.split())  # Normalize whitespace
        
        # Remove common variations
        normalized = normalized.replace('mission', '').strip()
        normalized = normalized.replace('launch', '').strip()
        
        return normalized
    
    def _launch_has_more_info(self, launch1: LaunchData, launch2: LaunchData) -> bool:
        """Check if launch1 has more information than launch2."""
        score1 = self._calculate_info_score(launch1)
        score2 = self._calculate_info_score(launch2)
        return score1 > score2
    
    def _calculate_info_score(self, launch: LaunchData) -> int:
        """Calculate information score for a launch."""
        score = 0
        
        if launch.launch_date:
            score += 2
        if launch.vehicle_type:
            score += 1
        if launch.payload_mass:
            score += 1
        if launch.orbit:
            score += 1
        if launch.details and len(launch.details) > 50:
            score += 2
        if launch.mission_patch_url:
            score += 1
        if launch.webcast_url:
            score += 1
        
        return score
    
    async def get_scraping_statistics(self) -> Dict[str, Any]:
        """Get comprehensive scraping statistics from all components."""
        stats = {
            'ethical_scraper': self.ethical_scraper.get_comprehensive_stats(),
            'scrapers': {
                'spacex': 'Browser-based scraper using Playwright',
                'nasa': 'HTTP-based scraper using aiohttp',
                'wikipedia': 'HTTP-based scraper using aiohttp',
                'pdf_processor': 'PDF processing using pdfplumber'
            },
            'capabilities': {
                'web_scraping': True,
                'pdf_processing': True,
                'rate_limiting': True,
                'robots_txt_compliance': True,
                'header_randomization': True,
                'retry_logic': True,
                'deduplication': True
            }
        }
        
        return stats


# Example usage function
async def example_usage():
    """Example of how to use the UnifiedScraper."""
    async with UnifiedScraper() as scraper:
        try:
            # Get comprehensive data from all sources
            print("Scraping all sources...")
            comprehensive_data = await scraper.get_comprehensive_data()
            
            launches = comprehensive_data['launches']
            metadata = comprehensive_data['metadata']
            
            print(f"\nResults:")
            print(f"Total unique launches: {metadata['total_launches']}")
            print(f"Sources scraped: {metadata['sources_scraped']}")
            print(f"Scraping duration: {metadata['scraping_duration']:.2f} seconds")
            print(f"Source breakdown: {metadata['source_breakdown']}")
            
            print(f"\nFirst 3 launches:")
            for launch in launches[:3]:
                print(f"- {launch.mission_name} ({launch.status})")
                if launch.launch_date:
                    print(f"  Date: {launch.launch_date}")
                if launch.vehicle_type:
                    print(f"  Vehicle: {launch.vehicle_type}")
                print()
            
            # Get scraping statistics
            stats = await scraper.get_scraping_statistics()
            print(f"Scraping capabilities: {list(stats['capabilities'].keys())}")
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())