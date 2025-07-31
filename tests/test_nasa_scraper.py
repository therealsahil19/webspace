"""
Unit tests for NASA scraper.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.scraping.nasa_scraper import NASAScraper, NASAScraperError
from src.models.schemas import LaunchData, LaunchStatus


class TestNASAScraper:
    """Test cases for NASAScraper."""
    
    @pytest.fixture
    def mock_ethical_scraper(self):
        """Mock ethical scraper."""
        mock_scraper = Mock()
        mock_scraper.prepare_request = AsyncMock(return_value={'User-Agent': 'test-agent'})
        return mock_scraper
    
    @pytest.fixture
    def nasa_scraper(self, mock_ethical_scraper):
        """Create NASAScraper instance with mocked dependencies."""
        return NASAScraper(mock_ethical_scraper)
    
    @pytest.fixture
    def sample_nasa_search_html(self):
        """Sample NASA search results HTML."""
        return """
        <html>
        <body>
            <div class="search-result">
                <h3><a href="/news/spacex-crew-8-launch">SpaceX Crew-8 Mission to International Space Station</a></h3>
                <p>NASA and SpaceX are targeting March 1, 2024, for the launch of the Crew-8 mission to the International Space Station. The mission will use a Falcon 9 rocket and Dragon spacecraft.</p>
                <time datetime="2024-03-01T10:30:00Z">March 1, 2024</time>
            </div>
            <div class="search-result">
                <h3><a href="/news/spacex-crs-30">SpaceX CRS-30 Cargo Mission</a></h3>
                <p>SpaceX's 30th Commercial Resupply Services mission will deliver scientific experiments and supplies to the space station using a Dragon cargo spacecraft.</p>
                <time datetime="2024-02-15T14:20:00Z">February 15, 2024</time>
            </div>
            <div class="search-result">
                <h3><a href="/news/mars-rover-update">Mars Rover Update</a></h3>
                <p>Latest updates from the Mars rover mission. No SpaceX content here.</p>
            </div>
        </body>
        </html>
        """
    
    @pytest.fixture
    def sample_nasa_news_html(self):
        """Sample NASA news releases HTML."""
        return """
        <html>
        <body>
            <article class="news-item">
                <h2>NASA: SpaceX Dragon Returns from Space Station</h2>
                <p>The SpaceX Dragon spacecraft successfully returned to Earth after completing its mission to the International Space Station. The Crew Dragon capsule carried four astronauts back safely.</p>
                <time datetime="2024-01-20T08:15:00Z">January 20, 2024</time>
            </article>
            <article class="news-item">
                <h2>Artemis Program Update</h2>
                <p>Updates on the Artemis lunar program. This article does not mention SpaceX.</p>
            </article>
            <article class="news-item">
                <h2>Commercial Crew Program Success</h2>
                <p>NASA's Commercial Crew Program continues to demonstrate success with SpaceX Falcon 9 launches carrying astronauts to the ISS.</p>
            </article>
        </body>
        </html>
        """
    
    @pytest.mark.asyncio
    async def test_scraper_initialization(self, mock_ethical_scraper):
        """Test scraper initialization."""
        scraper = NASAScraper(mock_ethical_scraper)
        assert scraper.ethical_scraper == mock_ethical_scraper
        assert scraper.session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, nasa_scraper):
        """Test async context manager."""
        with patch.object(nasa_scraper, 'start_session') as mock_start, \
             patch.object(nasa_scraper, 'close_session') as mock_close:
            
            async with nasa_scraper:
                mock_start.assert_called_once()
            
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_management(self, nasa_scraper):
        """Test session start and close."""
        # Test start session
        await nasa_scraper.start_session()
        assert nasa_scraper.session is not None
        
        # Test close session
        await nasa_scraper.close_session()
        # Session should be closed but we can't easily test this
    
    @pytest.mark.asyncio
    async def test_scrape_launches_without_session(self, nasa_scraper):
        """Test scraping without initialized session."""
        with pytest.raises(NASAScraperError, match="Session not initialized"):
            await nasa_scraper.scrape_launches()
    
    @pytest.mark.asyncio
    async def test_scrape_search_results(self, nasa_scraper, sample_nasa_search_html):
        """Test scraping NASA search results."""
        # Mock session and response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=sample_nasa_search_html)
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        nasa_scraper.session = mock_session
        
        # Mock the _scrape_url method to test parsing
        with patch.object(nasa_scraper, '_scrape_url') as mock_scrape_url:
            mock_scrape_url.return_value = [
                LaunchData(
                    slug="spacex-crew-8-mission",
                    mission_name="SpaceX Crew-8 Mission to International Space Station",
                    launch_date=datetime(2024, 3, 1, 10, 30, tzinfo=timezone.utc),
                    vehicle_type="Falcon 9",
                    status=LaunchStatus.UPCOMING
                ),
                LaunchData(
                    slug="spacex-crs-30-cargo-mission",
                    mission_name="SpaceX CRS-30 Cargo Mission",
                    launch_date=datetime(2024, 2, 15, 14, 20, tzinfo=timezone.utc),
                    vehicle_type="Dragon",
                    status=LaunchStatus.UPCOMING
                )
            ]
            
            launches = await nasa_scraper.scrape_launches()
            
            assert len(launches) >= 2
            assert any("Crew-8" in launch.mission_name for launch in launches)
            assert any("CRS-30" in launch.mission_name for launch in launches)
    
    @pytest.mark.asyncio
    async def test_parse_search_results(self, nasa_scraper, sample_nasa_search_html):
        """Test parsing search results HTML."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(sample_nasa_search_html, 'html.parser')
        launches = nasa_scraper._parse_search_results(soup)
        
        # Should find SpaceX-related launches only
        spacex_launches = [l for l in launches if nasa_scraper._is_spacex_related(l)]
        assert len(spacex_launches) >= 1
        
        # Check that non-SpaceX content is filtered out
        mission_names = [l.mission_name for l in launches]
        assert not any("Mars Rover" in name for name in mission_names)
    
    @pytest.mark.asyncio
    async def test_parse_news_releases(self, nasa_scraper, sample_nasa_news_html):
        """Test parsing news releases HTML."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(sample_nasa_news_html, 'html.parser')
        launches = nasa_scraper._parse_news_releases(soup)
        
        # Should find SpaceX-related articles only
        assert len(launches) >= 1
        
        # Check mission names contain SpaceX-related content
        mission_names = [l.mission_name for l in launches if l]
        spacex_related = [name for name in mission_names if any(
            keyword in name.lower() for keyword in ['spacex', 'dragon', 'falcon', 'crew']
        )]
        assert len(spacex_related) >= 1
    
    def test_mentions_spacex(self, nasa_scraper):
        """Test SpaceX mention detection."""
        from bs4 import BeautifulSoup
        
        # Test positive cases
        spacex_html = "<div>SpaceX Falcon 9 launch</div>"
        soup = BeautifulSoup(spacex_html, 'html.parser')
        assert nasa_scraper._mentions_spacex(soup.div)
        
        dragon_html = "<div>Dragon spacecraft mission</div>"
        soup = BeautifulSoup(dragon_html, 'html.parser')
        assert nasa_scraper._mentions_spacex(soup.div)
        
        # Test negative case
        other_html = "<div>Mars rover update</div>"
        soup = BeautifulSoup(other_html, 'html.parser')
        assert not nasa_scraper._mentions_spacex(soup.div)
    
    def test_is_spacex_related(self, nasa_scraper):
        """Test SpaceX relation detection for launch data."""
        # Test positive cases
        spacex_launch = LaunchData(
            slug="test-slug",
            mission_name="SpaceX Crew Mission",
            status=LaunchStatus.UPCOMING
        )
        assert nasa_scraper._is_spacex_related(spacex_launch)
        
        falcon_launch = LaunchData(
            slug="test-slug",
            mission_name="Falcon 9 Launch",
            status=LaunchStatus.UPCOMING
        )
        assert nasa_scraper._is_spacex_related(falcon_launch)
        
        # Test negative case
        other_launch = LaunchData(
            slug="test-slug",
            mission_name="Mars Rover Mission",
            status=LaunchStatus.UPCOMING
        )
        assert not nasa_scraper._is_spacex_related(other_launch)
    
    def test_extract_mission_name(self, nasa_scraper):
        """Test mission name extraction."""
        from bs4 import BeautifulSoup
        
        # Test with heading
        html_with_heading = """
        <div>
            <h2>SpaceX Crew-8 Mission Launch</h2>
            <p>Mission details here</p>
        </div>
        """
        soup = BeautifulSoup(html_with_heading, 'html.parser')
        name = nasa_scraper._extract_mission_name(soup.div, soup.div.get_text())
        assert name == "SpaceX Crew-8 Mission Launch"
        
        # Test with title link
        html_with_link = """
        <div>
            <a class="title-link" href="/mission">Dragon CRS-30 Mission</a>
            <p>Mission details here</p>
        </div>
        """
        soup = BeautifulSoup(html_with_link, 'html.parser')
        name = nasa_scraper._extract_mission_name(soup.div, soup.div.get_text())
        assert name == "Dragon CRS-30 Mission"
    
    def test_clean_nasa_title(self, nasa_scraper):
        """Test NASA title cleaning."""
        # Test removing NASA prefix
        title1 = "NASA: SpaceX Crew-8 Launch"
        cleaned1 = nasa_scraper._clean_nasa_title(title1)
        assert cleaned1 == "SpaceX Crew-8 Launch"
        
        # Test removing NASA suffix
        title2 = "SpaceX Dragon Mission - NASA"
        cleaned2 = nasa_scraper._clean_nasa_title(title2)
        assert cleaned2 == "SpaceX Dragon Mission"
        
        # Test filtering generic titles
        title3 = "NASA Press Release"
        cleaned3 = nasa_scraper._clean_nasa_title(title3)
        assert cleaned3 is None
    
    def test_extract_launch_status(self, nasa_scraper):
        """Test launch status extraction."""
        from bs4 import BeautifulSoup
        
        # Test success status
        success_html = "<div>Mission completed successfully</div>"
        soup = BeautifulSoup(success_html, 'html.parser')
        status = nasa_scraper._extract_launch_status(soup.div, soup.div.get_text(), None)
        assert status == LaunchStatus.SUCCESS
        
        # Test failure status
        failure_html = "<div>Mission failed to reach orbit</div>"
        soup = BeautifulSoup(failure_html, 'html.parser')
        status = nasa_scraper._extract_launch_status(soup.div, soup.div.get_text(), None)
        assert status == LaunchStatus.FAILURE
        
        # Test upcoming status
        upcoming_html = "<div>Mission scheduled for next month</div>"
        soup = BeautifulSoup(upcoming_html, 'html.parser')
        status = nasa_scraper._extract_launch_status(soup.div, soup.div.get_text(), None)
        assert status == LaunchStatus.UPCOMING
    
    def test_create_slug(self, nasa_scraper):
        """Test slug creation."""
        # Test normal mission name
        slug1 = nasa_scraper._create_slug("SpaceX Crew-8 Mission")
        assert slug1 == "spacex-crew-8-mission"
        
        # Test with special characters
        slug2 = nasa_scraper._create_slug("Dragon CRS-30: Cargo Mission!")
        assert slug2 == "dragon-crs-30-cargo-mission"
        
        # Test empty string
        slug3 = nasa_scraper._create_slug("")
        assert slug3.startswith("nasa-mission-")
    
    def test_deduplicate_launches(self, nasa_scraper):
        """Test launch deduplication."""
        launches = [
            LaunchData(slug="mission-1", mission_name="Mission 1", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-2", mission_name="Mission 2", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-1", mission_name="Mission 1 Duplicate", status=LaunchStatus.UPCOMING),
        ]
        
        unique_launches = nasa_scraper._deduplicate_launches(launches)
        assert len(unique_launches) == 2
        
        slugs = [launch.slug for launch in unique_launches]
        assert "mission-1" in slugs
        assert "mission-2" in slugs
    
    @pytest.mark.asyncio
    async def test_get_source_data(self, nasa_scraper):
        """Test source data generation."""
        source_data = await nasa_scraper.get_source_data()
        
        assert source_data.source_name == "NASA Official Website"
        assert source_data.source_url == nasa_scraper.NASA_SPACEX_SEARCH_URL
        assert source_data.data_quality_score == 0.8
        assert isinstance(source_data.scraped_at, datetime)
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, nasa_scraper):
        """Test HTTP error handling."""
        # Mock session with error response
        mock_response = Mock()
        mock_response.status = 404
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        nasa_scraper.session = mock_session
        
        with pytest.raises(NASAScraperError):
            await nasa_scraper.scrape_launches()
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, nasa_scraper):
        """Test network error handling."""
        import aiohttp
        
        # Mock session that raises network error
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Network error")
        )
        
        nasa_scraper.session = mock_session
        
        with pytest.raises(NASAScraperError):
            await nasa_scraper.scrape_launches()


if __name__ == "__main__":
    pytest.main([__file__])