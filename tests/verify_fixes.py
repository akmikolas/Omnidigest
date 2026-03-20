#!/usr/bin/env python3
"""
Verification script for the bug fixes.
Run this to verify that the fixes have been applied correctly.
"""
import sys
import os

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

def verify_fix_1():
    """Verify: Status update after LLM classification"""
    print("\n=== Fix 1: Status Update After Classification ===")

    # Check if update_classification sets status = 1
    with open('domains/daily_digest/db_repo.py', 'r') as f:
        content = f.read()

    if 'status = 1' in content and 'UPDATE news_articles' in content:
        # More specific check
        if 'SET category = %s, score = %s, summary_raw = %s, status = 1' in content:
            print("✅ PASS: update_classification now sets status = 1")
            return True
        else:
            print("❌ FAIL: status = 1 not found in UPDATE query")
            return False
    else:
        print("❌ FAIL: Expected code pattern not found")
        return False


def verify_fix_2():
    """Verify: Twitter threshold logic correction"""
    print("\n=== Fix 2: Twitter Threshold Logic ===")

    with open('domains/twitter/processor.py', 'r') as f:
        content = f.read()

    # Check for correct pattern: threshold == 1
    # Check for incorrect pattern: 1 >= threshold
    incorrect_pattern = 'if 1 >= threshold:'
    correct_pattern = 'if threshold == 1:'

    has_incorrect = incorrect_pattern in content
    has_correct = correct_pattern in content

    if has_incorrect:
        print(f"❌ FAIL: Found incorrect pattern '{incorrect_pattern}'")
        return False
    elif has_correct:
        print("✅ PASS: Threshold logic corrected to 'if threshold == 1:'")
        return True
    else:
        print("⚠️  WARNING: Could not verify threshold logic")
        return False


def verify_fix_3():
    """Verify: Breaking news source_count uses source_url"""
    print("\n=== Fix 3: Breaking News Source Count ===")

    with open('domains/breaking_news/db_repo.py', 'r') as f:
        content = f.read()

    # Find the get_story_source_count function
    if 'COUNT(DISTINCT r.source_url) as cnt' in content:
        print("✅ PASS: source_count now uses DISTINCT source_url")
        return True
    elif 'COUNT(DISTINCT r.source_platform) as cnt' in content:
        print("❌ FAIL: source_count still uses source_platform")
        return False
    else:
        print("⚠️  WARNING: Could not verify source_count logic")
        return False


def verify_fix_4():
    """Verify: RAG upload failure handling"""
    print("\n=== Fix 4: RAG Upload Failure Handling ===")

    with open('domains/ingestion/rss/standard_crawler.py', 'r') as f:
        content = f.read()

    # Look for the specific fix pattern:
    # We need "else:" after "if doc_id:" to handle the failure case

    # Check if there's proper handling by looking for the pattern:
    # "if doc_id:" followed by "else:" within a reasonable distance

    import re

    # Find the relevant block
    match = re.search(r'if doc_id:.*?self\.db\.update_status.*?else:.*?self\.db\.update_status', content, re.DOTALL)

    if match:
        print("✅ PASS: RAG upload failure is handled properly")
        return True
    else:
        # Check if there's at least an else for doc_id
        # Look for "if doc_id:" followed by "else:" anywhere in the rag block
        rag_match = re.search(r'if settings\.ragflow_enabled:.*?(?=if settings|\Z)', content, re.DOTALL)
        if rag_match:
            rag_block = rag_match.group(0)
            if 'if doc_id:' in rag_block and 'else:' in rag_block:
                # Verify the else is for doc_id, not for ragflow_enabled
                # The else should appear after "if doc_id:" in the block
                doc_id_pos = rag_block.find('if doc_id:')
                else_pos = rag_block.find('else:', doc_id_pos)
                if else_pos > doc_id_pos:
                    print("✅ PASS: RAG upload failure is handled properly")
                    return True

        print("❌ FAIL: RAG upload failure NOT handled")
        print("   When ragflow_enabled=True but doc_id=None,")
        print("   article is NOT marked as processed (status stays 0)")
        return False


def main():
    print("=" * 60)
    print("Bug Fix Verification Script")
    print("=" * 60)

    # Change to backend/src directory
    os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

    results = []

    results.append(verify_fix_1())
    results.append(verify_fix_2())
    results.append(verify_fix_3())
    results.append(verify_fix_4())

    print("\n" + "=" * 60)
    print(f"Summary: {sum(results)}/{len(results)} fixes verified")
    print("=" * 60)

    if all(results):
        print("\n✅ All fixes verified successfully!")
        return 0
    else:
        print("\n❌ Some fixes are missing or incorrect!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
