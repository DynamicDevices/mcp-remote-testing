# MCP Server Roadmap

## Quick Wins (Implement First)

### 1. Structured Logging
**Impact**: High | **Effort**: Low | **Time**: 2-3 hours

Add logging to all tools for debugging and monitoring.

**Implementation**:
- Create `lab_testing/utils/logger.py`
- Configure logging with file and console handlers
- Add request ID tracking
- Replace print statements with logger calls

**Example**:
```python
# utils/logger.py
import logging
from pathlib import Path

def setup_logger(name: str = "lab_testing") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # File handler
    log_dir = Path.home() / ".cache" / "ai-lab-testing" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "server.log")
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
```

### 2. Async Batch Operations
**Impact**: Very High | **Effort**: Medium | **Time**: 4-6 hours

Parallelize batch operations for much faster regression testing.

**Implementation**:
- Convert batch operations to async
- Use `asyncio.gather()` with semaphore for concurrency control
- Add progress tracking

**Example**:
```python
async def batch_operation_async(
    device_ids: List[str],
    operation: str,
    max_concurrent: int = 5,
    **kwargs
) -> Dict[str, Any]:
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_op(device_id: str):
        async with semaphore:
            # Run operation...
            return device_id, result
    
    tasks = [run_op(did) for did in device_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Process results...
```

### 3. Connection Pooling
**Impact**: High | **Effort**: Medium | **Time**: 6-8 hours

Reuse SSH connections for faster execution.

**Implementation**:
- Create `lab_testing/utils/ssh_pool.py`
- Maintain connection pool per device
- Auto-reconnect on failure
- Connection health checks

### 4. Health Check Resource
**Impact**: Medium | **Effort**: Low | **Time**: 1-2 hours

Add `health://status` resource for monitoring.

**Implementation**:
- Track server uptime, tool call counts
- Check VPN connectivity
- Check device config validity
- Return JSON status

### 5. Enhanced Error Types
**Impact**: Medium | **Effort**: Low | **Time**: 2-3 hours

Custom exceptions for better error handling.

**Implementation**:
- Create `lab_testing/exceptions.py`
- Define exception hierarchy
- Add retry logic for transient errors

## Medium-Term Improvements

### 6. Unit Test Suite
**Impact**: High | **Effort**: High | **Time**: 8-12 hours

Comprehensive test coverage.

**Implementation**:
- Create `tests/` directory
- Mock SSH, VPN, power monitoring
- Test each tool module
- Integration tests

### 7. Device State Caching
**Impact**: Medium | **Effort**: Medium | **Time**: 3-4 hours

Cache device status to reduce load.

**Implementation**:
- In-memory cache with TTL
- Cache invalidation on updates
- Configurable TTL per data type

### 8. Progress Tracking
**Impact**: Medium | **Effort**: Medium | **Time**: 4-6 hours

Track progress of long-running operations.

**Implementation**:
- Operation ID generation
- Progress storage (in-memory or file)
- `status://<operation_id>` resource
- Progress callbacks

## Recommended Implementation Order

**Week 1**:
1. Structured Logging (2-3h)
2. Health Check Resource (1-2h)
3. Enhanced Error Types (2-3h)

**Week 2**:
4. Async Batch Operations (4-6h)
5. Basic Unit Tests (4-6h)

**Week 3**:
6. Connection Pooling (6-8h)
7. Device State Caching (3-4h)

**Week 4**:
8. Progress Tracking (4-6h)
9. More Unit Tests (4-6h)

## Success Metrics

- **Performance**: Batch operations 5-10x faster with async
- **Reliability**: 99%+ success rate with connection pooling
- **Debugging**: <5min to diagnose issues with logging
- **Testing**: 80%+ code coverage
- **User Experience**: Progress feedback for all long operations

