from agent.agent import ResultCache


def test_result_cache_drops_the_oldest_when_full():
    """Simple test for our command cache ring buffer"""
    cache = ResultCache(size=2)
    cache.put("a", {"status": "SUCCEEDED"})
    cache.put("b", {"status": "SUCCEEDED"})
    cache.put("c", {"status": "FAILED"})

    assert cache.get("a") is None  # oldest evicted
    assert cache.get("b") == {"status": "SUCCEEDED"}
    assert cache.get("c") == {"status": "FAILED"}
