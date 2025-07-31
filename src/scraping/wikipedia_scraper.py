"""
Wikipedia scraper for SpaceX launch historical data using BeautifulSoup.
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


class WikipediaScraperError(Exception):
    """Base exception for Wikipedia scraper errors."""
    pass


class WikipediaScraper:
    """
    Wikipedia scraper for SpaceX launch historical data.
    Uses BeautifulSoup for static content parsing.
    """
    
    WIKIPEDIA_SPACEX_LAUNCHES_URL = "https://en.wikipedia.org/wiki/List_of_Falcon_9_and_Falcon_Heavy_launches"
    WIKIPEDIA_SPACEX_MISSIONS_URL = "https://en.wikipedia.org/wiki/List_of_SpaceX_missions"
    WIKIPEDIA_BASE_URL = "https://en.wikipedia.org"
    
    def __init__(self, ethical_scraper: Optional[EthicalScraper] = None):
        """
        Initialize the Wikipedia scraper.
        
        Args:
            ethical_scraper: EthicalScraper instance for rate limiting and headers
        """
        self.ethical_scraper = ethical_scraper or EthicalScraper()
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info("WikipediaScraper initialized")
    
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
            logger.info("Wikipedia scraper session started")
        except Exception as e:
            logger.error(f"Failed to start Wikipedia scraper session: {e}")
            raise WikipediaScraperError(f"Session initialization failed: {e}")
    
    async def close_session(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("Wikipedia scraper session closed")
    
    async def scrape_launches(self) -> List[LaunchData]:
        """
        Scrape SpaceX launch data from Wikipedia.
        
        Returns:
            List of LaunchData objects
            
        Raises:
            WikipediaScraperError: If scraping fails
        """
        if not self.session:
            raise WikipediaScraperError("Session not initialized. Use async context manager or call start_session()")
        
        try:
            all_launches = []
            
            # Try multiple Wikipedia sources
            urls_to_scrape = [
                self.WIKIPEDIA_SPACEX_LAUNCHES_URL,
                self.WIKIPEDIA_SPACEX_MISSIONS_URL,
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
            
            logger.info(f"Successfully scraped {len(unique_launches)} unique launches from Wikipedia")
            return unique_launches
            
        except Exception as e:
            logger.error(f"Error scraping Wikipedia launches: {e}")
            raise WikipediaScraperError(f"Failed to scrape launches: {e}")
    
    async def _scrape_url(self, url: str) -> List[LaunchData]:
        """
        Scrape launches from a specific Wikipedia URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            List of LaunchData objects
        """
        try:
            # Use ethical scraper for rate limiting and headers
            headers = await self.ethical_scraper.prepare_request(url)
            
            logger.info(f"Scraping Wikipedia URL: {url}")
            
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
            raise WikipediaScraperError(f"Failed to scrape {url}: {e}")
    
    async def _parse_launches_from_html(self, html_content: str, source_url: str) -> List[LaunchData]:
        """
        Parse launch data from Wikipedia HTML content.
        
        Args:
            html_content: HTML content from the page
            source_url: Source URL for context
            
        Returns:
            List of LaunchData objects
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        launches = []
        
        # Wikipedia typically uses tables for launch data
        launches.extend(self._parse_launch_tables(soup))
        
        # Also try parsing from lists
        launches.extend(self._parse_launch_lists(soup))
        
        logger.debug(f"Found {len(launches)} launches from Wikipedia")
        return launches
    
    def _parse_launch_tables(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse launches from Wikipedia tables."""
        launches = []
        
        # Look for tables that contain launch data
        tables = soup.find_all('table', class_=['wikitable', 'sortable'])
        
        for table in tables:
            try:
                # Check if this table contains launch data
                if not self._is_launch_table(table):
                    continue
                
                # Parse table headers to understand column structure
                headers = self._parse_table_headers(table)
                if not headers:
                    continue
                
                # Parse table rows
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    try:
                        launch_data = self._parse_table_row(row, headers)
                        if launch_data:
                            launches.append(launch_data)
                    except Exception as e:
                        logger.debug(f"Error parsing table row: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error parsing table: {e}")
                continue
        
        return launches
    
    def _is_launch_table(self, table) -> bool:
        """Check if a table contains launch data."""
        # Look for launch-related headers
        table_text = table.get_text().lower()
        launch_indicators = [
            'launch', 'mission', 'date', 'rocket', 'payload', 
            'falcon', 'dragon', 'outcome', 'result'
        ]
        
        return sum(1 for indicator in launch_indicators if indicator in table_text) >= 3
    
    def _parse_table_headers(self, table) -> Optional[Dict[str, int]]:
        """Parse table headers to map column names to indices."""
        header_row = table.find('tr')
        if not header_row:
            return None
        
        headers = {}
        cells = header_row.find_all(['th', 'td'])
        
        for i, cell in enumerate(cells):
            header_text = cell.get_text(strip=True).lower()
            
            # Map common header variations to standard names
            if any(word in header_text for word in ['date', 'time']):
                headers['date'] = i
            elif any(word in header_text for word in ['mission', 'name']):
                headers['mission'] = i
            elif any(word in header_text for word in ['rocket', 'vehicle', 'launcher']):
                headers['vehicle'] = i
            elif any(word in header_text for word in ['payload', 'cargo']):
                headers['payload'] = i
            elif any(word in header_text for word in ['outcome', 'result', 'status']):
                headers['outcome'] = i
            elif any(word in header_text for word in ['orbit', 'destination']):
                headers['orbit'] = i
            elif any(word in header_text for word in ['mass', 'weight']):
                headers['mass'] = i
        
        return headers if headers else None
    
    def _parse_table_row(self, row, headers: Dict[str, int]) -> Optional[LaunchData]:
        """Parse a single table row into LaunchData."""
        cells = row.find_all(['td', 'th'])
        
        if len(cells) < max(headers.values()) + 1:
            return None
        
        try:
            # Extract mission name
            mission_name = None
            if 'mission' in headers:
                mission_cell = cells[headers['mission']]
                mission_name = self._extract_text_from_cell(mission_cell)
            
            if not mission_name:
                return None
            
            # Create slug
            slug = self._create_slug(mission_name)
            
            # Extract launch date
            launch_date = None
            if 'date' in headers:
                date_cell = cells[headers['date']]
                launch_date = self._extract_date_from_cell(date_cell)
            
            # Extract vehicle type
            vehicle_type = None
            if 'vehicle' in headers:
                vehicle_cell = cells[headers['vehicle']]
                vehicle_type = self._extract_text_from_cell(vehicle_cell)
            
            # Extract status/outcome
            status = LaunchStatus.UPCOMING
            if 'outcome' in headers:
                outcome_cell = cells[headers['outcome']]
                status = self._extract_status_from_cell(outcome_cell, launch_date)
            
            # Extract payload mass
            payload_mass = None
            if 'mass' in headers:
                mass_cell = cells[headers['mass']]
                payload_mass = self._extract_mass_from_cell(mass_cell)
            
            # Extract orbit
            orbit = None
            if 'orbit' in headers:
                orbit_cell = cells[headers['orbit']]
                orbit = self._extract_text_from_cell(orbit_cell)
            
            # Extract details from payload column or other cells
            details = None
            if 'payload' in headers:
                payload_cell = cells[headers['payload']]
                details = self._extract_text_from_cell(payload_cell)
            
            # Create LaunchData object
            launch_data = LaunchData(
                slug=slug,
                mission_name=mission_name,
                launch_date=launch_date,
                vehicle_type=vehicle_type,
                payload_mass=payload_mass,
                orbit=orbit,
                status=status,
                details=details
            )
            
            logger.debug(f"Extracted Wikipedia launch: {mission_name}")
            return launch_data
            
        except Exception as e:
            logger.debug(f"Error parsing table row: {e}")
            return None
    
    def _extract_text_from_cell(self, cell) -> Optional[str]:
        """Extract clean text from a table cell."""
        if not cell:
            return None
        
        # Remove references and links, keep just the text
        text = cell.get_text(strip=True)
        
        # Remove Wikipedia reference markers like [1], [2], etc.
        text = re.sub(r'\[\d+\]', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text if text and len(text) > 1 else None
    
    def _extract_date_from_cell(self, cell) -> Optional[datetime]:
        """Extract date from a table cell."""
        text = self._extract_text_from_cell(cell)
        if not text:
            return None
        
        # Look for various date formats
        date_patterns = [
            r'(\d{1,2}\s+\w+\s+\d{4})',  # 1 January 2023
            r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 1, 2023
            r'(\d{4}-\d{2}-\d{2})',  # 2023-01-01
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',  # 1/1/2023
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(1)
                    
                    # Try ISO format first
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                    
                    # For other formats, we'd need more sophisticated parsing
                    # For now, return None and let validation handle it
                    
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_status_from_cell(self, cell, launch_date: Optional[datetime]) -> LaunchStatus:
        """Extract launch status from outcome cell."""
        text = self._extract_text_from_cell(cell)
        if not text:
            return self._infer_status_from_date(launch_date)
        
        text_lower = text.lower()
        
        # Look for explicit status indicators
        if any(word in text_lower for word in ['success', 'successful', 'nominal']):
            return LaunchStatus.SUCCESS
        
        if any(word in text_lower for word in ['failure', 'failed', 'lost', 'destroyed']):
            return LaunchStatus.FAILURE
        
        if any(word in text_lower for word in ['abort', 'cancelled', 'scrub']):
            return LaunchStatus.ABORTED
        
        if any(word in text_lower for word in ['partial', 'degraded']):
            return LaunchStatus.SUCCESS  # Partial success still counts as success
        
        # If no explicit status, infer from date
        return self._infer_status_from_date(launch_date)
    
    def _infer_status_from_date(self, launch_date: Optional[datetime]) -> LaunchStatus:
        """Infer status from launch date."""
        if not launch_date:
            return LaunchStatus.UPCOMING
        
        now = datetime.now(timezone.utc)
        if launch_date > now:
            return LaunchStatus.UPCOMING
        else:
            # For historical data, assume success unless explicitly stated otherwise
            return LaunchStatus.SUCCESS
    
    def _extract_mass_from_cell(self, cell) -> Optional[float]:
        """Extract payload mass from cell."""
        text = self._extract_text_from_cell(cell)
        if not text:
            return None
        
        # Look for mass patterns
        mass_patterns = [
            r'(\d+(?:\.\d+)?)\s*kg',
            r'(\d+(?:\.\d+)?)\s*t',  # tonnes
            r'(\d+(?:,\d{3})*)\s*kg',  # with thousands separator
        ]
        
        for pattern in mass_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    mass_str = match.group(1).replace(',', '')
                    mass = float(mass_str)
                    
                    # Convert tonnes to kg if needed
                    if 't' in match.group(0).lower() and 'kg' not in match.group(0).lower():
                        mass *= 1000
                    
                    return mass
                except ValueError:
                    continue
        
        return None
    
    def _parse_launch_lists(self, soup: BeautifulSoup) -> List[LaunchData]:
        """Parse launches from Wikipedia lists (as fallback)."""
        launches = []
        
        # Look for ordered or unordered lists that might contain launch data
        lists = soup.find_all(['ul', 'ol'])
        
        for list_elem in lists:
            # Check if this list contains launch-related content
            list_text = list_elem.get_text().lower()
            if not any(keyword in list_text for keyword in ['launch', 'mission', 'falcon', 'dragon']):
                continue
            
            # Parse list items
            items = list_elem.find_all('li')
            for item in items:
                try:
                    launch_data = self._parse_list_item(item)
                    if launch_data:
                        launches.append(launch_data)
                except Exception as e:
                    logger.debug(f"Error parsing list item: {e}")
                    continue
        
        return launches
    
    def _parse_list_item(self, item) -> Optional[LaunchData]:
        """Parse a list item into LaunchData."""
        text_content = item.get_text(strip=True)
        
        if not text_content or len(text_content) < 20:
            return None
        
        # Extract mission name (usually at the beginning)
        mission_match = re.match(r'^([^:]+)', text_content)
        if not mission_match:
            return None
        
        mission_name = mission_match.group(1).strip()
        slug = self._create_slug(mission_name)
        
        # Extract other information from the text
        launch_date = self._extract_date_from_text(text_content)
        vehicle_type = self._extract_vehicle_from_text(text_content)
        status = self._extract_status_from_text(text_content, launch_date)
        
        try:
            return LaunchData(
                slug=slug,
                mission_name=mission_name,
                launch_date=launch_date,
                vehicle_type=vehicle_type,
                status=status,
                details=text_content[:500] if len(text_content) > 50 else None
            )
        except Exception as e:
            logger.debug(f"Error creating LaunchData from list item: {e}")
            return None
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from free text."""
        date_patterns = [
            r'(\d{1,2}\s+\w+\s+\d{4})',  # 1 January 2023
            r'(\w+\s+\d{1,2},?\s+\d{4})',  # January 1, 2023
            r'(\d{4}-\d{2}-\d{2})',  # 2023-01-01
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(1)
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _extract_vehicle_from_text(self, text: str) -> Optional[str]:
        """Extract vehicle type from free text."""
        vehicle_patterns = [
            r'(Falcon\s+9)',
            r'(Falcon\s+Heavy)',
            r'(Dragon)',
        ]
        
        for pattern in vehicle_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_status_from_text(self, text: str, launch_date: Optional[datetime]) -> LaunchStatus:
        """Extract status from free text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['success', 'successful']):
            return LaunchStatus.SUCCESS
        
        if any(word in text_lower for word in ['failure', 'failed']):
            return LaunchStatus.FAILURE
        
        if any(word in text_lower for word in ['abort', 'cancelled']):
            return LaunchStatus.ABORTED
        
        return self._infer_status_from_date(launch_date)
    
    def _create_slug(self, mission_name: str) -> str:
        """Create a URL-friendly slug from mission name."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', mission_name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure it's not empty
        if not slug:
            slug = f"wiki-mission-{hash(mission_name) % 10000}"
        
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
            source_name="Wikipedia",
            source_url=self.WIKIPEDIA_SPACEX_LAUNCHES_URL,
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.7  # Good quality but community-edited
        )


# Example usage function
async def example_usage():
    """Example of how to use the WikipediaScraper."""
    async with WikipediaScraper() as scraper:
        try:
            launches = await scraper.scrape_launches()
            print(f"Scraped {len(launches)} SpaceX launches from Wikipedia:")
            
            for launch in launches[:5]:  # Show first 5
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