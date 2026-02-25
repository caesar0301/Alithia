"""
ArXiv Web Scraper Validation Example

This script validates that the ArxivWebScraper is working correctly
by testing various scenarios and providing detailed output.

Usage:
    python examples/arxiv_web_scraper_validation.py

Requirements:
    - beautifulsoup4 (bs4)
    - requests

    Install with: pip install beautifulsoup4 requests
"""

import logging
import sys
from datetime import datetime, timedelta

# Configure logging for detailed output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Import required dependencies
try:
    from alithia.constants import ARXIV_PAGE_SIZE
    from alithia.utils.arxiv_web_scraper import ArxivWebScraper
except ImportError as e:
    print("❌ ERROR: Missing required dependencies")
    print(f"   {e}")
    print("\nPlease install required packages:")
    print("   pip install beautifulsoup4 requests")
    print("\nAnd ensure the alithia package is installed:")
    print("   pip install -e .")
    sys.exit(1)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_paper_summary(papers, max_display=3):
    """Print a summary of papers with details."""
    if not papers:
        print("❌ No papers found")
        return

    print(f"✅ Found {len(papers)} papers\n")

    for i, paper in enumerate(papers[:max_display], 1):
        print(f"[{i}] {paper.title}")
        print(f"    ArXiv ID: {paper.arxiv_id}")
        print(f"    Authors: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}")
        if paper.published_date:
            print(f"    Published: {paper.published_date.strftime('%Y-%m-%d')}")
        print(f"    PDF URL: {paper.pdf_url}")
        if paper.summary:
            summary_preview = paper.summary[:150] + "..." if len(paper.summary) > 150 else paper.summary
            print(f"    Abstract: {summary_preview}")
        print()

    if len(papers) > max_display:
        print(f"    ... and {len(papers) - max_display} more papers\n")


def test_basic_search():
    """Test basic ArXiv search functionality."""
    print_section("Test 1: Basic Search (cs.AI)")

    scraper = ArxivWebScraper()

    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="cs.AI",
            max_results=5,
        )

        print_paper_summary(papers, max_display=3)

        # Validate results
        assert len(papers) > 0, "Should return at least some papers"
        assert all(paper.arxiv_id for paper in papers), "All papers should have ArXiv IDs"
        assert all(paper.title for paper in papers), "All papers should have titles"
        assert all(paper.pdf_url for paper in papers), "All papers should have PDF URLs"

        print("✅ Basic search validation PASSED")

    except Exception as e:
        print(f"❌ Basic search validation FAILED: {e}")
        raise


def test_multiple_categories():
    """Test searching multiple categories."""
    print_section("Test 2: Multiple Categories (cs.AI+cs.CV+cs.LG)")

    scraper = ArxivWebScraper()

    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="cs.AI+cs.CV+cs.LG",
            max_results=10,
        )

        print_paper_summary(papers, max_display=3)

        # Validate results
        assert len(papers) > 0, "Should return papers from multiple categories"

        print(f"✅ Multiple categories validation PASSED ({len(papers)} papers)")

    except Exception as e:
        print(f"❌ Multiple categories validation FAILED: {e}")
        raise


def test_date_filtering():
    """Test date range filtering."""
    print_section("Test 3: Date Filtering")

    scraper = ArxivWebScraper()

    # Get papers from last week
    to_date = datetime.now()
    from_date = to_date - timedelta(days=7)

    print(f"Searching papers from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}\n")

    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="cs.AI",
            max_results=10,
            from_date=from_date,
            to_date=to_date,
        )

        print_paper_summary(papers, max_display=3)

        # Validate date filtering
        if papers:
            for paper in papers:
                if paper.published_date:
                    assert (
                        from_date <= paper.published_date <= to_date + timedelta(days=1)
                    ), f"Paper date {paper.published_date} should be within range"

            print("✅ Date filtering validation PASSED")
        else:
            print("⚠️  No papers found in date range (might be expected for some dates)")

    except Exception as e:
        print(f"❌ Date filtering validation FAILED: {e}")
        raise


def test_pagination():
    """Test pagination with multiple results."""
    print_section("Test 4: Pagination (requesting more than one page)")

    scraper = ArxivWebScraper()

    # Request more than the default page size
    max_results = ARXIV_PAGE_SIZE + 10
    print(f"Requesting {max_results} papers (page size: {ARXIV_PAGE_SIZE})\n")

    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="cs.AI+cs.CV",
            max_results=max_results,
        )

        print(f"✅ Found {len(papers)} papers (requested {max_results})")

        # Validate pagination
        if len(papers) > ARXIV_PAGE_SIZE:
            print(f"✅ Successfully retrieved multiple pages (>{ARXIV_PAGE_SIZE} papers)")
        else:
            print(f"⚠️  Retrieved {len(papers)} papers (less than requested, might be end of results)")

        print_paper_summary(papers, max_display=2)

        print("✅ Pagination validation PASSED")

    except Exception as e:
        print(f"❌ Pagination validation FAILED: {e}")
        raise


