#!/usr/bin/env python3
"""
Demo script for SpaceX scraper functionality.
"""

import asyncio
import logging
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scraping.spacex_scraper import SpaceXScraper
from scraping.ethical_scraper import EthicalScraper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_spacex_scraper():
    """Demonstrate SpaceX scraper functionality."""
    logger.info("Starting SpaceX scraper demo")
    
    # Create ethical scraper with conservative settings
    ethical_scraper = EthicalScraper()
    
    # Create SpaceX scraper
    scraper = SpaceXScraper(ethical_scraper)
    
    try:
        # Get source data info
        source_data = await scraper.get_source_data()
        logger.info(f"Source: {source_data.source_name}")
        logger.info(f"URL: {source_data.source_url}")
        logger.info(f"Quality Score: {source_data.data_quality_score}")
        
        # Test HTML parsing with sample data
        sample_html = """
        <html>
        <body>
            <article class="launch-card">
                <h2>Demo Mission</h2>
                <time datetime="2024-12-01T10:00:00Z">December 1, 2024</time>
                <p class="vehicle">Falcon 9</p>
                <p class="description">Demo mission for testing purposes.</p>
                <span class="status">Upcoming</span>
            </article>
        </body>
        </html>
        """
        
        logger.info("Testing HTML parsing...")
        launches = await scraper._parse_launches_from_html(sample_html)
        
        if launches:
            logger.info(f"Successfully parsed {len(launches)} launches:")
            for launch in launches:
                logger.info(f"  - {launch.mission_name} ({launch.status})")
                logger.info(f"    Vehicle: {launch.vehicle_type}")
                logger.info(f"    Slug: {launch.slug}")
        else:
            logger.warning("No launches found in sample HTML")
        
        logger.info("SpaceX scraper demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(demo_spacex_scraper())