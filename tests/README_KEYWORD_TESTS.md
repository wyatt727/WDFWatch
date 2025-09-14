# Keyword System Test Suite

## Overview

This comprehensive test suite validates the keyword optimization system without requiring Twitter API keys. It simulates the entire pipeline from keyword discovery through multi-episode learning convergence.

## Test Coverage

### Core Components Tested
- ✅ **Twitter API v2 Query Building**
  - Proper operator syntax (`min_faves`, not `min_likes`)
  - Engagement thresholds
  - Exclusion operators (`-is:reply`, `-is:retweet`)
  - Time range parameters
  - Query length validation (512 char limit)
  - OR operator limits (25 max)

- ✅ **Keyword Weight Learning**
  - Initial weight assignment
  - Updates after classification
  - Learning rate application (0.3 factor)
  - Decay over time (30 days)
  - Weight boundaries (0.05 min, 1.0 max)
  - Persistence and loading

- ✅ **Keyword Prioritization**
  - Three-tier system (high ≥0.8, medium 0.5-0.8, low <0.5)
  - High-weight keywords searched first
  - Conditional execution for lower tiers
  - Low-weight keyword limiting

- ✅ **API Quota Management**
  - 10,000 monthly quota tracking
  - 180 searches/15min rate limiting
  - Credit estimation before execution
  - Progressive search strategy

- ✅ **Tweet Caching**
  - ALL tweets saved (including irrelevant)
  - Keyword-based filtering
  - Age-based cleanup (90 days)
  - Cache retrieval for testing

- ✅ **Multi-Episode Simulation**
  - Keyword convergence from 200 to ~30
  - Bad keywords drop below 0.5 weight
  - Good keywords rise above 0.8 weight
  - API usage optimization over time

## Test Files

### `test_keyword_system.py`
Main test suite with 50+ test cases covering:
- MockTwitterAPIv2 implementation
- Query building tests
- Keyword learning tests
- Prioritization tests
- Quota management tests
- Cache tests
- Integration tests
- Performance tests

### `test_edge_cases.py`
Edge cases and boundary conditions:
- Zero keywords
- 500+ keywords stress test
- Identical weights
- Unicode/emoji keywords
- Network errors
- Malformed data
- Concurrent access

### `test_days_back_integration.py`
Critical parameter flow testing:
- Settings to scrape task
- Scrape to Twitter API
- Metadata creation and reading
- Volume calculations
- End-to-end flow

### `run_keyword_tests.py`
Test runner that:
- Executes all test suites
- Generates console summary
- Creates JSON results
- Produces HTML report
- Provides confidence assessment

## Running the Tests

### Quick Test
```bash
# Run all tests with summary
python tests/run_keyword_tests.py
```

### Individual Test Suites
```bash
# Run specific test file
python -m pytest tests/test_keyword_system.py -v

# Or with unittest
python tests/test_keyword_system.py
```

### With Coverage
```bash
# Install coverage
pip install coverage

# Run with coverage
coverage run tests/run_keyword_tests.py
coverage report
coverage html  # Creates htmlcov/index.html
```

## What We Learn From Tests

### Keyword Convergence
- System naturally converges from 200+ keywords to ~30 effective ones
- Takes approximately 10 episodes for convergence
- Bad keywords drop below 0.5 weight threshold
- Good keywords rise above 0.8 weight threshold

### API Efficiency
- Initial episodes use more API credits
- Credit usage decreases as system learns
- Keyword grouping reduces API calls
- Progressive search saves unnecessary calls

### Error Resilience
- Handles network timeouts gracefully
- Recovers from rate limiting
- Manages corrupted data files
- Preserves all tweets for analysis

## Confidence Assessment

The test suite provides three confidence levels:

### 🟢 HIGH CONFIDENCE (≥95% pass rate)
- System ready for production use
- Safe to use real API keys
- Core functionality verified
- Edge cases handled

### 🟡 MODERATE CONFIDENCE (80-94% pass rate)
- System mostly ready
- Review failing tests
- Fix issues before production
- Most functionality working

### 🔴 LOW CONFIDENCE (<80% pass rate)
- System needs work
- Critical issues present
- Do not use real API keys
- Debug and fix failures

## Test Data

### Mock Tweet Generation
The test suite generates 500 mock tweets with:
- 30% relevant (WDF-related topics)
- 70% irrelevant (general topics)
- Varying engagement levels
- Realistic timestamps
- Proper metadata

### Keyword Sets
Tests use various keyword sets:
- Small (10 keywords)
- Medium (50 keywords)
- Large (200+ keywords)
- Edge cases (unicode, empty, duplicates)

## Performance Benchmarks

The test suite validates performance with:
- 1000 keywords: Query building < 1 second
- 10,000 tweets: Classification < 5 seconds
- Large cache: Memory usage within limits

## Integration with CI/CD

The test suite is designed for CI/CD integration:
- Returns proper exit codes
- Generates machine-readable JSON
- Produces human-readable HTML
- Supports parallel execution

## Extending the Tests

To add new tests:

1. Create test methods in appropriate file
2. Follow naming convention `test_*`
3. Use MockTwitterAPIv2 for API simulation
4. Document expected behavior
5. Run full suite to verify

## Troubleshooting

### Import Errors
```bash
# Ensure you're in project root
cd /path/to/WDFWatch
python tests/run_keyword_tests.py
```

### Missing Dependencies
```bash
# Install test requirements
pip install pytest unittest-mock
```

### File Path Issues
Tests use temporary files and should work cross-platform. If issues occur, check that temp directory is writable.

## Summary

This test suite provides comprehensive validation of the keyword system without requiring API keys. It simulates realistic scenarios, tests edge cases, and provides confidence that the system will work correctly when real API keys are added.

**Key Achievement**: We can now validate the entire keyword optimization pipeline, including:
- Proper Twitter API v2 syntax
- Engagement threshold implementation
- days_back parameter flow
- Keyword learning convergence
- API credit preservation
- Cache effectiveness

**Result**: With a passing test suite, you can be confident that the system will:
1. Build correct API queries
2. Respect quota limits
3. Learn from classification results
4. Converge on effective keywords
5. Handle errors gracefully
6. Preserve all data for analysis