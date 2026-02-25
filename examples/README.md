# Alithia Examples

This directory contains examples demonstrating key components of the Alithia research recommendation system.

## ArXiv Web Scraper Validation

A comprehensive validation suite for the ArXiv web scraper fallback mechanism.

### Requirements

Before running, ensure dependencies are installed:

```bash
pip install beautifulsoup4 requests
pip install -e .
```

### Running the Validation

```bash
python examples/arxiv_web_scraper_validation.py
```

### What It Tests

This validation suite runs 7 comprehensive tests:

1. **Basic Search**: Validates single-category searches work correctly
2. **Multiple Categories**: Tests searching across multiple ArXiv categories (e.g., cs.AI+cs.CV+cs.LG)
3. **Date Filtering**: Verifies date range filtering functionality
4. **Pagination**: Tests retrieving results across multiple pages
5. **Paper Details**: Validates scraping individual paper details by ArXiv ID
6. **Error Handling**: Ensures graceful handling of invalid inputs
7. **Performance**: Benchmarks scraping speed and efficiency

### Expected Output

- All tests should pass with ✅ indicators
- Performance should be under 30 seconds for 20 papers
- Displays sample papers with titles, authors, abstracts, and metadata
- Final summary shows overall validation status

### When to Use

- **After Updates**: Run after modifying web scraper code
- **Network Issues**: Test when API/RSS feed methods fail
- **Debugging**: Diagnose scraping problems with detailed logging
- **Integration Testing**: Verify scraper works in your environment

## ArXiv Yesterday Papers Diagnostic

This diagnostic tool helps investigate why yesterday's ArXiv query might return 0 papers.

### Running the Diagnostic

```bash
python examples/diagnose_yesterday_papers.py
```

This tool runs multiple tests to diagnose the issue:
1. **Category Query Test**: Verifies categories work without date filter
2. **Recent Papers (RSS)**: Shows what papers are actually available
3. **Date Format Verification**: Tests if date format works with a known date
4. **Multiple Date Ranges**: Tests last 7 days to find where papers exist
5. **Yesterday Query**: Tests the actual yesterday query

### Common Issues Diagnosed

- **ArXiv API Indexing Delay**: Papers may take hours/days to appear in API
- **No Submissions**: Some days (especially weekends/holidays) have fewer papers
- **Date Format Issues**: Verifies YYYYMMDDHHMM format works correctly
- **Category Issues**: Confirms categories are valid

## FlashRank Reranking Demo

This example demonstrates how FlashRank is used to rerank papers based on semantic relevance to a user's research corpus.

### Running the Demo

```bash
python -m examples.flashrank_demo
```

This comprehensive example demonstrates:
- Complete reranking pipeline as used in `alithia/paperscout/recommender.py`
- Time-decay weighting for recent papers
- Scoring multiple candidate papers against a corpus
- Detailed relevance analysis

**Runtime:** ~30-60 seconds  
**Note:** Requires network connection to download the FlashRank model on first run

## How FlashRank Works in Alithia

### The Problem
When new papers appear on arXiv, we need to determine which ones are most relevant to a researcher's interests.

### The Solution
1. **Semantic Similarity:** FlashRank compares paper abstracts using transformer-based embeddings, capturing conceptual relevance beyond keyword matching
2. **Corpus-Based Ranking:** Each new paper is scored against the user's entire Zotero library
3. **Time Decay:** More recent papers in the corpus get higher weights, reflecting current research interests
4. **Aggregation:** Individual relevance scores are combined with time weights to produce a final ranking

### Why This Method is Valid

1. **Semantic Understanding:** Unlike keyword matching, FlashRank understands context and meaning
   - Example: "transformer architecture" and "self-attention mechanism" are semantically related even with different words

2. **Personalization:** Scoring against the user's actual corpus ensures recommendations match their specific research direction

3. **Recency Weighting:** Time decay prevents the system from over-emphasizing older, possibly outdated research interests

4. **Proven Model:** Uses `ms-marco-MiniLM-L-12-v2`, a model trained on Microsoft's MARCO dataset for passage ranking

## Code Reference

The production implementation is in:
```
alithia/paperscout/recommender.py → rerank_papers()
```

Key parameters:
- `model_name`: FlashRank model (default: "ms-marco-MiniLM-L-12-v2")
- `corpus`: User's Zotero library papers
- `papers`: Candidate papers from arXiv to rank

## Requirements

These examples are part of the Alithia package and use the same dependencies.

If you haven't installed Alithia yet:
```bash
pip install -e .
```

The examples will then work with the installed dependencies (`flashrank`, `numpy`, etc.)

## Further Reading

- [FlashRank Documentation](https://github.com/PrithivirajDamodaran/FlashRank)
- [MS MARCO Dataset](https://microsoft.github.io/msmarco/)
- Alithia design docs: `specs/0_design.md`, `specs/1_prd.md`
