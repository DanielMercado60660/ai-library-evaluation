# End-to-End Workflow Tests

This directory contains manual workflow tests that trace complete operations across all three services (Catalog, Circulation, ILL).

## Prerequisites

1. **All three services must be running:**

   ```bash
   # Option 1: Using Docker Compose (recommended)
   docker-compose up

   # Option 2: Run individually in separate terminals
   # Terminal 1:
   cd services/catalog && uvicorn catalog.main:app --port 8001

   # Terminal 2:
   cd services/circulation && uvicorn circulation.main:app --port 8002

   # Terminal 3:
   cd services/ill && uvicorn ill.main:app --port 8003
   ```

2. **Databases seeded:**

   ```bash
   # From project root
   python scripts/seed_all.py
   ```

## Test Scripts

### 1. Checkout Workflow (`test_checkout_workflow.py`)

Tests the complete checkout process:
- Patron searches catalog for a book
- Checks book availability
- Verifies patron in circulation system
- Creates checkout
- Verifies instance status updated

**Run:**
```bash
python test_checkout_workflow.py
```

**Expected flow:**
1. Find "The Burden of Lorde Tuskar" in catalog
2. Get available instance
3. Verify patron "Trunsworth Greyvale"
4. Create checkout
5. Confirm instance marked as checked out

---

### 2. ILL Borrowing Workflow (`test_ill_borrow_workflow.py`)

Tests requesting a book from another library:
- Verifies patron exists
- Checks book NOT in our catalog
- Creates ILL request
- Tracks request status

**Run:**
```bash
python test_ill_borrow_workflow.py
```

**Expected flow:**
1. Verify patron (Dr. Helena Caladent)
2. Confirm book not in our catalog
3. Create ILL request to university-library
4. Request created with status "requested"

---

### 3. ILL Lending Workflow (`test_ill_lend_workflow.py`)

Tests lending to another library:
- External library queries our holdings
- We have the book available
- External library requests loan
- We approve and create inbound loan

**Run:**
```bash
python test_ill_lend_workflow.py
```

**Expected flow:**
1. External library queries holdings (ISBN lookup)
2. We report book available
3. External library requests loan
4. We approve and reserve instance
5. Inbound loan created

---

### 4. Run All Tests (`run_all_tests.py`)

Runs all three workflow tests in sequence:

```bash
python run_all_tests.py
```

This will execute all workflows and provide a summary of results.

## Service URLs

By default, the tests connect to:
- **Catalog:** http://localhost:8001
- **Circulation:** http://localhost:8002
- **ILL:** http://localhost:8003

## Interpreting Results

Each test script provides detailed output showing:
- **Steps** being executed
- **API calls** being made
- **Responses** from services
- **Status** of each operation

Look for:
- ✅ Success indicators
- ❌ Error indicators
- ⚠️  Warning indicators

## Troubleshooting

### Services not running
```
Error: Cannot connect to service
```
**Solution:** Make sure all three services are running on ports 8001-8003

### Database not seeded
```
Error: Patron not found / Book not found
```
**Solution:** Run `python scripts/seed_all.py`

### Port conflicts
```
Error: Address already in use
```
**Solution:** Check if another service is using ports 8001-8003

## Next Steps

After all workflows pass:
1. Implement integration tests (automated versions)
2. Add more complex scenarios
3. Test error handling and edge cases
4. Measure response times and performance
