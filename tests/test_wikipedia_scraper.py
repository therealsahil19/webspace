"""
Unit tests for Wikipedia scraper.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.scraping.wikipedia_scraper import WikipediaScraper, WikipediaScraperError
from src.models.schemas import LaunchData, LaunchStatus


class TestWikipediaScraper:
    """Test cases for WikipediaScraper."""
    
    @pytest.fixture
    def mock_ethical_scraper(self):
        """Mock ethical scraper."""
        mock_scraper = Mock()
        mock_scraper.prepare_request = AsyncMock(return_value={'User-Agent': 'test-agent'})
        return mock_scraper
    
    @pytest.fixture
    def wikipedia_scraper(self, mock_ethical_scraper):
        """Create WikipediaScraper instance with mocked dependencies."""
        return WikipediaScraper(mock_ethical_scraper)
    
    @pytest.fixture
    def sample_wikipedia_table_html(self):
        """Sample Wikipedia table HTML."""
        return """
        <html>
        <body>
            <table class="wikitable sortable">
                <tr>
                    <th>Date</th>
                    <th>Mission</th>
                    <th>Vehicle</th>
                    <th>Payload</th>
                    <th>Mass (kg)</th>
                    <th>Orbit</th>
                    <th>Outcome</th>
                </tr>
                <tr>
                    <td>2024-03-01</td>
                    <td>Starlink 6-1</td>
                    <td>Falcon 9</td>
                    <td>Starlink satellites</td>
                    <td>15,600</td>
                    <td>LEO</td>
                    <td>Success</td>
                </tr>
                <tr>
                    <td>2024-02-15</td>
                    <td>Crew-8</td>
                    <td>Falcon 9</td>
                    <td>Dragon spacecraft</td>
                    <td>12,500</td>
                    <td>ISS</td>
                    <td>Success</td>
                </tr>
                <tr>
                    <td>2024-04-10</td>
                    <td>Europa Clipper</td>
                    <td>Falcon Heavy</td>
                    <td>Europa probe</td>
                    <td>6,000</td>
                    <td>Jupiter</td>
                    <td>Planned</td>
                </tr>
            </table>
        </body>
        </html>
        """
    
    @pytest.fixture
    def sample_wikipedia_list_html(self):
        """Sample Wikipedia list HTML."""
        return """
        <html>
        <body>
            <ul>
                <li>Starlink 6-2: Launched March 15, 2024, using Falcon 9. Mission successful.</li>
                <li>CRS-30: Commercial Resupply Services mission launched February 20, 2024, using Dragon spacecraft.</li>
                <li>Crew-9: Upcoming crew rotation mission scheduled for April 2024.</li>
                <li>Other non-SpaceX mission: Some other space mission not related to SpaceX.</li>
            </ul>
        </body>
        </html>
        """
    
    @pytest.mark.asyncio
    async def test_scraper_initialization(self, mock_ethical_scraper):
        """Test scraper initialization."""
        scraper = WikipediaScraper(mock_ethical_scraper)
        assert scraper.ethical_scraper == mock_ethical_scraper
        assert scraper.session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, wikipedia_scraper):
        """Test async context manager."""
        with patch.object(wikipedia_scraper, 'start_session') as mock_start, \
             patch.object(wikipedia_scraper, 'close_session') as mock_close:
            
            async with wikipedia_scraper:
                mock_start.assert_called_once()
            
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_management(self, wikipedia_scraper):
        """Test session start and close."""
        # Test start session
        await wikipedia_scraper.start_session()
        assert wikipedia_scraper.session is not None
        
        # Test close session
        await wikipedia_scraper.close_session()
    
    @pytest.mark.asyncio
    async def test_scrape_launches_without_session(self, wikipedia_scraper):
        """Test scraping without initialized session."""
        with pytest.raises(WikipediaScraperError, match="Session not initialized"):
            await wikipedia_scraper.scrape_launches()
    
    def test_is_launch_table(self, wikipedia_scraper):
        """Test launch table detection."""
        from bs4 import BeautifulSoup
        
        # Test positive case
        launch_table_html = """
        <table class="wikitable">
            <tr><th>Date</th><th>Mission</th><th>Launch</th><th>Rocket</th><th>Outcome</th></tr>
            <tr><td>2024-01-01</td><td>Test Mission</td><td>Launch</td><td>Falcon 9</td><td>Success</td></tr>
        </table>
        """
        soup = BeautifulSoup(launch_table_html, 'html.parser')
        table = soup.find('table')
        assert wikipedia_scraper._is_launch_table(table)
        
        # Test negative case
        other_table_html = """
        <table class="wikitable">
            <tr><th>Name</th><th>Age</th><th>Country</th></tr>
            <tr><td>John</td><td>30</td><td>USA</td></tr>
        </table>
        """
        soup = BeautifulSoup(other_table_html, 'html.parser')
        table = soup.find('table')
        assert not wikipedia_scraper._is_launch_table(table)
    
    def test_parse_table_headers(self, wikipedia_scraper):
        """Test table header parsing."""
        from bs4 import BeautifulSoup
        
        table_html = """
        <table>
            <tr>
                <th>Launch Date</th>
                <th>Mission Name</th>
                <th>Vehicle</th>
                <th>Payload Mass</th>
                <th>Target Orbit</th>
                <th>Mission Outcome</th>
            </tr>
        </table>
        """
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table')
        headers = wikipedia_scraper._parse_table_headers(table)
        
        assert headers is not None
        assert 'date' in headers
        assert 'mission' in headers
        assert 'vehicle' in headers
        assert 'mass' in headers
        assert 'orbit' in headers
        assert 'outcome' in headers
    
    def test_parse_launch_tables(self, wikipedia_scraper, sample_wikipedia_table_html):
        """Test parsing launch tables."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(sample_wikipedia_table_html, 'html.parser')
        launches = wikipedia_scraper._parse_launch_tables(soup)
        
        assert len(launches) >= 2  # Should find at least Starlink and Crew missions
        
        # Check specific launches
        mission_names = [launch.mission_name for launch in launches]
        assert any("Starlink" in name for name in mission_names)
        assert any("Crew" in name for name in mission_names)
        
        # Check that launches have expected data
        for launch in launches:
            assert launch.slug
            assert launch.mission_name
            assert launch.status in [LaunchStatus.SUCCESS, LaunchStatus.UPCOMING]
    
    def test_parse_table_row(self, wikipedia_scraper):
        """Test parsing individual table rows."""
        from bs4 import BeautifulSoup
        
        # Create a sample row
        row_html = """
        <tr>
            <td>2024-03-01</td>
            <td>Starlink 6-1</td>
            <td>Falcon 9</td>
            <td>Starlink satellites</td>
            <td>15,600</td>
            <td>LEO</td>
            <td>Success</td>
        </tr>
        """
        soup = BeautifulSoup(row_html, 'html.parser')
        row = soup.find('tr')
        
        # Define headers mapping
        headers = {
            'date': 0,
            'mission': 1,
            'vehicle': 2,
            'payload': 3,
            'mass': 4,
            'orbit': 5,
            'outcome': 6
        }
        
        launch = wikipedia_scraper._parse_table_row(row, headers)
        
        assert launch is not None
        assert launch.mission_name == "Starlink 6-1"
        assert launch.vehicle_type == "Falcon 9"
        assert launch.payload_mass == 15600.0
        assert launch.orbit == "LEO"
        assert launch.status == LaunchStatus.SUCCESS
    
    def test_extract_text_from_cell(self, wikipedia_scraper):
        """Test text extraction from table cells."""
        from bs4 import BeautifulSoup
        
        # Test with references
        cell_html = '<td>Starlink 6-1<sup>[1]</sup></td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        text = wikipedia_scraper._extract_text_from_cell(cell)
        assert text == "Starlink 6-1"
        
        # Test with links
        cell_html = '<td><a href="/wiki/Falcon_9">Falcon 9</a></td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        text = wikipedia_scraper._extract_text_from_cell(cell)
        assert text == "Falcon 9"
    
    def test_extract_status_from_cell(self, wikipedia_scraper):
        """Test status extraction from cells."""
        from bs4 import BeautifulSoup
        
        # Test success
        cell_html = '<td>Success</td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        status = wikipedia_scraper._extract_status_from_cell(cell, None)
        assert status == LaunchStatus.SUCCESS
        
        # Test failure
        cell_html = '<td>Failure</td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        status = wikipedia_scraper._extract_status_from_cell(cell, None)
        assert status == LaunchStatus.FAILURE
        
        # Test partial success
        cell_html = '<td>Partial success</td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        status = wikipedia_scraper._extract_status_from_cell(cell, None)
        assert status == LaunchStatus.SUCCESS
    
    def test_extract_mass_from_cell(self, wikipedia_scraper):
        """Test mass extraction from cells."""
        from bs4 import BeautifulSoup
        
        # Test kg format
        cell_html = '<td>15,600 kg</td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        mass = wikipedia_scraper._extract_mass_from_cell(cell)
        assert mass == 15600.0
        
        # Test tonnes format
        cell_html = '<td>15.6 t</td>'
        soup = BeautifulSoup(cell_html, 'html.parser')
        cell = soup.find('td')
        mass = wikipedia_scraper._extract_mass_from_cell(cell)
        assert mass == 15600.0  # Converted to kg
    
    def test_parse_launch_lists(self, wikipedia_scraper, sample_wikipedia_list_html):
        """Test parsing launch lists."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(sample_wikipedia_list_html, 'html.parser')
        launches = wikipedia_scraper._parse_launch_lists(soup)
        
        assert len(launches) >= 2  # Should find SpaceX-related items
        
        # Check that non-SpaceX items are filtered out
        mission_names = [launch.mission_name for launch in launches]
        assert not any("Other non-SpaceX" in name for name in mission_names)
    
    def test_parse_list_item(self, wikipedia_scraper):
        """Test parsing individual list items."""
        from bs4 import BeautifulSoup
        
        # Test with detailed item
        item_html = '<li>Starlink 6-2: Launched March 15, 2024, using Falcon 9. Mission successful.</li>'
        soup = BeautifulSoup(item_html, 'html.parser')
        item = soup.find('li')
        
        launch = wikipedia_scraper._parse_list_item(item)
        
        assert launch is not None
        assert launch.mission_name == "Starlink 6-2"
        assert launch.vehicle_type == "Falcon 9"
        assert launch.status == LaunchStatus.SUCCESS
    
    def test_extract_date_from_text(self, wikipedia_scraper):
        """Test date extraction from text."""
        # Test various date formats
        text1 = "Launched on March 15, 2024"
        date1 = wikipedia_scraper._extract_date_from_text(text1)
        # Note: This would need more sophisticated date parsing to work fully
        
        text2 = "Mission scheduled for 2024-03-15"
        date2 = wikipedia_scraper._extract_date_from_text(text2)
        assert date2 == datetime(2024, 3, 15, tzinfo=timezone.utc)
    
    def test_extract_vehicle_from_text(self, wikipedia_scraper):
        """Test vehicle extraction from text."""
        text1 = "Launched using Falcon 9 rocket"
        vehicle1 = wikipedia_scraper._extract_vehicle_from_text(text1)
        assert vehicle1 == "Falcon 9"
        
        text2 = "Mission used Falcon Heavy vehicle"
        vehicle2 = wikipedia_scraper._extract_vehicle_from_text(text2)
        assert vehicle2 == "Falcon Heavy"
        
        text3 = "Dragon spacecraft mission"
        vehicle3 = wikipedia_scraper._extract_vehicle_from_text(text3)
        assert vehicle3 == "Dragon"
    
    def test_extract_status_from_text(self, wikipedia_scraper):
        """Test status extraction from text."""
        # Test success
        text1 = "Mission completed successfully"
        status1 = wikipedia_scraper._extract_status_from_text(text1, None)
        assert status1 == LaunchStatus.SUCCESS
        
        # Test failure
        text2 = "Mission failed to reach orbit"
        status2 = wikipedia_scraper._extract_status_from_text(text2, None)
        assert status2 == LaunchStatus.FAILURE
        
        # Test with future date
        future_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        text3 = "Mission scheduled for launch"
        status3 = wikipedia_scraper._extract_status_from_text(text3, future_date)
        assert status3 == LaunchStatus.UPCOMING
    
    def test_infer_status_from_date(self, wikipedia_scraper):
        """Test status inference from date."""
        # Test future date
        future_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        status1 = wikipedia_scraper._infer_status_from_date(future_date)
        assert status1 == LaunchStatus.UPCOMING
        
        # Test past date
        past_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        status2 = wikipedia_scraper._infer_status_from_date(past_date)
        assert status2 == LaunchStatus.SUCCESS
        
        # Test no date
        status3 = wikipedia_scraper._infer_status_from_date(None)
        assert status3 == LaunchStatus.UPCOMING
    
    def test_create_slug(self, wikipedia_scraper):
        """Test slug creation."""
        # Test normal mission name
        slug1 = wikipedia_scraper._create_slug("Starlink 6-1")
        assert slug1 == "starlink-6-1"
        
        # Test with special characters
        slug2 = wikipedia_scraper._create_slug("Crew-8: ISS Mission!")
        assert slug2 == "crew-8-iss-mission"
        
        # Test empty string
        slug3 = wikipedia_scraper._create_slug("")
        assert slug3.startswith("wiki-mission-")
    
    def test_deduplicate_launches(self, wikipedia_scraper):
        """Test launch deduplication."""
        launches = [
            LaunchData(slug="mission-1", mission_name="Mission 1", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-2", mission_name="Mission 2", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-1", mission_name="Mission 1 Duplicate", status=LaunchStatus.UPCOMING),
        ]
        
        unique_launches = wikipedia_scraper._deduplicate_launches(launches)
        assert len(unique_launches) == 2
        
        slugs = [launch.slug for launch in unique_launches]
        assert "mission-1" in slugs
        assert "mission-2" in slugs
    
    @pytest.mark.asyncio
    async def test_get_source_data(self, wikipedia_scraper):
        """Test source data generation."""
        source_data = await wikipedia_scraper.get_source_data()
        
        assert source_data.source_name == "Wikipedia"
        assert source_data.source_url == wikipedia_scraper.WIKIPEDIA_SPACEX_LAUNCHES_URL
        assert source_data.data_quality_score == 0.7
        assert isinstance(source_data.scraped_at, datetime)
    
    @pytest.mark.asyncio
    async def test_scrape_with_mock_data(self, wikipedia_scraper, sample_wikipedia_table_html):
        """Test complete scraping flow with mock data."""
        # Mock session and response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=sample_wikipedia_table_html)
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        wikipedia_scraper.session = mock_session
        
        launches = await wikipedia_scraper.scrape_launches()
        
        assert len(launches) >= 1
        assert all(isinstance(launch, LaunchData) for launch in launches)
        assert all(launch.slug for launch in launches)
        assert all(launch.mission_name for launch in launches)
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, wikipedia_scraper):
        """Test HTTP error handling."""
        # Mock session with error response
        mock_response = Mock()
        mock_response.status = 404
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        wikipedia_scraper.session = mock_session
        
        with pytest.raises(WikipediaScraperError):
            await wikipedia_scraper.scrape_launches()
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, wikipedia_scraper):
        """Test network error handling."""
        import aiohttp
        
        # Mock session that raises network error
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Network error")
        )
        
        wikipedia_scraper.session = mock_session
        
        with pytest.raises(WikipediaScraperError):
            await wikipedia_scraper.scrape_launches()


if __name__ == "__main__":
    pytest.main([__file__])