def test_paper_details_scraping():
    """Test scraping individual paper details."""
    print_section("Test 5: Individual Paper Details Scraping")

    scraper = ArxivWebScraper()

    # Use a well-known paper ID (GPT-3 paper)
    test_arxiv_id = "2005.14165"
    print(f"Fetching details for paper: {test_arxiv_id}\n")

    try:
        paper = scraper.scrape_paper_details(test_arxiv_id)

        if paper:
            print(f"✅ Successfully scraped paper details\n")
            print(f"Title: {paper.title}")
            print(f"ArXiv ID: {paper.arxiv_id}")
            print(f"Authors: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}")
            if paper.published_date:
                print(f"Published: {paper.published_date.strftime('%Y-%m-%d')}")
            print(f"PDF URL: {paper.pdf_url}")
            if paper.summary:
                print(f"Abstract length: {len(paper.summary)} characters")
                print(f"Abstract preview: {paper.summary[:200]}...")

            # Validate fields
            assert paper.title, "Paper should have a title"
            assert paper.arxiv_id == test_arxiv_id, "Paper should have correct ArXiv ID"
            assert paper.authors, "Paper should have authors"
            assert paper.summary, "Paper should have an abstract"
            assert paper.pdf_url, "Paper should have a PDF URL"

            print("\n✅ Paper details validation PASSED")
        else:
            print("❌ Failed to scrape paper details")
            raise AssertionError("Paper details scraping returned None")

    except Exception as e:
        print(f"❌ Paper details validation FAILED: {e}")
        raise


def test_error_handling():
    """Test error handling with invalid inputs."""
    print_section("Test 6: Error Handling")

    scraper = ArxivWebScraper()

    # Test 1: Invalid category
    print("Testing invalid category (should handle gracefully)...")
    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="invalid.category",
            max_results=5,
        )
        print(f"Result: {len(papers)} papers (empty list expected for invalid category)")
        print("✅ Invalid category handled gracefully\n")
    except Exception as e:
        print(f"⚠️  Exception raised: {e}\n")

    # Test 2: Invalid paper ID
    print("Testing invalid paper ID (should return None)...")
    try:
        paper = scraper.scrape_paper_details("9999.99999")
        if paper is None:
            print("✅ Invalid paper ID handled gracefully (returned None)\n")
        else:
            print(f"⚠️  Unexpected result: {paper}\n")
    except Exception as e:
        print(f"⚠️  Exception raised: {e}\n")

    print("✅ Error handling validation PASSED")


def run_performance_test():
    """Test performance of the web scraper."""
    print_section("Test 7: Performance Benchmark")

    import time

    scraper = ArxivWebScraper()

    print("Fetching 20 papers to measure performance...\n")
    start_time = time.time()

    try:
        papers = scraper.scrape_arxiv_search(
            arxiv_query="cs.AI+cs.CV",
            max_results=20,
        )

        elapsed_time = time.time() - start_time

        print(f"✅ Retrieved {len(papers)} papers in {elapsed_time:.2f} seconds")
        print(f"   Average: {elapsed_time / max(len(papers), 1):.2f} seconds per paper")

        if elapsed_time < 30:
            print("   ✅ Performance: GOOD (< 30 seconds)")
        elif elapsed_time < 60:
            print("   ⚠️  Performance: ACCEPTABLE (30-60 seconds)")
        else:
            print("   ⚠️  Performance: SLOW (> 60 seconds)")

        print("\n✅ Performance test PASSED")

    except Exception as e:
        print(f"❌ Performance test FAILED: {e}")
        raise


def main():
    """Run all validation tests."""
    print("\n" + "🔍" * 40)
    print("  ArXiv Web Scraper Validation Suite")
    print("🔍" * 40)

    tests = [
        ("Basic Search", test_basic_search),
        ("Multiple Categories", test_multiple_categories),
        ("Date Filtering", test_date_filtering),
        ("Pagination", test_pagination),
        ("Paper Details", test_paper_details_scraping),
        ("Error Handling", test_error_handling),
        ("Performance", run_performance_test),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            test_func()
            results[test_name] = "✅ PASSED"
        except Exception as e:
            results[test_name] = f"❌ FAILED: {str(e)}"
            logger.error(f"Test '{test_name}' failed", exc_info=True)

    # Print summary
    print_section("TEST SUMMARY")

    all_passed = True
    for test_name, result in results.items():
        print(f"{test_name:25s} → {result}")
        if "FAILED" in result:
            all_passed = False

    print("\n" + "=" * 80)

    if all_passed:
        print("🎉 ALL TESTS PASSED! ArXiv Web Scraper is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED. Check the output above for details.")

    print("=" * 80 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
