"""
SpaceX website scraper using Playwright for dynamic content handling.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import re

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

from ..models.schemas import LaunchData, LaunchStatus, SourceData
from .ethical_scraper import EthicalScraper
from .retry_handler import RetryableError

logger = logging.getLogger(__name__)


class SpaceXScraperError(Exception):
    """Base exception for SpaceX scraper errors."""
    pass


class SpaceXScraper:
    """
    SpaceX website scraper using Playwright for JavaScript-heavy content.
    Implements ethical scraping practices and robust error handling.
    """
    
    SPACEX_LAUNCHES_URL = "https://www.spacex.com/launches"
    SPACEX_BASE_URL = "https://www.spacex.com"
    
    def __init__(self, ethical_scraper: Optional[EthicalScraper] = None):
        """
        Initialize the SpaceX scraper.
        
        Args:
            ethical_scraper: EthicalScraper instance for rate limiting and headers
        """
        self.ethical_scraper = ethical_scraper or EthicalScraper()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        logger.info("SpaceXScraper initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_browser()
    
    async def start_browser(self):
        """Start the Playwright browser."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            # Create a new page with realistic viewport
            self.page = await self.browser.new_page(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            logger.info("Playwright browser started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise SpaceXScraperError(f"Browser initialization failed: {e}")
    
    async def close_browser(self):
        """Close the Playwright browser."""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
    
    async def scrape_launches(self) -> List[LaunchData]:
        """
        Scrape launch data from SpaceX website.
        
        Returns:
            List of LaunchData objects
            
        Raises:
            SpaceXScraperError: If scraping fails
        """
        if not self.page:
            raise SpaceXScraperError("Browser not initialized. Use async context manager or call start_browser()")
        
        try:
            # Use ethical scraper for rate limiting and headers
            headers = await self.ethical_scraper.prepare_request(self.SPACEX_LAUNCHES_URL)
            
            # Set headers on the page
            await self.page.set_extra_http_headers(headers)
            
            logger.info(f"Navigating to {self.SPACEX_LAUNCHES_URL}")
            
            # Navigate to launches page with timeout
            await self.page.goto(
                self.SPACEX_LAUNCHES_URL,
                wait_until='networkidle',
                timeout=30000
            )
            
            # Wait for launch content to load
            await self._wait_for_launch_content()
            
            # Get page content
            content = await self.page.content()
            
            # Parse launches from HTML
            launches = await self._parse_launches_from_html(content)
            
            logger.info(f"Successfully scraped {len(launches)} launches from SpaceX")
            return launches
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout while scraping SpaceX: {e}")
            raise RetryableError(f"SpaceX scraping timeout: {e}")
        
        except Exception as e:
            logger.error(f"Error scraping SpaceX launches: {e}")
            raise SpaceXScraperError(f"Failed to scrape launches: {e}")
    
    async def _wait_for_launch_content(self):
        """Wait for launch content to be loaded on the page."""
        try:
            # Wait for common launch-related selectors
            selectors_to_try = [
                '[data-testid="launch-card"]',
                '.launch-card',
                '[class*="launch"]',
                '[class*="mission"]',
                'article',
                '.grid',
                '[data-cy="launch"]'
            ]
            
            for selector in selectors_to_try:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    logger.debug(f"Found launch content with selector: {selector}")
                    return
                except PlaywrightTimeoutError:
                    continue
            
            # If no specific selectors work, wait a bit for dynamic content
            logger.warning("No specific launch selectors found, waiting for general content")
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.warning(f"Error waiting for launch content: {e}")
            # Continue anyway, might still be able to parse
    
    async def _parse_launches_from_html(self, html_content: str) -> List[LaunchData]:
        """
        Parse launch data from HTML content using BeautifulSoup.
        
        Args:
            html_content: HTML content from the page
            
        Returns:
            List of LaunchData objects
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        all_launches = []
        found_slugs = set()  # Track unique launches to avoid duplicates
        
        # Try multiple parsing strategies and combine results
        parsing_strategies = [
            self._parse_strategy_data_testid,
            self._parse_strategy_launch_cards,
            self._parse_strategy_articles,
            self._parse_strategy_generic_grid
        ]
        
        for strategy in parsing_strategies:
            try:
                strategy_launches = strategy(soup)
                if strategy_launches:
                    logger.debug(f"Found {len(strategy_launches)} launches using {strategy.__name__}")
                    # Add unique launches only
                    for launch in strategy_launches:
                        if launch.slug not in found_slugs:
                            all_launches.append(launch)
                            found_slugs.add(launch.slug)
            except Exception as e:
                logger.debug(f"Parsing strategy {strategy.__name__} failed: {e}")
                continue
        
        if not all_launches:
            logger.warning("No launches found with any parsing strategy")
            # Try to extract any text that might contain launch information
            fallback_launches = self._parse_fallback_text_extraction(soup)
            for launch in fallback_launches:
                if launch.slug not in found_slugs:
                    all_launches.append(launch)
                    found_slugs.add(launch.slug)
        
        logger.info(f"Total unique launches found: {len(all_launches)}")
        return all_launches
    
    def _parse_strategy_data_testid(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse using data-testid attributes (modern SpaceX site)."""
        launches = []
        launch_cards = soup.find_all(attrs={'data-testid': re.compile(r'launch|mission')})
        
        for card in launch_cards:
            try:
                launch_data = self._extract_launch_from_element(card)
                if launch_data:
                    launches.append(launch_data)
            except Exception as e:
                logger.debug(f"Error parsing launch card with data-testid: {e}")
                continue
        
        return launches
    
    def _parse_strategy_launch_cards(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse using launch card class names."""
        launches = []
        
        # Look for elements with launch-related class names
        selectors = [
            '.launch-card',
            '[class*="launch"]',
            '[class*="mission"]',
            '[class*="Launch"]',
            '[class*="Mission"]'
        ]
        
        found_slugs = set()  # Track unique launches to avoid duplicates
        
        for selector in selectors:
            cards = soup.select(selector)
            for card in cards:
                try:
                    launch_data = self._extract_launch_from_element(card)
                    if launch_data and launch_data.slug not in found_slugs:
                        launches.append(launch_data)
                        found_slugs.add(launch_data.slug)
                except Exception as e:
                    logger.debug(f"Error parsing launch card with selector {selector}: {e}")
                    continue
        
        return launches
    
    def _parse_strategy_articles(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse using article elements."""
        launches = []
        articles = soup.find_all('article')
        
        for article in articles:
            try:
                # Only process if it looks like launch content
                if self._looks_like_launch_content(article):
                    launch_data = self._extract_launch_from_element(article)
                    if launch_data:
                        launches.append(launch_data)
            except Exception as e:
                logger.debug(f"Error parsing article element: {e}")
                continue
        
        return launches
    
    def _parse_strategy_generic_grid(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse using generic grid or container elements."""
        launches = []
        
        # Look for grid containers that might contain launches
        containers = soup.select('.grid, [class*="grid"], .container, [class*="container"]')
        
        for container in containers:
            # Look for child elements that might be launch items
            items = container.find_all(['div', 'article', 'section'], recursive=False)
            
            for item in items:
                try:
                    # Check if this item contains launch-like content
                    if self._looks_like_launch_content(item):
                        launch_data = self._extract_launch_from_element(item)
                        if launch_data:
                            launches.append(launch_data)
                except Exception as e:
                    logger.debug(f"Error parsing grid item: {e}")
                    continue
        
        return launches
    
    def _parse_fallback_text_extraction(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Fallback parsing using text pattern matching."""
        launches = []
        
        # Extract all text and look for launch-like patterns
        text_content = soup.get_text()
        
        # Look for mission names and dates in the text
        mission_patterns = [
            r'(Starlink|Crew|CRS|NROL|SES|Eutelsat|OneWeb|Transporter)[\s\-]*\d*',
            r'Falcon\s+(9|Heavy)',
            r'Dragon\s+\w+',
        ]
        
        date_patterns = [
            r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',
            r'\b\w+\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b'
        ]
        
        # This is a basic fallback - in a real implementation,
        # you'd want more sophisticated text parsing
        logger.info("Using fallback text extraction - results may be limited")
        
        return launches
    
    def _looks_like_launch_content(self, element) -> bool:
        """Check if an element looks like it contains launch content."""
        text = element.get_text().lower()
        
        # Look for launch-related keywords
        launch_keywords = [
            'falcon', 'dragon', 'starlink', 'crew', 'mission',
            'launch', 'rocket', 'payload', 'orbit', 'landing'
        ]
        
        return any(keyword in text for keyword in launch_keywords)
    
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
            
            if not text_content or len(text_content) < 10:
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
            mission_patch_url = self._extract_mission_patch_url(element)
            webcast_url = self._extract_webcast_url(element)
            
            # Create LaunchData object
            launch_data = LaunchData(
                slug=slug,
                mission_name=mission_name,
                launch_date=launch_date,
                vehicle_type=vehicle_type,
                status=status,
                details=details,
                mission_patch_url=mission_patch_url,
                webcast_url=webcast_url
            )
            
            logger.debug(f"Extracted launch: {mission_name}")
            return launch_data
            
        except Exception as e:
            logger.debug(f"Error extracting launch data: {e}")
            return None
    
    def _extract_mission_name(self, element, text_content: str) -> Optional[str]:
        """Extract mission name from element."""
        # Try to find mission name in various ways
        
        # Look for headings first
        headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text(strip=True)
            if heading_text and len(heading_text) > 3:
                return heading_text
        
        # Look for elements with title-like classes
        title_selectors = [
            '[class*="title"]',
            '[class*="name"]',
            '[class*="mission"]',
            '[class*="heading"]'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if title_text and len(title_text) > 3:
                    return title_text
        
        # Fallback: extract from text using patterns
        mission_patterns = [
            r'(Starlink[\s\-]*\d*[\s\-]*\w*)',
            r'(Crew[\s\-]*\d*[\s\-]*\w*)',
            r'(CRS[\s\-]*\d*)',
            r'(NROL[\s\-]*\d*)',
            r'(\w+[\s\-]*\d*[\s\-]*Mission)',
            r'(Falcon\s+(?:9|Heavy)[\s\-]*\w*)',
        ]
        
        for pattern in mission_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Last resort: use first meaningful line of text
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        if lines:
            first_line = lines[0]
            if 5 <= len(first_line) <= 100:  # Reasonable mission name length
                return first_line
        
        return None
    
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
            r'\b(\d{4}-\d{2}-\d{2})\b',  # ISO format
            r'\b(\w+\s+\d{1,2},?\s+\d{4})\b',  # Month Day, Year
            r'\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b',  # MM/DD/YYYY or DD/MM/YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                try:
                    # Try different date parsing approaches
                    date_str = match if isinstance(match, str) else match[0]
                    
                    # Try ISO format first
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                    
                    # Try other formats (this is simplified - you might want to use dateutil)
                    # For now, return None and let the validation handle it
                    
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_vehicle_type(self, element, text_content: str) -> Optional[str]:
        """Extract vehicle type from element."""
        vehicle_patterns = [
            r'(Falcon\s+9)',
            r'(Falcon\s+Heavy)',
            r'(Starship)',
            r'(Dragon)',
        ]
        
        for pattern in vehicle_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_launch_status(self, element, text_content: str, launch_date: Optional[datetime]) -> LaunchStatus:
        """Extract or infer launch status."""
        text_lower = text_content.lower()
        
        # Look for explicit status indicators first
        if any(word in text_lower for word in ['success', 'successful', 'completed']):
            return LaunchStatus.SUCCESS
        
        if any(word in text_lower for word in ['failure', 'failed', 'unsuccessful']):
            return LaunchStatus.FAILURE
        
        if any(word in text_lower for word in ['abort', 'cancelled', 'scrub']):
            return LaunchStatus.ABORTED
        
        if any(word in text_lower for word in ['in flight', 'flying', 'active']):
            return LaunchStatus.IN_FLIGHT
        
        if any(word in text_lower for word in ['upcoming', 'scheduled', 'planned']):
            return LaunchStatus.UPCOMING
        
        # Infer from date if available and no explicit status found
        if launch_date:
            now = datetime.now(timezone.utc)
            if launch_date > now:
                return LaunchStatus.UPCOMING
            else:
                # For past launches without explicit status, default to success
                # This is reasonable since failed launches are usually explicitly marked
                return LaunchStatus.SUCCESS
        
        # Default to upcoming if no date or status found
        return LaunchStatus.UPCOMING
    
    def _extract_details(self, element, text_content: str) -> Optional[str]:
        """Extract mission details from element."""
        # Look for description or details elements
        detail_selectors = [
            '[class*="description"]',
            '[class*="detail"]',
            '[class*="summary"]',
            'p'
        ]
        
        for selector in detail_selectors:
            detail_elem = element.select_one(selector)
            if detail_elem:
                detail_text = detail_elem.get_text(strip=True)
                if detail_text and len(detail_text) > 20:  # Meaningful details
                    return detail_text[:500]  # Limit length
        
        # Fallback: use part of the text content
        if len(text_content) > 100:
            # Take middle portion, avoiding title and date
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            if len(lines) > 2:
                detail_lines = lines[1:-1]  # Skip first and last line
                details = ' '.join(detail_lines)
                if len(details) > 20:
                    return details[:500]
        
        return None
    
    def _extract_mission_patch_url(self, element) -> Optional[str]:
        """Extract mission patch image URL from element."""
        # Look for images
        images = element.find_all('img')
        for img in images:
            src = img.get('src') or img.get('data-src')
            if src:
                # Make URL absolute
                if src.startswith('/'):
                    src = urljoin(self.SPACEX_BASE_URL, src)
                
                # Check if it looks like a mission patch
                if any(keyword in src.lower() for keyword in ['patch', 'mission', 'logo']):
                    return src
                
                # If it's the only image, assume it's the patch
                if len(images) == 1:
                    return src
        
        return None
    
    def _extract_webcast_url(self, element) -> Optional[str]:
        """Extract webcast URL from element."""
        # Look for links
        links = element.find_all('a')
        for link in links:
            href = link.get('href')
            if href:
                # Check for webcast-related keywords
                link_text = link.get_text().lower()
                if any(keyword in link_text for keyword in ['watch', 'webcast', 'live', 'stream']):
                    if href.startswith('/'):
                        href = urljoin(self.SPACEX_BASE_URL, href)
                    return href
                
                # Check URL for streaming services
                if any(domain in href for domain in ['youtube.com', 'youtu.be', 'twitch.tv']):
                    return href
        
        return None
    
    def _create_slug(self, mission_name: str) -> str:
        """Create a URL-friendly slug from mission name."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', mission_name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure it's not empty
        if not slug:
            slug = f"mission-{hash(mission_name) % 10000}"
        
        return slug
    
    async def get_source_data(self) -> SourceData:
        """Get source data for tracking."""
        return SourceData(
            source_name="SpaceX Official Website",
            source_url=self.SPACEX_LAUNCHES_URL,
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.9  # High quality as it's the official source
        )


# Example usage function
async def example_usage():
    """Example of how to use the SpaceXScraper."""
    async with SpaceXScraper() as scraper:
        try:
            launches = await scraper.scrape_launches()
            print(f"Scraped {len(launches)} launches:")
            
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