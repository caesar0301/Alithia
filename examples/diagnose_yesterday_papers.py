"""
Diagnostic script to investigate why yesterday's ArXiv query returns 0 papers.

This script tests various scenarios to understand:
1. What papers are actually available (without date filter)
2. What the most recent paper dates are
3. Whether the date format works correctly
4. Why yesterday's query might return 0 papers
"""

from datetime import datetime, timedelta

from alithia.utils.arxiv_paper_fetcher import (
    ArxivPaperFetcher,
    build_arxiv_search_query,
)


def test_yesterday_query():
    """Test querying for yesterday's papers."""
    print("=" * 80)
    print("Test 1: Querying Yesterday's Papers")
    print("=" * 80)

    # Calculate yesterday
    yesterday = datetime.now() - timedelta(days=1)
    from_time = yesterday.strftime("%Y%m%d") + "0000"
    to_time = yesterday.strftime("%Y%m%d") + "2359"

    print(f"Yesterday: {yesterday.strftime('%Y-%m-%d')}")
    print(f"Date range: {from_time} to {to_time}")
    print()

    fetcher = ArxivPaperFetcher(max_retries=2)
    result = fetcher.fetch_papers(
        arxiv_query="cs.AI+cs.CV+cs.LG+cs.CL",
        from_time=from_time,
        to_time=to_time,
        max_results=10,
        debug=True,
    )

    print(f"Strategy used: {result.strategy_used}")
    print(f"Success: {result.success}")
    print(f"Papers found: {len(result.papers)}")
    print(f"Elapsed time: {result.elapsed_time:.2f}s")

    if result.papers:
        print("\nPapers found:")
        for i, paper in enumerate(result.papers[:5], 1):
            print(f"  {i}. {paper.arxiv_id} - {paper.title[:60]}...")
            if paper.published_date:
                print(f"     Published: {paper.published_date.strftime('%Y-%m-%d')}")
    else:
        print("\n⚠️  No papers found for yesterday!")
    print()


def test_recent_papers_no_date_filter():
    """Test what papers are available without date filter."""
    print("=" * 80)
    print("Test 2: Recent Papers (No Date Filter)")
    print("=" * 80)

    fetcher = ArxivPaperFetcher(max_retries=2)
    result = fetcher._fetch_with_rss_feed(
        arxiv_query="cs.AI+cs.CV+cs.LG+cs.CL",
        max_results=20,
    )

    print(f"Strategy: RSS Feed")
    print(f"Success: {result.success}")
    print(f"Papers found: {len(result.papers)}")
    print()

    if result.papers:
        print("Most recent papers (first 10):")
        for i, paper in enumerate(result.papers[:10], 1):
            date_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "unknown"
            print(f"  {i}. [{date_str}] {paper.arxiv_id} - {paper.title[:50]}...")

        # Analyze dates
        dates = [p.published_date for p in result.papers if p.published_date]
        if dates:
            most_recent = max(dates)
            oldest = min(dates)
            print(f"\nDate analysis:")
            print(f"  Most recent: {most_recent.strftime('%Y-%m-%d')}")
            print(f"  Oldest: {oldest.strftime('%Y-%m-%d')}")
            print(f"  Date range: {(most_recent - oldest).days} days")

            # Count papers by date
            from collections import Counter

            date_counts = Counter(d.strftime("%Y-%m-%d") for d in dates)
            print(f"\nPapers by date (most recent first):")
            for date, count in sorted(date_counts.items(), reverse=True)[:10]:
                print(f"  {date}: {count} papers")
    else:
        print("⚠️  No papers found in RSS feed!")
    print()


