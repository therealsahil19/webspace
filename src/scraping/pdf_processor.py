"""
PDF processor for extracting SpaceX launch information from press kits and documents.
"""

import asyncio
import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from urllib.parse import urlparse

import aiohttp
import aiofiles
import pdfplumber

from ..models.schemas import LaunchData, LaunchStatus, SourceData
from .ethical_scraper import EthicalScraper
from .retry_handler import RetryableError

logger = logging.getLogger(__name__)


class PDFProcessorError(Exception):
    """Base exception for PDF processor errors."""
    pass


class PDFProcessor:
    """
    PDF processor for extracting SpaceX launch information from press kits and documents.
    Handles both local files and remote URLs.
    """
    
    def __init__(self, ethical_scraper: Optional[EthicalScraper] = None):
        """
        Initialize the PDF processor.
        
        Args:
            ethical_scraper: EthicalScraper instance for rate limiting and headers
        """
        self.ethical_scraper = ethical_scraper or EthicalScraper()
        self.session: Optional[aiohttp.ClientSession] = None
        
        logger.info("PDFProcessor initialized")
    
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
            timeout = aiohttp.ClientTimeout(total=60, connect=10)  # Longer timeout for PDFs
            self.session = aiohttp.ClientSession(timeout=timeout)
            logger.info("PDF processor session started")
        except Exception as e:
            logger.error(f"Failed to start PDF processor session: {e}")
            raise PDFProcessorError(f"Session initialization failed: {e}")
    
    async def close_session(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("PDF processor session closed")
    
    async def process_pdf_url(self, pdf_url: str) -> List[LaunchData]:
        """
        Process a PDF from a URL.
        
        Args:
            pdf_url: URL of the PDF to process
            
        Returns:
            List of LaunchData objects extracted from the PDF
            
        Raises:
            PDFProcessorError: If processing fails
        """
        if not self.session:
            raise PDFProcessorError("Session not initialized. Use async context manager or call start_session()")
        
        try:
            # Download PDF to temporary file
            temp_file = await self._download_pdf(pdf_url)
            
            try:
                # Process the downloaded PDF
                launches = await self.process_pdf_file(temp_file, source_url=pdf_url)
                return launches
            finally:
                # Clean up temporary file
                try:
                    temp_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_file}: {e}")
            
        except Exception as e:
            logger.error(f"Error processing PDF from URL {pdf_url}: {e}")
            raise PDFProcessorError(f"Failed to process PDF from URL: {e}")
    
    async def process_pdf_file(self, file_path: Union[str, Path], source_url: Optional[str] = None) -> List[LaunchData]:
        """
        Process a local PDF file.
        
        Args:
            file_path: Path to the PDF file
            source_url: Optional source URL for tracking
            
        Returns:
            List of LaunchData objects extracted from the PDF
            
        Raises:
            PDFProcessorError: If processing fails
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise PDFProcessorError(f"PDF file not found: {file_path}")
        
        try:
            logger.info(f"Processing PDF file: {file_path}")
            
            # Extract text from PDF
            text_content = await self._extract_text_from_pdf(file_path)
            
            if not text_content:
                logger.warning(f"No text extracted from PDF: {file_path}")
                return []
            
            # Parse launch data from text
            launches = await self._parse_launches_from_text(text_content, source_url or str(file_path))
            
            logger.info(f"Extracted {len(launches)} launches from PDF: {file_path}")
            return launches
            
        except Exception as e:
            logger.error(f"Error processing PDF file {file_path}: {e}")
            raise PDFProcessorError(f"Failed to process PDF file: {e}")
    
    async def _download_pdf(self, pdf_url: str) -> Path:
        """
        Download a PDF from URL to a temporary file.
        
        Args:
            pdf_url: URL of the PDF to download
            
        Returns:
            Path to the temporary file
        """
        try:
            # Use ethical scraper for rate limiting and headers
            headers = await self.ethical_scraper.prepare_request(pdf_url)
            
            logger.info(f"Downloading PDF from: {pdf_url}")
            
            async with self.session.get(pdf_url, headers=headers) as response:
                if response.status != 200:
                    raise RetryableError(f"HTTP {response.status} for {pdf_url}")
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and not pdf_url.lower().endswith('.pdf'):
                    logger.warning(f"URL may not be a PDF: {pdf_url} (content-type: {content_type})")
                
                # Create temporary file
                temp_file = Path(tempfile.mktemp(suffix='.pdf'))
                
                # Download content
                async with aiofiles.open(temp_file, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                
                logger.info(f"Downloaded PDF to: {temp_file}")
                return temp_file
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error downloading PDF {pdf_url}: {e}")
            raise RetryableError(f"Network error: {e}")
        
        except Exception as e:
            logger.error(f"Error downloading PDF {pdf_url}: {e}")
            raise PDFProcessorError(f"Failed to download PDF: {e}")
    
    async def _extract_text_from_pdf(self, file_path: Path) -> str:
        """
        Extract text content from PDF file.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        try:
            text_content = ""
            
            # Use pdfplumber to extract text
            with pdfplumber.open(file_path) as pdf:
                logger.debug(f"PDF has {len(pdf.pages)} pages")
                
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_content += f"\n--- Page {page_num + 1} ---\n"
                            text_content += page_text
                            text_content += "\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                        continue
            
            logger.debug(f"Extracted {len(text_content)} characters from PDF")
            return text_content
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise PDFProcessorError(f"Failed to extract text from PDF: {e}")
    
    async def _parse_launches_from_text(self, text_content: str, source_identifier: str) -> List[LaunchData]:
        """
        Parse launch data from extracted PDF text.
        
        Args:
            text_content: Extracted text from PDF
            source_identifier: Source identifier for tracking
            
        Returns:
            List of LaunchData objects
        """
        launches = []
        
        # Try different parsing strategies
        parsing_strategies = [
            self._parse_press_kit_format,
            self._parse_mission_overview_format,
            self._parse_technical_document_format,
            self._parse_generic_text_format
        ]
        
        for strategy in parsing_strategies:
            try:
                strategy_launches = strategy(text_content, source_identifier)
                if strategy_launches:
                    logger.debug(f"Found {len(strategy_launches)} launches using {strategy.__name__}")
                    launches.extend(strategy_launches)
                    break  # Use first successful strategy
            except Exception as e:
                logger.debug(f"Parsing strategy {strategy.__name__} failed: {e}")
                continue
        
        # Remove duplicates
        unique_launches = self._deduplicate_launches(launches)
        
        return unique_launches
    
    def _parse_press_kit_format(self, text: str, source_identifier: str) -> List[LaunchData]:
        """Parse SpaceX press kit format."""
        launches = []
        
        # Look for press kit sections
        sections = self._split_into_sections(text)
        
        for section in sections:
            # Look for mission information
            mission_info = self._extract_mission_info_from_section(section)
            if mission_info:
                try:
                    launch_data = self._create_launch_data_from_info(mission_info, source_identifier)
                    if launch_data:
                        launches.append(launch_data)
                except Exception as e:
                    logger.debug(f"Error creating launch data from press kit section: {e}")
                    continue
        
        return launches
    
    def _parse_mission_overview_format(self, text: str, source_identifier: str) -> List[LaunchData]:
        """Parse mission overview document format."""
        launches = []
        
        # Look for mission overview patterns
        mission_patterns = [
            r'Mission:\s*([^\n]+)',
            r'Launch:\s*([^\n]+)',
            r'Vehicle:\s*([^\n]+)',
            r'Payload:\s*([^\n]+)',
        ]
        
        mission_data = {}
        for pattern in mission_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                key = pattern.split(':')[0].lower().replace(r'\s*', '')
                mission_data[key] = matches[0].strip()
        
        if mission_data:
            try:
                launch_data = self._create_launch_data_from_dict(mission_data, source_identifier)
                if launch_data:
                    launches.append(launch_data)
            except Exception as e:
                logger.debug(f"Error creating launch data from mission overview: {e}")
        
        return launches
    
    def _parse_technical_document_format(self, text: str, source_identifier: str) -> List[LaunchData]:
        """Parse technical document format."""
        launches = []
        
        # Look for technical specifications and launch details
        # This is a simplified implementation - real technical docs would need more sophisticated parsing
        
        # Extract key-value pairs
        kv_patterns = [
            r'Launch\s+Date:\s*([^\n]+)',
            r'Mission\s+Name:\s*([^\n]+)',
            r'Vehicle:\s*([^\n]+)',
            r'Payload\s+Mass:\s*([^\n]+)',
            r'Target\s+Orbit:\s*([^\n]+)',
        ]
        
        tech_data = {}
        for pattern in kv_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                key = pattern.split(':')[0].lower().replace(r'\s+', '_').replace('\\', '')
                tech_data[key] = match.group(1).strip()
        
        if tech_data:
            try:
                launch_data = self._create_launch_data_from_dict(tech_data, source_identifier)
                if launch_data:
                    launches.append(launch_data)
            except Exception as e:
                logger.debug(f"Error creating launch data from technical document: {e}")
        
        return launches
    
    def _parse_generic_text_format(self, text: str, source_identifier: str) -> List[LaunchData]:
        """Parse generic text format as fallback."""
        launches = []
        
        # Look for any mention of SpaceX missions
        mission_patterns = [
            r'(Starlink[\s\-]*\d*[\s\-]*\w*)',
            r'(Crew[\s\-]*\d*[\s\-]*\w*)',
            r'(CRS[\s\-]*\d*)',
            r'(Dragon[\s\-]*\w*[\s\-]*Mission)',
            r'(Falcon\s+(?:9|Heavy)[\s\-]*\w*)',
        ]
        
        found_missions = set()
        for pattern in mission_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                mission_name = match.strip()
                if mission_name not in found_missions:
                    found_missions.add(mission_name)
                    
                    try:
                        # Create basic launch data
                        slug = self._create_slug(mission_name)
                        launch_data = LaunchData(
                            slug=slug,
                            mission_name=mission_name,
                            status=LaunchStatus.UPCOMING,  # Default status
                            details=f"Extracted from PDF: {source_identifier}"
                        )
                        launches.append(launch_data)
                    except Exception as e:
                        logger.debug(f"Error creating generic launch data: {e}")
                        continue
        
        return launches
    
    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into logical sections."""
        # Split by common section headers
        section_patterns = [
            r'\n\s*MISSION\s+OVERVIEW\s*\n',
            r'\n\s*LAUNCH\s+DETAILS\s*\n',
            r'\n\s*VEHICLE\s+INFORMATION\s*\n',
            r'\n\s*PAYLOAD\s+INFORMATION\s*\n',
            r'\n\s*---\s*Page\s+\d+\s*---\s*\n',
        ]
        
        sections = [text]  # Start with full text
        
        for pattern in section_patterns:
            new_sections = []
            for section in sections:
                parts = re.split(pattern, section, flags=re.IGNORECASE)
                new_sections.extend(parts)
            sections = new_sections
        
        # Filter out very short sections
        return [section.strip() for section in sections if len(section.strip()) > 100]
    
    def _extract_mission_info_from_section(self, section: str) -> Optional[Dict[str, str]]:
        """Extract mission information from a text section."""
        info = {}
        
        # Common information patterns
        patterns = {
            'mission_name': [
                r'Mission:\s*([^\n]+)',
                r'Mission\s+Name:\s*([^\n]+)',
                r'Launch:\s*([^\n]+)',
            ],
            'launch_date': [
                r'Launch\s+Date:\s*([^\n]+)',
                r'Date:\s*([^\n]+)',
                r'Scheduled:\s*([^\n]+)',
            ],
            'vehicle': [
                r'Vehicle:\s*([^\n]+)',
                r'Rocket:\s*([^\n]+)',
                r'Launch\s+Vehicle:\s*([^\n]+)',
            ],
            'payload': [
                r'Payload:\s*([^\n]+)',
                r'Cargo:\s*([^\n]+)',
                r'Mission\s+Payload:\s*([^\n]+)',
            ],
            'orbit': [
                r'Orbit:\s*([^\n]+)',
                r'Target\s+Orbit:\s*([^\n]+)',
                r'Destination:\s*([^\n]+)',
            ],
            'mass': [
                r'Mass:\s*([^\n]+)',
                r'Payload\s+Mass:\s*([^\n]+)',
                r'Weight:\s*([^\n]+)',
            ]
        }
        
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, section, re.IGNORECASE)
                if match:
                    info[key] = match.group(1).strip()
                    break  # Use first match for each key
        
        return info if info else None
    
    def _create_launch_data_from_info(self, info: Dict[str, str], source_identifier: str) -> Optional[LaunchData]:
        """Create LaunchData from extracted information dictionary."""
        try:
            mission_name = info.get('mission_name')
            if not mission_name:
                return None
            
            slug = self._create_slug(mission_name)
            
            # Parse launch date
            launch_date = None
            if 'launch_date' in info:
                launch_date = self._parse_date_string(info['launch_date'])
            
            # Extract vehicle type
            vehicle_type = info.get('vehicle')
            if vehicle_type:
                vehicle_type = self._clean_vehicle_name(vehicle_type)
            
            # Extract payload mass
            payload_mass = None
            if 'mass' in info:
                payload_mass = self._parse_mass_string(info['mass'])
            
            # Determine status
            status = LaunchStatus.UPCOMING
            if launch_date:
                now = datetime.now(timezone.utc)
                if launch_date < now:
                    status = LaunchStatus.SUCCESS  # Assume past launches were successful
            
            # Create details from available info
            details_parts = []
            for key, value in info.items():
                if key not in ['mission_name', 'launch_date', 'vehicle', 'mass'] and value:
                    details_parts.append(f"{key.replace('_', ' ').title()}: {value}")
            
            details = "; ".join(details_parts) if details_parts else f"Extracted from PDF: {source_identifier}"
            
            return LaunchData(
                slug=slug,
                mission_name=mission_name,
                launch_date=launch_date,
                vehicle_type=vehicle_type,
                payload_mass=payload_mass,
                orbit=info.get('orbit'),
                status=status,
                details=details[:500] if details else None  # Limit length
            )
            
        except Exception as e:
            logger.debug(f"Error creating LaunchData from info: {e}")
            return None
    
    def _create_launch_data_from_dict(self, data: Dict[str, str], source_identifier: str) -> Optional[LaunchData]:
        """Create LaunchData from a generic data dictionary."""
        # Map common keys to our format
        key_mapping = {
            'mission': 'mission_name',
            'launch': 'mission_name',
            'launch_date': 'launch_date',
            'date': 'launch_date',
            'vehicle': 'vehicle_type',
            'rocket': 'vehicle_type',
            'payload_mass': 'payload_mass',
            'mass': 'payload_mass',
            'target_orbit': 'orbit',
            'orbit': 'orbit',
        }
        
        mapped_data = {}
        for key, value in data.items():
            mapped_key = key_mapping.get(key, key)
            mapped_data[mapped_key] = value
        
        return self._create_launch_data_from_info(mapped_data, source_identifier)
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse a date string into datetime object."""
        # Clean up the date string
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        
        # Try various date formats
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # ISO format
            r'(\w+\s+\d{1,2},?\s+\d{4})',  # Month Day, Year
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',  # MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    date_part = match.group(1)
                    if re.match(r'\d{4}-\d{2}-\d{2}', date_part):
                        return datetime.fromisoformat(date_part).replace(tzinfo=timezone.utc)
                    # For other formats, we'd need more sophisticated parsing
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _clean_vehicle_name(self, vehicle_str: str) -> str:
        """Clean and standardize vehicle name."""
        vehicle_str = vehicle_str.strip()
        
        # Standardize common vehicle names
        if re.search(r'falcon\s*9', vehicle_str, re.IGNORECASE):
            return "Falcon 9"
        elif re.search(r'falcon\s*heavy', vehicle_str, re.IGNORECASE):
            return "Falcon Heavy"
        elif re.search(r'dragon', vehicle_str, re.IGNORECASE):
            return "Dragon"
        
        return vehicle_str
    
    def _parse_mass_string(self, mass_str: str) -> Optional[float]:
        """Parse mass string into float (kg)."""
        # Look for mass patterns
        mass_patterns = [
            r'(\d+(?:\.\d+)?)\s*kg',
            r'(\d+(?:\.\d+)?)\s*t',  # tonnes
            r'(\d+(?:,\d{3})*)\s*kg',  # with thousands separator
        ]
        
        for pattern in mass_patterns:
            match = re.search(pattern, mass_str, re.IGNORECASE)
            if match:
                try:
                    mass_value = float(match.group(1).replace(',', ''))
                    
                    # Convert tonnes to kg if needed
                    if 't' in match.group(0).lower() and 'kg' not in match.group(0).lower():
                        mass_value *= 1000
                    
                    return mass_value
                except ValueError:
                    continue
        
        return None
    
    def _create_slug(self, mission_name: str) -> str:
        """Create a URL-friendly slug from mission name."""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', mission_name.lower())
        slug = re.sub(r'[\s_-]+', '-', slug)
        slug = slug.strip('-')
        
        # Ensure it's not empty
        if not slug:
            slug = f"pdf-mission-{hash(mission_name) % 10000}"
        
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
    
    async def get_source_data(self, source_identifier: str) -> SourceData:
        """Get source data for tracking."""
        return SourceData(
            source_name="PDF Document",
            source_url=source_identifier,
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.6  # Medium quality as PDFs can be inconsistent
        )


# Example usage function
async def example_usage():
    """Example of how to use the PDFProcessor."""
    async with PDFProcessor() as processor:
        try:
            # Example with a hypothetical PDF URL
            pdf_url = "https://example.com/spacex-mission-press-kit.pdf"
            
            # In a real scenario, you would have actual PDF URLs
            print(f"Would process PDF from: {pdf_url}")
            
            # For demonstration, create a sample text
            sample_text = """
            MISSION OVERVIEW
            Mission Name: Starlink 6-1
            Launch Date: 2024-01-15
            Vehicle: Falcon 9
            Payload Mass: 15,600 kg
            Target Orbit: Low Earth Orbit
            """
            
            # Process sample text directly
            launches = await processor._parse_launches_from_text(sample_text, "sample.pdf")
            print(f"Extracted {len(launches)} launches from sample text:")
            
            for launch in launches:
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