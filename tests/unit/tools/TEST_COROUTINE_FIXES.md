# Coroutine Fix Test Documentation

This document describes the comprehensive test suites created to demonstrate and validate fixes for coroutine/async issues in the Odoo Intelligence MCP tools.

## Overview

Three main tools have coroutine-related issues that need to be fixed:
1. `execute_code` - Code execution in Odoo environment
2. `permission_checker` - Security and access rights checking
3. `view_model_usage` - View and field usage analysis

## Test Files Created

### 1. test_execute_code_fix.py

Tests for fixing coroutine issues in `execute_code`:

#### Key Test Cases:
- **test_execute_code_handles_search_count_in_arithmetic**: Tests arithmetic operations on `search_count()` results
  - Currently fails with "unsupported operand type(s) for +: 'coroutine' and 'coroutine'"
  - Should await coroutines and perform calculations on the integer results

- **test_execute_code_handles_browse_attribute_access**: Tests accessing attributes on `browse()` results
  - Currently may fail when browse returns a coroutine
  - Should await the coroutine and access attributes on the actual record

- **test_execute_code_handles_search_and_iteration**: Tests iterating over `search()` results
  - Currently fails with "coroutine object is not iterable"
  - Should await the search and iterate over the recordset

- **test_execute_code_handles_mixed_async_operations**: Complex scenario with multiple async calls
  - Tests combinations of search_count, search, browse, and attribute access
  - Validates that all async operations are properly awaited

- **test_execute_code_handles_create_and_write**: Tests record creation and modification
  - Ensures create() and write() operations work without coroutine errors

- **test_execute_code_handles_domain_operations**: Tests complex domain calculations
  - Multiple search_count calls with arithmetic operations
  - Percentage calculations and conditional logic

### 2. test_permission_checker_fix.py

Tests for fixing coroutine issues in `permission_checker`:

#### Key Test Cases:
- **test_permission_checker_handles_user_search**: Tests user lookup via `search()`
  - Currently fails with "coroutine object has no attribute 'id'"
  - Should await the search and access user attributes

- **test_permission_checker_handles_user_browse_by_id**: Tests user lookup by ID using `browse()`
  - Tests the fallback mechanism when search by login fails
  - Should properly await browse operations

- **test_permission_checker_handles_record_access_check**: Tests specific record permission checking
  - Uses browse() to get a specific record
  - Should await and check access on the actual record object

- **test_permission_checker_handles_model_access_rules**: Tests complex access rule analysis
  - Multiple groups with different permissions
  - Should aggregate permissions correctly

- **test_permission_checker_handles_record_rules**: Tests row-level security analysis
  - Domain-based record rules
  - Global vs group-specific rules

- **test_permission_checker_complex_scenario**: Real-world scenario with multiple permission layers
  - Project manager with multiple groups
  - Model access + record rules + specific record check

### 3. test_view_model_usage_fix.py

Tests for fixing coroutine issues in `view_model_usage`:

#### Key Test Cases:
- **test_view_model_usage_handles_view_search**: Tests view search returning coroutines
  - Currently fails when trying to iterate over coroutine
  - Should await the search and iterate over view records

- **test_view_model_usage_handles_empty_search_results**: Tests empty view results
  - Should handle empty async search results gracefully

- **test_view_model_usage_complex_view_parsing**: Tests complex view structures
  - Nested XML, multiple field types, buttons, and actions
  - Should parse all elements correctly after awaiting

- **test_view_model_usage_multiple_view_types**: Tests various view types
  - Form, tree, search, kanban, graph views
  - Should handle all view types and count field usage

- **test_view_model_usage_with_inheritance**: Tests inherited views
  - Base views and inheritance via xpath
  - Should detect fields from all view layers

- **test_view_model_usage_with_computed_fields**: Tests computed and related fields
  - Should detect fields even if they're computed or invisible

## Common Issues and Expected Fixes

### Issue 1: Unawaited Coroutines
**Problem**: Methods like `search()`, `search_count()`, `browse()` return coroutines that aren't awaited
**Fix**: Add `await` before these async method calls

### Issue 2: Attribute Access on Coroutines
**Problem**: Trying to access `.id`, `.name`, etc. on coroutine objects
**Fix**: Await the coroutine first, then access attributes on the result

### Issue 3: Iteration over Coroutines
**Problem**: `for record in env['model'].search([])` fails because coroutine isn't iterable
**Fix**: `for record in await env['model'].search([])`

### Issue 4: Arithmetic on Coroutines
**Problem**: `count1 + count2` fails when both are coroutines from `search_count()`
**Fix**: `(await count1) + (await count2)` or await both first

## Running the Tests

To run these specific test files:

```bash
# Run all coroutine fix tests
pytest tests/unit/tools/code/test_execute_code_fix.py -v
pytest tests/unit/tools/model/test_view_model_usage_fix.py -v
pytest tests/unit/tools/security/test_permission_checker_fix.py -v

# Run all together
pytest tests/unit/tools/*/test_*_fix.py -v
```

## Implementation Notes

The fixes should:
1. Identify all async method calls in the code
2. Add proper `await` statements
3. Handle exceptions from async operations
4. Maintain backward compatibility with mock environments (for testing)
5. Ensure the functions remain `async def` if they use await

## Success Criteria

All tests should pass, demonstrating that:
- Coroutines are properly awaited before use
- Arithmetic operations work on numeric results, not coroutines
- Attribute access works on actual objects, not coroutines
- Iteration works over actual collections, not coroutines
- Error handling remains robust with async operations