def test_date_format_verification():
    """Test if date format works by querying a known date with papers."""
    print("=" * 80)
    print("Test 3: Date Format Verification")
    print("=" * 80)

    # First, get a recent paper to find a date that has papers
    fetcher = ArxivPaperFetcher(max_retries=2)
    rss_result = fetcher._fetch_with_rss_feed(
        arxiv_query="cs.AI+cs.CV+cs.LG+cs.CL",
        max_results=5,
    )

    if not rss_result.papers:
        print("⚠️  Cannot verify date format - no papers found in RSS feed")
        return

    # Get the most recent paper's date
    recent_paper = rss_result.papers[0]
    if not recent_paper.published_date:
        print("⚠️  Cannot verify date format - recent paper has no published date")
        return

    test_date = recent_paper.published_date
    from_time = test_date.strftime("%Y%m%d") + "0000"
    to_time = test_date.strftime("%Y%m%d") + "2359"

    print(f"Testing date format with known date: {test_date.strftime('%Y-%m-%d')}")
    print(f"Date range format: {from_time} to {to_time}")
    print()

    # Build query
    query = build_arxiv_search_query("cs.AI+cs.CV+cs.LG+cs.CL", from_time, to_time)
    print(f"Query: {query}")
    print()

    # Test the query
    api_result = fetcher._fetch_with_api_search(
        arxiv_query="cs.AI+cs.CV+cs.LG+cs.CL",
        from_time=from_time,
        to_time=to_time,
        max_results=10,
    )

    print(f"API search result:")
    print(f"  Success: {api_result.success}")
    print(f"  Papers found: {len(api_result.papers)}")

    if api_result.papers:
        print(f"  ✅ Date format works! Found {len(api_result.papers)} papers for {test_date.strftime('%Y-%m-%d')}")
        for i, paper in enumerate(api_result.papers[:3], 1):
            print(f"    {i}. {paper.arxiv_id} - {paper.title[:50]}...")
    else:
        print(f"  ❌ Date format may be incorrect - 0 papers found for known date {test_date.strftime('%Y-%m-%d')}")
    print()


def test_multiple_date_ranges():
    """Test multiple recent date ranges to find where papers exist."""
    print("=" * 80)
    print("Test 4: Multiple Date Ranges")
    print("=" * 80)

    fetcher = ArxivPaperFetcher(max_retries=1)

    # Test last 7 days
    for days_ago in range(7):
        test_date = datetime.now() - timedelta(days=days_ago)
        from_time = test_date.strftime("%Y%m%d") + "0000"
        to_time = test_date.strftime("%Y%m%d") + "2359"

        result = fetcher._fetch_with_api_search(
            arxiv_query="cs.AI",
            from_time=from_time,
            to_time=to_time,
            max_results=5,
        )

        date_str = test_date.strftime("%Y-%m-%d")
        status = "✅" if len(result.papers) > 0 else "❌"
        print(f"{status} {date_str}: {len(result.papers)} papers")

    print()


def test_category_query():
    """Test if categories work without date filter."""
    print("=" * 80)
    print("Test 5: Category Query Test (No Date Filter)")
    print("=" * 80)

    import arxiv

    categories = "cs.AI+cs.CV+cs.LG+cs.CL"
    category_query = "cat:cs.AI OR cat:cs.CV OR cat:cs.LG OR cat:cs.CL"

    print(f"Categories: {categories}")
    print(f"Query: {category_query}")
    print()

    client = arxiv.Client(num_retries=2, delay_seconds=1)
    search = arxiv.Search(
        query=category_query,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
        max_results=10,
    )

    papers = []
    for result in client.results(search):
        papers.append(result)
        if len(papers) >= 10:
            break

    print(f"Found {len(papers)} papers (no date filter)")
    if papers:
        print("\nMost recent papers:")
        for i, paper in enumerate(papers[:5], 1):
            date_str = (
                paper.published.strftime("%Y-%m-%d") if hasattr(paper, "published") and paper.published else "unknown"
            )
            print(f"  {i}. [{date_str}] {paper.get_short_id()} - {paper.title[:50]}...")
    print()


def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 80)
    print("ArXiv Yesterday Papers Diagnostic Tool")
    print("=" * 80)
    print(f"Current date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        test_category_query()
        test_recent_papers_no_date_filter()
        test_date_format_verification()
        test_multiple_date_ranges()
        test_yesterday_query()

        print("=" * 80)
        print("Diagnostic Summary")
        print("=" * 80)
        print("""
Interpretation:
1. If Test 5 (category query) returns papers → Categories are valid
2. If Test 2 (RSS feed) shows recent papers → ArXiv has papers available
3. If Test 3 (date format) works → Date format is correct
4. If Test 4 shows gaps → Some days have no submissions
5. If yesterday (Test 1) returns 0 → Likely indexing delay or no submissions

Common issues:
- ArXiv API indexing delay: Papers may take hours/days to appear in API
- No submissions: Some days (especially weekends/holidays) have fewer papers
- Date format: Verify YYYYMMDDHHMM format matches ArXiv API expectations
        """)

    except Exception as e:
        print(f"\n❌ Error during diagnostics: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
