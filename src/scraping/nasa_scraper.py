"""
NASA website scraper for SpaceX launch information using BeautifulSoup.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

from ..models.schemas import LaunchData, LaunchStatus, SourceData
from .ethical_scraper import EthicalScraper
from .retry_handler import RetryableError

logger = logging.getLogger(__name__)


class NASAScraperError(Exception):
    """Base exception for NASA scraper errors."""
    pass


class NASAScraper:
    """
    NASA website scraper for SpaceX launch information.
    Uses BeautifulSoup for static content parsing.
    """
    
    NASA_LAUNCHES_URL = "https://www.nasa.gov/news/releases"
    NASA_SPACEX_SEARCH_URL = "https://www.nasa.gov/search/?q=spacex+launch"
    NASA_BASE_URL = "https://www.nasa.gov"
    
    def __init__(self, ethical_scraper: Optional[EthicalScraper] = None):
        """
        Initialize the NASA scraper.
        
        Args:
            ethical_scraper: EthicalScraper instance for rate limiting and headers
        """
        self.ethical_scraper = ethical_scraper or EthicalScraper()
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info("NASAScraper initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()
    
    async def start_session(self):
        """Start the aiohttp session."""
        try:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("NASA scraper session started")
        except Exception as e:
            logger.error(f"Failed to start NASA scraper session: {e}")
            raise NASAScraperError(f"Session initialization failed: {e}")
    
    async def close_session(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("NASA scraper session closed")
    
    async def scrape_launches(self) -> List[LaunchData]:
        """
        Scrape SpaceX launch data from NASA website.
        
        Returns:
            List of LaunchData objects
            
        Raises:
            NASAScraperError: If scraping fails
        """
        if not self.session:
            raise NASAScraperError("Session not initialized. Use async context manager or call start_session()")
        
        try:
            all_launches = []
            
            # Try multiple NASA sources
            urls_to_scrape = [
                self.NASA_SPACEX_SEARCH_URL,
                self.NASA_LAUNCHES_URL,
            ]
            
            for url in urls_to_scrape:
                try:
                    launches = await self._scrape_url(url)
                    all_launches.extend(launches)
                    logger.info(f"Found {len(launches)} launches from {url}")
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
            
            # Remove duplicates based on slug
            unique_launches = self._deduplicate_launches(all_launches)
            
            logger.info(f"Successfully scraped {len(unique_launches)} unique launches from NASA")
            return unique_launches
            
        except Exception as e:
            logger.error(f"Error scraping NASA launches: {e}")
            raise NASAScraperError(f"Failed to scrape launches: {e}")
    
    async def _scrape_url(self, url: str) -> List[LaunchData]:
        """
        Scrape launches from a specific NASA URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            List of LaunchData objects
        """
        try:
            # Use ethical scraper for rate limiting and headers
            headers = await self.ethical_scraper.prepare_request(url)
            
            logger.info(f"Scraping NASA URL: {url}")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise RetryableError(f"HTTP {response.status} for {url}")
                
                html_content = await response.text()
            
            # Parse launches from HTML
            launches = await self._parse_launches_from_html(html_content, url)
            
            return launches
            
        except aiohttp.ClientError as e:
            logger.error(f"Network error scraping {url}: {e}")
            raise RetryableError(f"Network error: {e}")
        
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            raise NASAScraperError(f"Failed to scrape {url}: {e}")
    
    async def _parse_launches_from_html(self, html_content: str, source_url: str) -> List[LaunchData]:
        """
        Parse launch data from NASA HTML content.
        
        Args:
            html_content: HTML content from the page
            source_url: Source URL for context
            
        Returns:
            List of LaunchData objects
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        launches = []
        
        # Try different parsing strategies based on URL
        if "search" in source_url:
            launches.extend(self._parse_search_results(soup))
        else:
            launches.extend(self._parse_news_releases(soup))
        
        # Filter for SpaceX-related launches only
        spacex_launches = [launch for launch in launches if self._is_spacex_related(launch)]
        
        logger.debug(f"Found {len(spacex_launches)} SpaceX-related launches from {len(launches)} total")
        return spacex_launches
    
    def _parse_search_results(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse launches from NASA search results page."""
        launches = []
        
        # Look for search result items
        result_selectors = [
            '.search-result',
            '.result-item',
            '[class*="search"]',
            'article',
            '.news-item'
        ]
        
        for selector in result_selectors:
            results = soup.select(selector)
            if results:
                logger.debug(f"Found {len(results)} results with selector: {selector}")
                for result in results:
                    try:
                        launch_data = self._extract_launch_from_element(result)
                        if launch_data:
                            launches.append(launch_data)
                    except Exception as e:
                        logger.debug(f"Error parsing search result: {e}")
                        continue
                break  # Use first successful selector
        
        return launches
    
    def _parse_news_releases(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse launches from NASA news releases page."""
        launches = []
        
        # Look for news article elements
        article_selectors = [
            'article',
            '.news-item',
            '.press-release',
            '[class*="news"]',
            '[class*="release"]'
        ]
        
        for selector in article_selectors:
            articles = soup.select(selector)
            if articles:
                logger.debug(f"Found {len(articles)} articles with selector: {selector}")
                for article in articles:
                    try:
                        # Only process if it mentions SpaceX
                        if self._mentions_spacex(article):
                            launch_data = self._extract_launch_from_element(article)
                            if launch_data:
                                launches.append(launch_data)
                    except Exception as e:
                        logger.debug(f"Error parsing news article: {e}")
                        continue
                break  # Use first successful selector
        
        return launches
    
    def _mentions_spacex(self, element) -> bool:
        """Check if an element mentions SpaceX."""
        text = element.get_text().lower()
        spacex_keywords = ['spacex', 'space x', 'falcon', 'dragon', 'crew dragon', 'cargo dragon']
        return any(keyword in text for keyword in spacex_keywords)
    
    def _is_spacex_related(self, launch_data: LaunchData) -> bool:
        """Check if launch data is SpaceX-related."""
        text_to_check = f"{launch_data.mission_name} {launch_data.details or ''}".lower()
        spacex_keywords = ['spacex', 'space x', 'falcon', 'dragon', 'crew', 'cargo']
        return any(keyword in text_to_check for keyword in spacex_keywords)
    
    def _extract_launch_from_element(self, element) -> Optional[LaunchData]:
        """
        Extract launch data from a single HTML element.
        
        Args:
            element: BeautifulSoup element containing launch data
            
        Returns:
            LaunchData object or None if extraction fails
        """
        try:
            # Extract text content
            text_content = element.get_text(strip=True)
            
            if not text_content or len(text_content) < 20:
                return None
            
            # Extract mission name
            mission_name = self._extract_mission_name(element, text_content)
            if not mission_name:
                return None
            
            # Create slug from mission name
            slug = self._create_slug(mission_name)
            
            # Extract other data
            launch_date = self._extract_launch_date(element, text_content)
            vehicle_type = self._extract_vehicle_type(element, text_content)
            status = self._extract_launch_status(element, text_content, launch_date)
            details = self._extract_details(element, text_content)
            
            # Create LaunchData object
            launch_data = LaunchData(
                slug=slug,
                mission_name=mission_name,
                launch_date=launch_date,
                vehicle_type=vehicle_type,
                status=status,
                details=details
            )
            
            logger.debug(f"Extracted NASA launch: {mission_name}")
            return launch_data
            
        except Exception as e:
            logger.debug(f"Error extracting launch data from NASA: {e}")
            return None
    
    def _extract_mission_name(self, element, text_content: str) -> Optional[str]:
        """Extract mission name from element."""
        # Look for headings first
        headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text(strip=True)
            if heading_text and len(heading_text) > 5:
                # Clean up NASA-style titles
                cleaned_title = self._clean_nasa_title(heading_text)
                if cleaned_title:
                    return cleaned_title
        
        # Look for title links
        title_links = element.find_all('a', class_=re.compile(r'title|headline'))
        for link in title_links:
            link_text = link.get_text(strip=True)
            if link_text and len(link_text) > 5:
                cleaned_title = self._clean_nasa_title(link_text)
                if cleaned_title:
                    return cleaned_title
        
        # Extract from text using patterns
        mission_patterns = [
            r'(SpaceX\s+(?:Crew|CRS|Cargo)[\s\-]*\d*[\s\-]*\w*)',
            r'(Crew[\s\-]*\d*[\s\-]*Mission)',
            r'(CRS[\s\-]*\d*)',
            r'(Dragon[\s\-]*\w*[\s\-]*Mission)',
            r'(Commercial\s+Crew[\s\-]*\w*)',
        ]
        
        for pattern in mission_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _clean_nasa_title(self, title: str) -> Optional[str]:
        """Clean NASA-style titles to extract mission names."""
        # Remove common NASA prefixes/suffixes
        title = re.sub(r'^(NASA|Press Release|News):\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*NASA$', '', title, flags=re.IGNORECASE)
        
        # If it's too generic, skip it
        generic_terms = ['nasa', 'press release', 'news', 'update', 'statement']
        if any(term in title.lower() for term in generic_terms) and len(title) < 30:
            return None
        
        return title.strip() if len(title) > 5 else None
    
    def _extract_launch_date(self, element, text_content: str) -> Optional[datetime]:
        """Extract launch date from element."""
        # Look for time elements first
        time_elem = element.find('time')
        if time_elem:
            datetime_attr = time_elem.get('datetime')
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                except ValueError:
                    pass
        
        # Look for date patterns in text
        date_patterns = [
            r'\b(\w+\s+\d{1,2},?\s+\d{4})\b',  # Month Day, Year
            r'\b(\d{4}-\d{2}-\d{2})\b',  # ISO format
            r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b',  # MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                try:
                    date_str = match if isinstance(match, str) else match[0]
                    
                    # Try ISO format first
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                    
                    # For other formats, we'd need more sophisticated parsing
                    # For now, return None and let validation handle it
                    
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_vehicle_type(self, element, text_content: str) -> Optional[str]:
        """Extract vehicle type from element."""
        vehicle_patterns = [
            r'(Falcon\s+9)',
            r'(Falcon\s+Heavy)',
            r'(Dragon)',
            r'(Crew\s+Dragon)',
            r'(Cargo\s+Dragon)',
        ]
        
        for pattern in vehicle_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_launch_status(self, element, text_content: str, launch_date: Optional[datetime]) -> LaunchStatus:
        """Extract or infer launch status."""
        text_lower = text_content.lower()
        
        # Look for explicit status indicators
        if any(word in text_lower for word in ['successful', 'success', 'completed', 'landed']):
            return LaunchStatus.SUCCESS
        
        if any(word in text_lower for word in ['failed', 'failure', 'unsuccessful', 'lost']):
            return LaunchStatus.FAILURE
        
        if any(word in text_lower for word in ['abort', 'cancelled', 'scrub', 'delayed']):
            return LaunchStatus.ABORTED
        
        if any(word in text_lower for word in ['upcoming', 'scheduled', 'planned', 'will launch']):
            return LaunchStatus.UPCOMING
        
        # Infer from date if available
        if launch_date:
            now = datetime.now(timezone.utc)
            if launch_date > now:
                return LaunchStatus.UPCOMING
            else:
                return LaunchStatus.SUCCESS  # Assume past launches were successful unless stated otherwise
        
        return LaunchStatus.UPCOMING
    
    def _extract_details(self, element, text_content: str) -> Optional[str]:
        """Extract mission details from element."""
        # Look for description paragraphs
        paragraphs = element.find_all('p')
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            if len(p_text) > 50:  # Meaningful content
                return p_text[:500]  # Limit length
        
        # Fallback: use part of the text content
        if len(text_content) > 100:
            # Take first meaningful paragraph
            sentences = text_content.split('. ')
            if len(sentences) > 1:
                details = '. '.join(sentences[:3])  # First 3 sentences
                if len(details) > 50:
                    return details[:500]
        
        return None
    
    def _create_slug(self, mission_name: str) -> str:
        """Create a URL-friendly slug from mission name."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', mission_name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure it's not empty
        if not slug:
            slug = f"nasa-mission-{hash(mission_name) % 10000}"
        
        return slug
    
    def _deduplicate_launches(self, launches: List[LaunchData]) -> List[LaunchData]:
        """Remove duplicate launches based on slug."""
        seen_slugs = set()
        unique_launches = []
        
        for launch in launches:
            if launch.slug not in seen_slugs:
                unique_launches.append(launch)
                seen_slugs.add(launch.slug)
        
        return unique_launches
    
    async def get_source_data(self) -> SourceData:
        """Get source data for tracking."""
        return SourceData(
            source_name="NASA Official Website",
            source_url=self.NASA_SPACEX_SEARCH_URL,
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.8  # High quality but secondary source
        )


# Example usage function
async def example_usage():
    """Example of how to use the NASAScraper."""
    async with NASAScraper() as scraper:
        try:
            launches = await scraper.scrape_launches()
            print(f"Scraped {len(launches)} SpaceX launches from NASA:")
            
            for launch in launches[:3]:  # Show first 3
                print(f"- {launch.mission_name} ({launch.status})")
                if launch.launch_date:
                    print(f"  Date: {launch.launch_date}")
                if launch.vehicle_type:
                    print(f"  Vehicle: {launch.vehicle_type}")
                print()
            
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())