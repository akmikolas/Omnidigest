# Test Case Specifications

## 1. Twitter Processor Fix Tests

### Test 1.1: Dead Code After Return Statement
**File:** `domains/twitter/processor.py`
**Location:** Line 203-204

| Field | Value |
|-------|-------|
| Test Name | twitter_processor_dead_code_removal |
| Input | Any batch of tweets for One-Pass processing |
| Expected | Code should execute without reaching line 204 (dead code after return) |
| Verification | Run `_triage_batch_onepass` and verify no duplicate results |

**Test Steps:**
1. Call `_triage_batch_onepass` with a batch of 5 tweets
2. Verify results are returned correctly
3. Check logs for any errors related to processing

---

### Test 1.2: Threshold Logic Correction for New Events
**File:** `domains/twitter/processor.py`
**Location:** Line 136, Line 282

| Field | Value |
|-------|-------|
| Test Name | twitter_new_event_threshold_logic |
| Input | A significant tweet with `is_significant=True`, threshold=2 |
| Expected | New event should NOT trigger alert immediately (threshold must be >= 2) |

**Test Steps:**
1. Mock settings with `twitter_event_push_threshold = 2`
2. Process a new significant tweet (first of its kind)
3. Verify event is created with `source_count = 1`
4. Verify no alert is pushed (because 1 < threshold)
5. Process another similar tweet
6. Verify `source_count = 2` and alert IS pushed

---

### Test 1.3: Existing Event Threshold Logic
**File:** `domains/twitter/processor.py`
**Location:** Line 107, Line 251

| Field | Value |
|-------|-------|
| Test Name | twitter_existing_event_threshold_logic |
| Input | Second similar tweet linking to existing event with threshold=2 |
| Expected | Alert should trigger when `new_count >= threshold` |

**Test Steps:**
1. Create existing event with `source_count = 1`
2. Process a similar tweet that matches to existing event
3. Verify `increment_twitter_event_source_count` is called
4. Verify alert is pushed when `source_count >= threshold`

---

## 2. Daily Digest Status Update Tests

### Test 2.1: Status Update After LLM Classification
**File:** `domains/daily_digest/processor.py` (ContentProcessor)
**Location:** Lines 156-162

| Field | Value |
|-------|-------|
| Test Name | daily_digest_status_update_after_classification |
| Input | List of unclassified articles with `category=NULL` |
| Expected | After classification, articles should have `status=1` |

**Setup:**
```python
# Database state before test
news_articles:
  - id: "test-article-1"
    title: "Test Article"
    content: "Test content..."
    category: NULL
    score: NULL
    status: NULL  # unprocessed
```

**Test Steps:**
1. Insert test article with `status=NULL`
2. Run `ContentProcessor.run_processing_cycle()`
3. Verify article has:
   - `category` = "AI & LLMs" (or valid category)
   - `score` = 60+
   - `status` = 1 (processed) <- THIS IS THE KEY CHECK

**Expected DB State:**
```python
news_articles:
  - id: "test-article-1"
    category: "AI & LLMs"  # NOT NULL
    score: 75              # NOT NULL
    status: 1              # PROCESSED
```

---

### Test 2.2: RAG Upload Failure Handling
**File:** `domains/ingestion/rss/standard_crawler.py`
**Location:** Lines 175-184

| Field | Value |
|-------|-------|
| Test Name | daily_digest_rag_upload_failure_handling |
| Input | RSS article fetch with RAG upload failing |
| Expected | Article should still be marked as `status=1` even if RAG fails |

**Test Steps:**
1. Set `settings.ragflow_enabled = True`
2. Mock RAG client to return `None` for `upload_document`
3. Run crawler on a new RSS feed
4. Verify article is created and marked as `status=1`

**Edge Cases:**
- RAG upload returns None → should still mark as processed
- RAG upload raises exception → should still mark as processed
- RAG upload succeeds → should mark with ragflow_id

---

