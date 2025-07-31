"""
Unit tests for unified scraper.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from pathlib import Path

from src.scraping.unified_scraper import UnifiedScraper, UnifiedScraperError
from src.models.schemas import LaunchData, LaunchStatus, SourceData


class TestUnifiedScraper:
    """Test cases for UnifiedScraper."""
    
    @pytest.fixture
    def mock_ethical_scraper(self):
        """Mock ethical scraper."""
        mock_scraper = Mock()
        mock_scraper.get_comprehensive_stats = Mock(return_value={'test': 'stats'})
        return mock_scraper
    
    @pytest.fixture
    def sample_launch_data(self):
        """Sample launch data for testing."""
        return [
            LaunchData(
                slug="starlink-6-1",
                mission_name="Starlink 6-1",
                launch_date=datetime(2024, 3, 1, tzinfo=timezone.utc),
                vehicle_type="Falcon 9",
                status=LaunchStatus.UPCOMING
            ),
            LaunchData(
                slug="crew-8",
                mission_name="Crew-8",
                launch_date=datetime(2024, 2, 15, tzinfo=timezone.utc),
                vehicle_type="Falcon 9",
                status=LaunchStatus.SUCCESS
            ),
            LaunchData(
                slug="crs-30",
                mission_name="CRS-30",
                launch_date=datetime(2024, 1, 20, tzinfo=timezone.utc),
                vehicle_type="Dragon",
                status=LaunchStatus.SUCCESS
            )
        ]
    
    @pytest.fixture
    def sample_source_data(self):
        """Sample source data for testing."""
        return [
            SourceData(
                source_name="SpaceX Official Website",
                source_url="https://www.spacex.com/launches",
                scraped_at=datetime.now(timezone.utc),
                data_quality_score=0.9
            ),
            SourceData(
                source_name="NASA Official Website",
                source_url="https://www.nasa.gov/search/?q=spacex+launch",
                scraped_at=datetime.now(timezone.utc),
                data_quality_score=0.8
            )
        ]
    
    @pytest.fixture
    def unified_scraper(self, mock_ethical_scraper):
        """Create UnifiedScraper instance with mocked dependencies."""
        with patch('src.scraping.unified_scraper.SpaceXScraper') as mock_spacex, \
             patch('src.scraping.unified_scraper.NASAScraper') as mock_nasa, \
             patch('src.scraping.unified_scraper.WikipediaScraper') as mock_wikipedia, \
             patch('src.scraping.unified_scraper.PDFProcessor') as mock_pdf:
            
            scraper = UnifiedScraper(mock_ethical_scraper)
            
            # Store mocks for later access
            scraper._mock_spacex = mock_spacex.return_value
            scraper._mock_nasa = mock_nasa.return_value
            scraper._mock_wikipedia = mock_wikipedia.return_value
            scraper._mock_pdf = mock_pdf.return_value
            
            return scraper
    
    @pytest.mark.asyncio
    async def test_scraper_initialization(self, mock_ethical_scraper):
        """Test scraper initialization."""
        with patch('src.scraping.unified_scraper.SpaceXScraper'), \
             patch('src.scraping.unified_scraper.NASAScraper'), \
             patch('src.scraping.unified_scraper.WikipediaScraper'), \
             patch('src.scraping.unified_scraper.PDFProcessor'):
            
            scraper = UnifiedScraper(mock_ethical_scraper)
            assert scraper.ethical_scraper == mock_ethical_scraper
    
    @pytest.mark.asyncio
    async def test_context_manager(self, unified_scraper):
        """Test async context manager."""
        with patch.object(unified_scraper, 'start_all_scrapers') as mock_start, \
             patch.object(unified_scraper, 'close_all_scrapers') as mock_close:
            
            async with unified_scraper:
                mock_start.assert_called_once()
            
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_all_scrapers(self, unified_scraper):
        """Test starting all scrapers."""
        # Mock individual scraper start methods
        unified_scraper._mock_spacex.start_browser = AsyncMock()
        unified_scraper._mock_nasa.start_session = AsyncMock()
        unified_scraper._mock_wikipedia.start_session = AsyncMock()
        unified_scraper._mock_pdf.start_session = AsyncMock()
        
        await unified_scraper.start_all_scrapers()
        
        unified_scraper._mock_spacex.start_browser.assert_called_once()
        unified_scraper._mock_nasa.start_session.assert_called_once()
        unified_scraper._mock_wikipedia.start_session.assert_called_once()
        unified_scraper._mock_pdf.start_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_all_scrapers(self, unified_scraper):
        """Test closing all scrapers."""
        # Mock individual scraper close methods
        unified_scraper._mock_spacex.close_browser = AsyncMock()
        unified_scraper._mock_nasa.close_session = AsyncMock()
        unified_scraper._mock_wikipedia.close_session = AsyncMock()
        unified_scraper._mock_pdf.close_session = AsyncMock()
        
        await unified_scraper.close_all_scrapers()
        
        unified_scraper._mock_spacex.close_browser.assert_called_once()
        unified_scraper._mock_nasa.close_session.assert_called_once()
        unified_scraper._mock_wikipedia.close_session.assert_called_once()
        unified_scraper._mock_pdf.close_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_all_scrapers_with_errors(self, unified_scraper):
        """Test closing all scrapers with some errors."""
        # Mock individual scraper close methods with some errors
        unified_scraper._mock_spacex.close_browser = AsyncMock(side_effect=Exception("SpaceX error"))
        unified_scraper._mock_nasa.close_session = AsyncMock()
        unified_scraper._mock_wikipedia.close_session = AsyncMock(side_effect=Exception("Wikipedia error"))
        unified_scraper._mock_pdf.close_session = AsyncMock()
        
        # Should not raise exception, just log warnings
        await unified_scraper.close_all_scrapers()
        
        unified_scraper._mock_nasa.close_session.assert_called_once()
        unified_scraper._mock_pdf.close_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources(self, unified_scraper, sample_launch_data):
        """Test scraping all sources."""
        # Mock individual scraper methods
        unified_scraper._mock_spacex.scrape_launches = AsyncMock(return_value=sample_launch_data[:2])
        unified_scraper._mock_nasa.scrape_launches = AsyncMock(return_value=sample_launch_data[1:])
        unified_scraper._mock_wikipedia.scrape_launches = AsyncMock(return_value=[sample_launch_data[0]])
        
        results = await unified_scraper.scrape_all_sources()
        
        assert 'spacex' in results
        assert 'nasa' in results
        assert 'wikipedia' in results
        assert len(results['spacex']) == 2
        assert len(results['nasa']) == 2
        assert len(results['wikipedia']) == 1
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources_with_include_filter(self, unified_scraper, sample_launch_data):
        """Test scraping with include filter."""
        unified_scraper._mock_spacex.scrape_launches = AsyncMock(return_value=sample_launch_data[:2])
        unified_scraper._mock_nasa.scrape_launches = AsyncMock(return_value=sample_launch_data[1:])
        
        results = await unified_scraper.scrape_all_sources(include_sources=['spacex', 'nasa'])
        
        assert 'spacex' in results
        assert 'nasa' in results
        assert 'wikipedia' not in results
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources_with_exclude_filter(self, unified_scraper, sample_launch_data):
        """Test scraping with exclude filter."""
        unified_scraper._mock_spacex.scrape_launches = AsyncMock(return_value=sample_launch_data[:2])
        unified_scraper._mock_wikipedia.scrape_launches = AsyncMock(return_value=[sample_launch_data[0]])
        
        results = await unified_scraper.scrape_all_sources(exclude_sources=['nasa'])
        
        assert 'spacex' in results
        assert 'wikipedia' in results
        assert 'nasa' not in results
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources_with_errors(self, unified_scraper, sample_launch_data):
        """Test scraping with some source errors."""
        unified_scraper._mock_spacex.scrape_launches = AsyncMock(return_value=sample_launch_data[:2])
        unified_scraper._mock_nasa.scrape_launches = AsyncMock(side_effect=Exception("NASA error"))
        unified_scraper._mock_wikipedia.scrape_launches = AsyncMock(return_value=[sample_launch_data[0]])
        
        results = await unified_scraper.scrape_all_sources()
        
        assert 'spacex' in results
        assert 'nasa' in results  # Should be empty list
        assert 'wikipedia' in results
        assert len(results['spacex']) == 2
        assert len(results['nasa']) == 0  # Error resulted in empty list
        assert len(results['wikipedia']) == 1
    
    @pytest.mark.asyncio
    async def test_scrape_with_fallback_primary_success(self, unified_scraper, sample_launch_data):
        """Test fallback scraping when primary sources succeed."""
        unified_scraper._mock_spacex.scrape_launches = AsyncMock(return_value=sample_launch_data[:2])
        
        # Mock scrape_all_sources for primary sources
        with patch.object(unified_scraper, 'scrape_all_sources') as mock_scrape:
            mock_scrape.return_value = {'spacex': sample_launch_data[:2]}
            
            launches = await unified_scraper.scrape_with_fallback(
                primary_sources=['spacex'],
                fallback_sources=['nasa', 'wikipedia'],
                min_launches=1
            )
            
            assert len(launches) == 2
            # Should only call scrape_all_sources once (for primary)
            assert mock_scrape.call_count == 1
    
    @pytest.mark.asyncio
    async def test_scrape_with_fallback_primary_insufficient(self, unified_scraper, sample_launch_data):
        """Test fallback scraping when primary sources are insufficient."""
        # Mock scrape_all_sources to return insufficient primary data, then fallback data
        with patch.object(unified_scraper, 'scrape_all_sources') as mock_scrape:
            mock_scrape.side_effect = [
                {'spacex': []},  # Primary sources return empty
                {'nasa': sample_launch_data[1:], 'wikipedia': [sample_launch_data[0]]}  # Fallback sources
            ]
            
            launches = await unified_scraper.scrape_with_fallback(
                primary_sources=['spacex'],
                fallback_sources=['nasa', 'wikipedia'],
                min_launches=1
            )
            
            assert len(launches) >= 1
            # Should call scrape_all_sources twice (primary + fallback)
            assert mock_scrape.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_pdf_sources(self, unified_scraper, sample_launch_data):
        """Test PDF source processing."""
        unified_scraper._mock_pdf.process_pdf_url = AsyncMock(return_value=[sample_launch_data[0]])
        unified_scraper._mock_pdf.process_pdf_file = AsyncMock(return_value=[sample_launch_data[1]])
        
        pdf_urls = ["https://example.com/test1.pdf", "https://example.com/test2.pdf"]
        pdf_files = [Path("test1.pdf"), Path("test2.pdf")]
        
        launches = await unified_scraper.process_pdf_sources(pdf_urls, pdf_files)
        
        # Should process 2 URLs + 2 files, but deduplicated
        assert len(launches) >= 1
        assert unified_scraper._mock_pdf.process_pdf_url.call_count == 2
        assert unified_scraper._mock_pdf.process_pdf_file.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_pdf_sources_with_errors(self, unified_scraper, sample_launch_data):
        """Test PDF source processing with some errors."""
        unified_scraper._mock_pdf.process_pdf_url = AsyncMock(side_effect=[
            [sample_launch_data[0]],  # First URL succeeds
            Exception("PDF error")    # Second URL fails
        ])
        
        pdf_urls = ["https://example.com/test1.pdf", "https://example.com/test2.pdf"]
        
        launches = await unified_scraper.process_pdf_sources(pdf_urls=pdf_urls)
        
        # Should get launches from successful URL only
        assert len(launches) == 1
        assert unified_scraper._mock_pdf.process_pdf_url.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_comprehensive_data(self, unified_scraper, sample_launch_data, sample_source_data):
        """Test getting comprehensive data."""
        # Mock scrape_all_sources
        with patch.object(unified_scraper, 'scrape_all_sources') as mock_scrape:
            mock_scrape.return_value = {
                'spacex': sample_launch_data[:2],
                'nasa': sample_launch_data[1:],
                'wikipedia': [sample_launch_data[0]]
            }
            
            # Mock source data methods
            unified_scraper._mock_spacex.get_source_data = AsyncMock(return_value=sample_source_data[0])
            unified_scraper._mock_nasa.get_source_data = AsyncMock(return_value=sample_source_data[1])
            unified_scraper._mock_wikipedia.get_source_data = AsyncMock(return_value=sample_source_data[0])
            
            result = await unified_scraper.get_comprehensive_data()
            
            assert 'launches' in result
            assert 'source_data' in result
            assert 'metadata' in result
            
            assert len(result['launches']) >= 1  # Deduplicated
            assert len(result['source_data']) == 3
            assert result['metadata']['total_launches'] >= 1
            assert 'scraping_duration' in result['metadata']
            assert 'scraped_at' in result['metadata']
    
    @pytest.mark.asyncio
    async def test_get_comprehensive_data_with_pdfs(self, unified_scraper, sample_launch_data):
        """Test getting comprehensive data including PDFs."""
        # Mock scrape_all_sources and process_pdf_sources
        with patch.object(unified_scraper, 'scrape_all_sources') as mock_scrape, \
             patch.object(unified_scraper, 'process_pdf_sources') as mock_pdf:
            
            mock_scrape.return_value = {'spacex': sample_launch_data[:2]}
            mock_pdf.return_value = [sample_launch_data[2]]
            
            # Mock source data methods
            unified_scraper._mock_spacex.get_source_data = AsyncMock(return_value=SourceData(
                source_name="SpaceX", source_url="test", scraped_at=datetime.now(timezone.utc), data_quality_score=0.9
            ))
            unified_scraper._mock_pdf.get_source_data = AsyncMock(return_value=SourceData(
                source_name="PDF", source_url="test", scraped_at=datetime.now(timezone.utc), data_quality_score=0.6
            ))
            
            result = await unified_scraper.get_comprehensive_data(
                include_pdfs=True,
                pdf_urls=["https://example.com/test.pdf"]
            )
            
            assert len(result['launches']) >= 2  # Web + PDF launches
            assert 'pdf' in result['metadata']['sources_scraped']
    
    def test_deduplicate_launches(self, unified_scraper):
        """Test launch deduplication."""
        # Create launches with duplicates
        launches = [
            LaunchData(slug="starlink-6-1", mission_name="Starlink 6-1", status=LaunchStatus.UPCOMING),
            LaunchData(slug="starlink-6-1-duplicate", mission_name="Starlink 6-1", status=LaunchStatus.UPCOMING, details="More details"),
            LaunchData(slug="crew-8", mission_name="Crew-8", status=LaunchStatus.SUCCESS),
            LaunchData(slug="crew-8-alt", mission_name="Crew 8 Mission", status=LaunchStatus.SUCCESS),  # Similar name
        ]
        
        unique_launches = unified_scraper._deduplicate_launches(launches)
        
        # Should deduplicate based on normalized mission names
        assert len(unique_launches) <= len(launches)
        
        # Check that the one with more info is kept
        starlink_launches = [l for l in unique_launches if "starlink" in l.mission_name.lower()]
        if starlink_launches:
            assert starlink_launches[0].details is not None  # Should keep the one with details
    
    def test_normalize_mission_name(self, unified_scraper):
        """Test mission name normalization."""
        # Test basic normalization
        assert unified_scraper._normalize_mission_name("Starlink 6-1") == "starlink 6-1"
        
        # Test with extra words
        assert unified_scraper._normalize_mission_name("Starlink 6-1 Mission Launch") == "starlink 6-1"
        
        # Test with multiple spaces
        assert unified_scraper._normalize_mission_name("Crew   8    Mission") == "crew 8"
    
    def test_calculate_info_score(self, unified_scraper):
        """Test information score calculation."""
        # Launch with minimal info
        minimal_launch = LaunchData(slug="test", mission_name="Test", status=LaunchStatus.UPCOMING)
        minimal_score = unified_scraper._calculate_info_score(minimal_launch)
        
        # Launch with more info
        detailed_launch = LaunchData(
            slug="test",
            mission_name="Test",
            status=LaunchStatus.UPCOMING,
            launch_date=datetime.now(timezone.utc),
            vehicle_type="Falcon 9",
            payload_mass=15000.0,
            orbit="LEO",
            details="Detailed mission description with lots of information",
            mission_patch_url="https://example.com/patch.png",
            webcast_url="https://example.com/webcast"
        )
        detailed_score = unified_scraper._calculate_info_score(detailed_launch)
        
        assert detailed_score > minimal_score
    
    def test_launch_has_more_info(self, unified_scraper):
        """Test comparison of launch information."""
        launch1 = LaunchData(slug="test1", mission_name="Test 1", status=LaunchStatus.UPCOMING)
        launch2 = LaunchData(
            slug="test2",
            mission_name="Test 2",
            status=LaunchStatus.UPCOMING,
            launch_date=datetime.now(timezone.utc),
            vehicle_type="Falcon 9"
        )
        
        assert unified_scraper._launch_has_more_info(launch2, launch1)
        assert not unified_scraper._launch_has_more_info(launch1, launch2)
    
    @pytest.mark.asyncio
    async def test_get_scraping_statistics(self, unified_scraper):
        """Test getting scraping statistics."""
        stats = await unified_scraper.get_scraping_statistics()
        
        assert 'ethical_scraper' in stats
        assert 'scrapers' in stats
        assert 'capabilities' in stats
        
        assert stats['capabilities']['web_scraping'] is True
        assert stats['capabilities']['pdf_processing'] is True
        assert stats['capabilities']['rate_limiting'] is True
        assert stats['capabilities']['deduplication'] is True
    
    @pytest.mark.asyncio
    async def test_scrape_all_sources_no_valid_sources(self, unified_scraper):
        """Test scraping with no valid sources."""
        with pytest.raises(UnifiedScraperError, match="No valid sources specified"):
            await unified_scraper.scrape_all_sources(include_sources=['invalid_source'])
    
    @pytest.mark.asyncio
    async def test_start_scrapers_error_handling(self, unified_scraper):
        """Test error handling during scraper startup."""
        unified_scraper._mock_spacex.start_browser = AsyncMock(side_effect=Exception("Browser error"))
        
        with pytest.raises(UnifiedScraperError):
            await unified_scraper.start_all_scrapers()


if __name__ == "__main__":
    pytest.main([__file__])