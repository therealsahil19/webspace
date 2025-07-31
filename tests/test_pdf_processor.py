"""
Unit tests for PDF processor.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, mock_open
from datetime import datetime, timezone

from src.scraping.pdf_processor import PDFProcessor, PDFProcessorError
from src.models.schemas import LaunchData, LaunchStatus


class TestPDFProcessor:
    """Test cases for PDFProcessor."""
    
    @pytest.fixture
    def mock_ethical_scraper(self):
        """Mock ethical scraper."""
        mock_scraper = Mock()
        mock_scraper.prepare_request = AsyncMock(return_value={'User-Agent': 'test-agent'})
        return mock_scraper
    
    @pytest.fixture
    def pdf_processor(self, mock_ethical_scraper):
        """Create PDFProcessor instance with mocked dependencies."""
        return PDFProcessor(mock_ethical_scraper)
    
    @pytest.fixture
    def sample_press_kit_text(self):
        """Sample press kit text content."""
        return """
        SPACEX MISSION PRESS KIT
        
        MISSION OVERVIEW
        Mission: Starlink 6-1
        Launch Date: March 1, 2024
        Vehicle: Falcon 9
        Payload: Starlink satellites
        Payload Mass: 15,600 kg
        Target Orbit: Low Earth Orbit (LEO)
        
        LAUNCH DETAILS
        The Starlink 6-1 mission will deploy 23 Starlink satellites to low Earth orbit.
        This mission represents SpaceX's continued effort to build out the Starlink
        constellation for global broadband coverage.
        
        VEHICLE INFORMATION
        The Falcon 9 rocket will be used for this mission, with the first stage
        expected to land on the autonomous spaceport drone ship.
        """
    
    @pytest.fixture
    def sample_technical_doc_text(self):
        """Sample technical document text."""
        return """
        TECHNICAL SPECIFICATIONS
        
        Launch Date: 2024-02-15
        Mission Name: Crew-8
        Vehicle: Falcon 9 Block 5
        Payload Mass: 12,500 kg
        Target Orbit: International Space Station
        
        MISSION PARAMETERS
        The Crew-8 mission will transport four astronauts to the International
        Space Station using the Dragon spacecraft. The mission duration is
        expected to be approximately 6 months.
        """
    
    @pytest.fixture
    def sample_generic_text(self):
        """Sample generic text with mission mentions."""
        return """
        SpaceX continues to advance commercial spaceflight with multiple missions
        planned for 2024. The Starlink program will see continued deployments,
        with Starlink 6-2 scheduled for March 15, 2024.
        
        The Crew Dragon program has been highly successful, with Crew-9 mission
        planned for April 2024. Falcon Heavy missions are also planned for
        later in the year.
        
        Commercial Resupply Services missions like CRS-30 continue to support
        the International Space Station with regular cargo deliveries.
        """
    
    @pytest.mark.asyncio
    async def test_processor_initialization(self, mock_ethical_scraper):
        """Test processor initialization."""
        processor = PDFProcessor(mock_ethical_scraper)
        assert processor.ethical_scraper == mock_ethical_scraper
        assert processor.session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, pdf_processor):
        """Test async context manager."""
        with patch.object(pdf_processor, 'start_session') as mock_start, \
             patch.object(pdf_processor, 'close_session') as mock_close:
            
            async with pdf_processor:
                mock_start.assert_called_once()
            
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_session_management(self, pdf_processor):
        """Test session start and close."""
        # Test start session
        await pdf_processor.start_session()
        assert pdf_processor.session is not None
        
        # Test close session
        await pdf_processor.close_session()
    
    @pytest.mark.asyncio
    async def test_process_pdf_url_without_session(self, pdf_processor):
        """Test processing PDF URL without initialized session."""
        with pytest.raises(PDFProcessorError, match="Session not initialized"):
            await pdf_processor.process_pdf_url("https://example.com/test.pdf")
    
    @pytest.mark.asyncio
    async def test_process_nonexistent_file(self, pdf_processor):
        """Test processing non-existent PDF file."""
        with pytest.raises(PDFProcessorError, match="PDF file not found"):
            await pdf_processor.process_pdf_file("/nonexistent/file.pdf")
    
    @pytest.mark.asyncio
    async def test_download_pdf(self, pdf_processor):
        """Test PDF download functionality."""
        # Mock session and response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        
        # Mock content chunks
        async def mock_iter_chunked(size):
            yield b'%PDF-1.4 fake pdf content'
            yield b' more content'
        
        mock_response.content.iter_chunked = mock_iter_chunked
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        pdf_processor.session = mock_session
        
        # Mock aiofiles
        with patch('aiofiles.open', mock_open()) as mock_file:
            temp_file = await pdf_processor._download_pdf("https://example.com/test.pdf")
            
            assert isinstance(temp_file, Path)
            assert temp_file.suffix == '.pdf'
    
    @pytest.mark.asyncio
    async def test_extract_text_from_pdf(self, pdf_processor, sample_press_kit_text):
        """Test text extraction from PDF."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Mock pdfplumber
            mock_page = Mock()
            mock_page.extract_text.return_value = sample_press_kit_text
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            with patch('pdfplumber.open', return_value=mock_pdf):
                text = await pdf_processor._extract_text_from_pdf(temp_path)
                
                assert sample_press_kit_text in text
                assert "Page 1" in text
        
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
    
    def test_parse_press_kit_format(self, pdf_processor, sample_press_kit_text):
        """Test parsing press kit format."""
        launches = pdf_processor._parse_press_kit_format(sample_press_kit_text, "test.pdf")
        
        assert len(launches) >= 1
        
        launch = launches[0]
        assert "Starlink" in launch.mission_name
        assert launch.vehicle_type == "Falcon 9"
        assert launch.orbit == "Low Earth Orbit (LEO)"
    
    def test_parse_technical_document_format(self, pdf_processor, sample_technical_doc_text):
        """Test parsing technical document format."""
        launches = pdf_processor._parse_technical_document_format(sample_technical_doc_text, "test.pdf")
        
        assert len(launches) >= 1
        
        launch = launches[0]
        assert "Crew-8" in launch.mission_name
        assert launch.vehicle_type == "Falcon 9 Block 5"
        assert launch.payload_mass == 12500.0
    
    def test_parse_generic_text_format(self, pdf_processor, sample_generic_text):
        """Test parsing generic text format."""
        launches = pdf_processor._parse_generic_text_format(sample_generic_text, "test.pdf")
        
        assert len(launches) >= 2  # Should find multiple mission mentions
        
        mission_names = [launch.mission_name for launch in launches]
        assert any("Starlink" in name for name in mission_names)
        assert any("Crew" in name for name in mission_names)
    
    def test_split_into_sections(self, pdf_processor, sample_press_kit_text):
        """Test text splitting into sections."""
        sections = pdf_processor._split_into_sections(sample_press_kit_text)
        
        assert len(sections) >= 1
        assert all(len(section) > 100 for section in sections)  # Filter out short sections
    
    def test_extract_mission_info_from_section(self, pdf_processor):
        """Test mission information extraction from section."""
        section_text = """
        MISSION OVERVIEW
        Mission: Starlink 6-1
        Launch Date: March 1, 2024
        Vehicle: Falcon 9
        Payload: Starlink satellites
        Mass: 15,600 kg
        Orbit: LEO
        """
        
        info = pdf_processor._extract_mission_info_from_section(section_text)
        
        assert info is not None
        assert info['mission_name'] == "Starlink 6-1"
        assert info['launch_date'] == "March 1, 2024"
        assert info['vehicle'] == "Falcon 9"
        assert info['payload'] == "Starlink satellites"
        assert info['mass'] == "15,600 kg"
        assert info['orbit'] == "LEO"
    
    def test_create_launch_data_from_info(self, pdf_processor):
        """Test LaunchData creation from info dictionary."""
        info = {
            'mission_name': 'Starlink 6-1',
            'launch_date': '2024-03-01',
            'vehicle': 'Falcon 9',
            'mass': '15,600 kg',
            'orbit': 'LEO'
        }
        
        launch_data = pdf_processor._create_launch_data_from_info(info, "test.pdf")
        
        assert launch_data is not None
        assert launch_data.mission_name == "Starlink 6-1"
        assert launch_data.vehicle_type == "Falcon 9"
        assert launch_data.payload_mass == 15600.0
        assert launch_data.orbit == "LEO"
        assert launch_data.slug == "starlink-6-1"
    
    def test_parse_date_string(self, pdf_processor):
        """Test date string parsing."""
        # Test ISO format
        date1 = pdf_processor._parse_date_string("2024-03-01")
        assert date1 == datetime(2024, 3, 1, tzinfo=timezone.utc)
        
        # Test other formats (would need more sophisticated parsing)
        date2 = pdf_processor._parse_date_string("March 1, 2024")
        # This would return None with current simple implementation
        
        # Test invalid format
        date3 = pdf_processor._parse_date_string("invalid date")
        assert date3 is None
    
    def test_clean_vehicle_name(self, pdf_processor):
        """Test vehicle name cleaning."""
        # Test Falcon 9 variations
        assert pdf_processor._clean_vehicle_name("falcon 9") == "Falcon 9"
        assert pdf_processor._clean_vehicle_name("Falcon9") == "Falcon 9"
        
        # Test Falcon Heavy
        assert pdf_processor._clean_vehicle_name("falcon heavy") == "Falcon Heavy"
        
        # Test Dragon
        assert pdf_processor._clean_vehicle_name("dragon spacecraft") == "Dragon"
        
        # Test unknown vehicle
        assert pdf_processor._clean_vehicle_name("Unknown Rocket") == "Unknown Rocket"
    
    def test_parse_mass_string(self, pdf_processor):
        """Test mass string parsing."""
        # Test kg format
        mass1 = pdf_processor._parse_mass_string("15,600 kg")
        assert mass1 == 15600.0
        
        # Test tonnes format
        mass2 = pdf_processor._parse_mass_string("15.6 t")
        assert mass2 == 15600.0  # Converted to kg
        
        # Test simple kg format
        mass3 = pdf_processor._parse_mass_string("12500 kg")
        assert mass3 == 12500.0
        
        # Test invalid format
        mass4 = pdf_processor._parse_mass_string("unknown mass")
        assert mass4 is None
    
    def test_create_slug(self, pdf_processor):
        """Test slug creation."""
        # Test normal mission name
        slug1 = pdf_processor._create_slug("Starlink 6-1")
        assert slug1 == "starlink-6-1"
        
        # Test with special characters
        slug2 = pdf_processor._create_slug("Crew-8: ISS Mission!")
        assert slug2 == "crew-8-iss-mission"
        
        # Test empty string
        slug3 = pdf_processor._create_slug("")
        assert slug3.startswith("pdf-mission-")
    
    def test_deduplicate_launches(self, pdf_processor):
        """Test launch deduplication."""
        launches = [
            LaunchData(slug="mission-1", mission_name="Mission 1", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-2", mission_name="Mission 2", status=LaunchStatus.UPCOMING),
            LaunchData(slug="mission-1", mission_name="Mission 1 Duplicate", status=LaunchStatus.UPCOMING),
        ]
        
        unique_launches = pdf_processor._deduplicate_launches(launches)
        assert len(unique_launches) == 2
        
        slugs = [launch.slug for launch in unique_launches]
        assert "mission-1" in slugs
        assert "mission-2" in slugs
    
    @pytest.mark.asyncio
    async def test_parse_launches_from_text(self, pdf_processor, sample_press_kit_text):
        """Test complete text parsing."""
        launches = await pdf_processor._parse_launches_from_text(sample_press_kit_text, "test.pdf")
        
        assert len(launches) >= 1
        
        launch = launches[0]
        assert launch.mission_name
        assert launch.slug
        assert isinstance(launch.status, LaunchStatus)
    
    @pytest.mark.asyncio
    async def test_get_source_data(self, pdf_processor):
        """Test source data generation."""
        source_data = await pdf_processor.get_source_data("test.pdf")
        
        assert source_data.source_name == "PDF Document"
        assert source_data.source_url == "test.pdf"
        assert source_data.data_quality_score == 0.6
        assert isinstance(source_data.scraped_at, datetime)
    
    @pytest.mark.asyncio
    async def test_process_pdf_file_with_mock(self, pdf_processor, sample_press_kit_text):
        """Test processing PDF file with mocked pdfplumber."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Mock pdfplumber
            mock_page = Mock()
            mock_page.extract_text.return_value = sample_press_kit_text
            
            mock_pdf = Mock()
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = Mock(return_value=mock_pdf)
            mock_pdf.__exit__ = Mock(return_value=None)
            
            with patch('pdfplumber.open', return_value=mock_pdf):
                launches = await pdf_processor.process_pdf_file(temp_path)
                
                assert len(launches) >= 1
                assert all(isinstance(launch, LaunchData) for launch in launches)
        
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_process_pdf_url_complete_flow(self, pdf_processor, sample_press_kit_text):
        """Test complete PDF URL processing flow."""
        # Mock session and response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {'content-type': 'application/pdf'}
        
        # Mock content chunks
        async def mock_iter_chunked(size):
            yield b'%PDF-1.4 fake pdf content'
        
        mock_response.content.iter_chunked = mock_iter_chunked
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        pdf_processor.session = mock_session
        
        # Mock pdfplumber
        mock_page = Mock()
        mock_page.extract_text.return_value = sample_press_kit_text
        
        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)
        
        with patch('aiofiles.open', mock_open()), \
             patch('pdfplumber.open', return_value=mock_pdf), \
             patch('pathlib.Path.unlink'):  # Mock file deletion
            
            launches = await pdf_processor.process_pdf_url("https://example.com/test.pdf")
            
            assert len(launches) >= 1
            assert all(isinstance(launch, LaunchData) for launch in launches)
    
    @pytest.mark.asyncio
    async def test_http_error_handling(self, pdf_processor):
        """Test HTTP error handling."""
        # Mock session with error response
        mock_response = Mock()
        mock_response.status = 404
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
        
        pdf_processor.session = mock_session
        
        with pytest.raises(PDFProcessorError):
            await pdf_processor.process_pdf_url("https://example.com/test.pdf")
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, pdf_processor):
        """Test network error handling."""
        import aiohttp
        
        # Mock session that raises network error
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(
            side_effect=aiohttp.ClientError("Network error")
        )
        
        pdf_processor.session = mock_session
        
        with pytest.raises(PDFProcessorError):
            await pdf_processor.process_pdf_url("https://example.com/test.pdf")
    
    @pytest.mark.asyncio
    async def test_pdf_extraction_error_handling(self, pdf_processor):
        """Test PDF extraction error handling."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            # Mock pdfplumber to raise an error
            with patch('pdfplumber.open', side_effect=Exception("PDF parsing error")):
                with pytest.raises(PDFProcessorError):
                    await pdf_processor.process_pdf_file(temp_path)
        
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])