### Test 2.3: No Duplicate Processing
**File:** `domains/daily_digest/db_repo.py`
**Location:** `get_unclassified_articles()`

| Field | Value |
|-------|-------|
| Test Name | daily_digest_no_duplicate_classification |
| Input | Already classified articles (category is NOT NULL) |
| Expected | Should NOT be returned by `get_unclassified_articles()` |

**Test Steps:**
1. Insert article with `category="AI & LLMs"` (already classified)
2. Call `get_unclassified_articles()`
3. Verify the article is NOT in the result

---

## 3. Breaking News Source Count Tests

### Test 3.1: Source Count for New Story
**File:** `domains/breaking_news/processor.py`
**Location:** Lines 188-202

| Field | Value |
|-------|-------|
| Test Name | breaking_news_source_count_new_story |
| Input | New breaking event creating a new story |
| Expected | Story should have correct `source_count` based on distinct platforms |

**Test Steps:**
1. Clear test data
2. Process 2 breaking streams from different platforms (e.g., "Twitter", "Reuters")
3. Create new story
4. Verify `get_story_source_count()` returns 2 (distinct platforms)

**SQL Logic Verification:**
```sql
-- Should count DISTINCT source_platform
SELECT COUNT(DISTINCT r.source_platform)
FROM breaking_events e
JOIN event_stream_mapping m ON m.event_id = e.id
JOIN breaking_stream_raw r ON r.id = m.stream_id
WHERE e.story_id = %s
```

---

### Test 3.2: Source Count Aggregation
**File:** `domains/breaking_news/db_repo.py`
**Location:** `update_story()`, `update_story_verification()`

| Field | Value |
|-------|-------|
| Test Name | breaking_news_source_count_verification_status |
| Input | Story with different source counts |
| Expected | Verification status should update correctly |

**Test Table:**

| source_count | Expected Status |
|--------------|-----------------|
| 0 | "developing" |
| 1 | "developing" |
| 2 | "verified" |
| 5 | "verified" |

**Test Steps:**
1. Create story with `source_count = 1`
2. Call `update_story_verification()`
3. Verify status is "developing"
4. Update to `source_count = 2`
5. Call `update_story_verification()`
6. Verify status is "verified"

---

### Test 3.3: Source Count After Event Link
**File:** `domains/breaking_news/processor.py`
**Location:** Line 193-196

| Field | Value |
|-------|-------|
| Test Name | breaking_news_event_link_source_count |
| Input | Event linked to existing story |
| Expected | Story source_count should update when new event linked |

**Test Steps:**
1. Create story with existing event (source_count = 1 from platform A)
2. Process new breaking stream from platform B
3. Link new event to existing story
4. Call `get_story_source_count()`
5. Verify returns 2 (platforms A and B)

---

## Test Execution Order

1. **Unit Tests** (Mock-based, no DB required)
   - Test 1.1: Dead code removal
   - Test 1.2: Threshold logic correction

2. **Integration Tests** (Requires DB)
   - Test 2.1: Status update after classification
   - Test 2.2: RAG upload failure handling
   - Test 2.3: No duplicate classification
   - Test 3.1: Source count for new story
   - Test 3.2: Source count verification status
   - Test 3.3: Event link source count

3. **End-to-End Tests**
   - Full pipeline from RSS fetch → classification → daily summary

---

## Mock Fixtures Needed

```python
# Mock fixtures for testing
@pytest.fixture
def mock_db():
    """Mock database manager"""
    pass

@pytest.fixture
def mock_llm():
    """Mock LLM manager returning classification results"""
    pass

@pytest.fixture
def mock_rag():
    """Mock RAG client"""
    pass

@pytest.fixture
def sample_articles():
    """Sample articles for testing"""
    return [
        {
            "id": "test-1",
            "title": "AI Model Release",
            "content": "OpenAI releases new model...",
            "category": None,
            "score": None,
            "status": None
        }
    ]
```
