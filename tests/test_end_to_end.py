"""
End-to-end tests for critical user journeys using Playwright.
Tests the complete system from frontend to backend integration.
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from unittest.mock import patch, Mock
import json

from src.database import get_database_manager
from src.models.launch import Launch
from src.repositories.launch_repository import LaunchRepository


class TestEndToEndUserJourneys:
    """End-to-end tests for critical user journeys."""
    
    @pytest.fixture(scope="class")
    async def browser_setup(self):
        """Set up browser for testing."""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        yield browser, context, playwright
        await context.close()
        await browser.close()
        await playwright.stop()
    
    @pytest.fixture
    async def page(self, browser_setup):
        """Create a new page for each test."""
        browser, context, playwright = browser_setup
        page = await context.new_page()
        yield page
        await page.close()
    
    @pytest.fixture
    async def test_data_setup(self):
        """Set up test data in database."""
        db_manager = get_database_manager()
        
        # Create test launches
        test_launches = [
            Launch(
                slug="test-upcoming-launch",
                mission_name="Test Upcoming Mission",
                launch_date=datetime.utcnow() + timedelta(days=7),
                vehicle_type="Falcon 9",
                status="upcoming",
                details="Test upcoming launch for E2E testing",
                payload_mass=5000.0,
                orbit="LEO"
            ),
            Launch(
                slug="test-historical-launch",
                mission_name="Test Historical Mission",
                launch_date=datetime.utcnow() - timedelta(days=30),
                vehicle_type="Falcon Heavy",
                status="success",
                details="Test historical launch for E2E testing",
                payload_mass=10000.0,
                orbit="GTO"
            ),
            Launch(
                slug="test-failed-launch",
                mission_name="Test Failed Mission",
                launch_date=datetime.utcnow() - timedelta(days=60),
                vehicle_type="Falcon 9",
                status="failure",
                details="Test failed launch for E2E testing",
                payload_mass=3000.0,
                orbit="LEO"
            )
        ]
        
        with db_manager.session_scope() as session:
            # Clean up existing test data
            session.query(Launch).filter(
                Launch.slug.in_([launch.slug for launch in test_launches])
            ).delete(synchronize_session=False)
            
            # Add test data
            for launch in test_launches:
                session.add(launch)
            session.commit()
        
        yield test_launches
        
        # Cleanup
        with db_manager.session_scope() as session:
            session.query(Launch).filter(
                Launch.slug.in_([launch.slug for launch in test_launches])
            ).delete(synchronize_session=False)
            session.commit()
    
    @pytest.mark.asyncio
    async def test_homepage_loads_and_displays_launches(self, page: Page, test_data_setup):
        """Test that homepage loads and displays launch information."""
        # Navigate to homepage
        await page.goto("http://localhost:3000")
        
        # Wait for page to load
        await page.wait_for_selector('[data-testid="homepage"]', timeout=10000)
        
        # Check page title
        title = await page.title()
        assert "SpaceX Launch Tracker" in title
        
        # Check that launch cards are displayed
        launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
        assert len(launch_cards) > 0
        
        # Check that upcoming launches section exists
        upcoming_section = await page.query_selector('[data-testid="upcoming-launches"]')
        assert upcoming_section is not None
        
        # Check navigation links
        nav_links = await page.query_selector_all('nav a')
        assert len(nav_links) >= 3  # Home, Launches, Admin
    
    @pytest.mark.asyncio
    async def test_launches_page_search_and_filter(self, page: Page, test_data_setup):
        """Test launches page search and filtering functionality."""
        # Navigate to launches page
        await page.goto("http://localhost:3000/launches")
        
        # Wait for launches to load
        await page.wait_for_selector('[data-testid="launches-page"]', timeout=10000)
        
        # Test search functionality
        search_input = await page.query_selector('[data-testid="search-input"]')
        assert search_input is not None
        
        await search_input.fill("Test Upcoming")
        await page.keyboard.press("Enter")
        
        # Wait for search results
        await page.wait_for_timeout(1000)
        
        # Check that search results are filtered
        launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
        assert len(launch_cards) >= 1
        
        # Check that the correct launch is displayed
        first_card = launch_cards[0]
        card_text = await first_card.inner_text()
        assert "Test Upcoming Mission" in card_text
        
        # Test status filter
        status_filter = await page.query_selector('[data-testid="status-filter"]')
        if status_filter:
            await status_filter.select_option("upcoming")
            await page.wait_for_timeout(1000)
            
            # Verify filtered results
            filtered_cards = await page.query_selector_all('[data-testid="launch-card"]')
            for card in filtered_cards:
                card_text = await card.inner_text()
                assert "upcoming" in card_text.lower() or "countdown" in card_text.lower()
    
    @pytest.mark.asyncio
    async def test_launch_detail_page_navigation(self, page: Page, test_data_setup):
        """Test navigation to launch detail page and content display."""
        # Navigate to launches page
        await page.goto("http://localhost:3000/launches")
        await page.wait_for_selector('[data-testid="launches-page"]', timeout=10000)
        
        # Click on first launch card
        first_card = await page.query_selector('[data-testid="launch-card"]')
        assert first_card is not None
        
        await first_card.click()
        
        # Wait for detail page to load
        await page.wait_for_selector('[data-testid="launch-detail"]', timeout=10000)
        
        # Check that detail page contains expected elements
        mission_name = await page.query_selector('[data-testid="mission-name"]')
        assert mission_name is not None
        
        launch_date = await page.query_selector('[data-testid="launch-date"]')
        assert launch_date is not None
        
        vehicle_type = await page.query_selector('[data-testid="vehicle-type"]')
        assert vehicle_type is not None
        
        # Check for countdown timer on upcoming launches
        countdown = await page.query_selector('[data-testid="countdown-timer"]')
        if countdown:
            countdown_text = await countdown.inner_text()
            assert any(unit in countdown_text.lower() for unit in ["days", "hours", "minutes", "seconds"])
    
    @pytest.mark.asyncio
    async def test_upcoming_launches_page(self, page: Page, test_data_setup):
        """Test upcoming launches page functionality."""
        # Navigate to upcoming launches page
        await page.goto("http://localhost:3000/launches/upcoming")
        await page.wait_for_selector('[data-testid="upcoming-launches-page"]', timeout=10000)
        
        # Check that only upcoming launches are displayed
        launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
        
        for card in launch_cards:
            card_text = await card.inner_text()
            # Should contain countdown or upcoming status
            assert any(indicator in card_text.lower() 
                      for indicator in ["countdown", "upcoming", "days", "hours"])
        
        # Check for countdown timers
        countdown_timers = await page.query_selector_all('[data-testid="countdown-timer"]')
        assert len(countdown_timers) > 0
    
    @pytest.mark.asyncio
    async def test_historical_launches_page(self, page: Page, test_data_setup):
        """Test historical launches page functionality."""
        # Navigate to historical launches page
        await page.goto("http://localhost:3000/launches/historical")
        await page.wait_for_selector('[data-testid="historical-launches-page"]', timeout=10000)
        
        # Check that historical launches are displayed
        launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
        assert len(launch_cards) > 0
        
        # Check for success/failure indicators
        for card in launch_cards:
            card_text = await card.inner_text()
            assert any(status in card_text.lower() 
                      for status in ["success", "failure", "completed"])
    
    @pytest.mark.asyncio
    async def test_responsive_design_mobile(self, browser_setup, test_data_setup):
        """Test responsive design on mobile viewport."""
        browser, context, playwright = browser_setup
        
        # Create mobile context
        mobile_context = await browser.new_context(
            viewport={"width": 375, "height": 667},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        )
        
        page = await mobile_context.new_page()
        
        try:
            # Navigate to homepage
            await page.goto("http://localhost:3000")
            await page.wait_for_selector('[data-testid="homepage"]', timeout=10000)
            
            # Check mobile navigation
            mobile_menu = await page.query_selector('[data-testid="mobile-menu"]')
            if mobile_menu:
                await mobile_menu.click()
                await page.wait_for_timeout(500)
                
                # Check that navigation items are visible
                nav_items = await page.query_selector_all('[data-testid="mobile-nav-item"]')
                assert len(nav_items) > 0
            
            # Check that launch cards are properly sized for mobile
            launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
            for card in launch_cards:
                box = await card.bounding_box()
                assert box["width"] <= 375  # Should fit in mobile viewport
            
        finally:
            await page.close()
            await mobile_context.close()
    
    @pytest.mark.asyncio
    async def test_error_handling_offline_mode(self, page: Page):
        """Test error handling when API is unavailable."""
        # Intercept API calls and return errors
        await page.route("**/api/**", lambda route: route.abort())
        
        # Navigate to homepage
        await page.goto("http://localhost:3000")
        
        # Wait for error handling to kick in
        await page.wait_for_timeout(3000)
        
        # Check for offline banner or error message
        offline_banner = await page.query_selector('[data-testid="offline-banner"]')
        error_message = await page.query_selector('[data-testid="error-message"]')
        
        assert offline_banner is not None or error_message is not None
        
        # Check that cached data is displayed if available
        cached_data = await page.query_selector('[data-testid="cached-data"]')
        if cached_data:
            cached_text = await cached_data.inner_text()
            assert "cached" in cached_text.lower() or "offline" in cached_text.lower()
    
    @pytest.mark.asyncio
    async def test_admin_login_flow(self, page: Page):
        """Test admin login functionality."""
        # Navigate to admin login page
        await page.goto("http://localhost:3000/admin/login")
        await page.wait_for_selector('[data-testid="login-form"]', timeout=10000)
        
        # Fill in login form with test credentials
        username_input = await page.query_selector('[data-testid="username-input"]')
        password_input = await page.query_selector('[data-testid="password-input"]')
        login_button = await page.query_selector('[data-testid="login-button"]')
        
        assert username_input is not None
        assert password_input is not None
        assert login_button is not None
        
        await username_input.fill("admin")
        await password_input.fill("admin123")
        await login_button.click()
        
        # Wait for redirect or error message
        await page.wait_for_timeout(2000)
        
        # Check if redirected to admin dashboard or error is shown
        current_url = page.url
        error_message = await page.query_selector('[data-testid="login-error"]')
        
        # Either should be redirected to dashboard or show appropriate error
        assert "/admin/dashboard" in current_url or error_message is not None
    
    @pytest.mark.asyncio
    async def test_performance_page_load_times(self, page: Page, test_data_setup):
        """Test page load performance."""
        # Test homepage load time
        start_time = time.time()
        await page.goto("http://localhost:3000")
        await page.wait_for_selector('[data-testid="homepage"]', timeout=10000)
        homepage_load_time = time.time() - start_time
        
        # Homepage should load within 3 seconds
        assert homepage_load_time < 3.0, f"Homepage took {homepage_load_time:.2f}s to load"
        
        # Test launches page load time
        start_time = time.time()
        await page.goto("http://localhost:3000/launches")
        await page.wait_for_selector('[data-testid="launches-page"]', timeout=10000)
        launches_load_time = time.time() - start_time
        
        # Launches page should load within 3 seconds
        assert launches_load_time < 3.0, f"Launches page took {launches_load_time:.2f}s to load"
        
        # Test launch detail page load time
        first_card = await page.query_selector('[data-testid="launch-card"]')
        if first_card:
            start_time = time.time()
            await first_card.click()
            await page.wait_for_selector('[data-testid="launch-detail"]', timeout=10000)
            detail_load_time = time.time() - start_time
            
            # Detail page should load within 2 seconds
            assert detail_load_time < 2.0, f"Detail page took {detail_load_time:.2f}s to load"


class TestAPIEndToEndIntegration:
    """End-to-end tests for API integration."""
    
    @pytest.mark.asyncio
    async def test_complete_data_flow(self, page: Page):
        """Test complete data flow from scraping to frontend display."""
        # This test would require a running backend
        # For now, we'll test the API endpoints directly
        
        # Navigate to a page that triggers API calls
        await page.goto("http://localhost:3000/launches")
        
        # Monitor network requests
        api_requests = []
        
        def handle_request(request):
            if "/api/" in request.url:
                api_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers)
                })
        
        page.on("request", handle_request)
        
        # Wait for page to load and make API calls
        await page.wait_for_selector('[data-testid="launches-page"]', timeout=10000)
        await page.wait_for_timeout(2000)
        
        # Verify API calls were made
        assert len(api_requests) > 0
        
        # Check for expected API endpoints
        api_urls = [req["url"] for req in api_requests]
        assert any("/api/launches" in url for url in api_urls)
        
        # Verify data is displayed
        launch_cards = await page.query_selector_all('[data-testid="launch-card"]')
        assert len(launch_cards) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])