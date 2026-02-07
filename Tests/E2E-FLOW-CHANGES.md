# E2E Testing Flow Changes

## Summary

The end-to-end testing flow has been updated to prompt the user BEFORE each test (instead of after) and track detailed test status.

## Key Changes

### 1. Prompt Timing
- **Before**: Prompt appeared AFTER test completed
- **After**: Prompt appears BEFORE test runs

### 2. User Options
- **Before**: Y/S/N (Yes/Skip use case/No)
  - Y = Continue to next test
  - S = Skip remaining tests in use case
  - N = Stop and exit
- **After**: Y/S/Q (Yes/Skip/Quit)
  - Y = Run this test
  - S = Skip this test, proceed to next
  - Q = Quit and save progress

### 3. Test Status
- **Before**: Tests tracked as 'passed' or 'failed'
- **After**: Tests tracked as 'succeeded', 'failed', or 'skipped'
  - **succeeded** = Test ran and passed
  - **failed** = Test ran but failed
  - **skipped** = User chose to skip the test

### 4. Previous Status Display
- **Before**: No display of previous test status
- **After**: When resuming, shows previous status before prompting:
  ```
  Previous run: ✅ SUCCEEDED
  Previous run: ❌ FAILED
  Previous run: ⏭ SKIPPED
  ```

### 5. Skip Behavior
- **Before**: S skipped all remaining tests in the use case
- **After**: S skips only the current test, continues to next test

### 6. State Structure
- **Before**:
  ```json
  {
    "completed_tests": [
      {"use_case": "...", "url_index": 0, "status": "passed"}
    ],
    "skipped_use_cases": ["playlist_audio_only"]
  }
  ```
- **After**:
  ```json
  {
    "test_results": [
      {"use_case": "...", "url_index": 0, "status": "succeeded"},
      {"use_case": "...", "url_index": 1, "status": "failed"},
      {"use_case": "...", "url_index": 2, "status": "skipped"}
    ]
  }
  ```

## Benefits

1. **Better control**: User decides whether to run each test individually
2. **Previous status visible**: See what happened in previous runs
3. **Re-run capability**: Can re-run failed tests by choosing Y when resuming
4. **Clearer status**: Three distinct states (succeeded/failed/skipped)
5. **Simpler logic**: No "skip use case" concept, just individual test decisions

## Example Workflows

### First Run

```
[1/2] URL: https://youtu.be/xxxxx
Args: []
Timeout: 120s
------------------------------------------------------------

What do you want to do?
  [Y] Yes - Run this test
  [S] Skip - Skip this test, proceed to next
  [Q] Quit - Save progress and exit

Your choice (Y/S/Q): Y

▶️  Running test...
[test runs...]
✅ TEST PASSED (45.3s)
💾 Status saved: succeeded
```

### Resume After Failure

```
[1/2] URL: https://youtu.be/xxxxx
Args: []
Timeout: 120s
------------------------------------------------------------
Previous run: ❌ FAILED

What do you want to do?
  [Y] Yes - Run this test
  [S] Skip - Skip this test, proceed to next
  [Q] Quit - Save progress and exit

Your choice (Y/S/Q): Y

▶️  Running test...
[test runs again...]
✅ TEST PASSED (42.1s)
💾 Status saved: succeeded
```

### Skip Test

```
[2/2] URL: https://youtu.be/yyyyy
Args: []
Timeout: 120s
------------------------------------------------------------

What do you want to do?
  [Y] Yes - Run this test
  [S] Skip - Skip this test, proceed to next
  [Q] Quit - Save progress and exit

Your choice (Y/S/Q): S

⏭ Skipping this test...
[proceeds to next use case]
```

## Migration Notes

- Old state files will not work with new version (different structure)
- Users should complete or abandon old test sessions before upgrading
- Documentation has been updated to reflect new flow

## Files Modified

1. `Tests/e2e_main.py` - Main test runner logic
2. `Docs/E2E-TESTING-GUIDE.md` - User guide updated
3. `Tests/README-E2E-TESTS.md` - Quick reference updated

## Files Created

1. `Tests/E2E-FLOW-CHANGES.md` - This document
