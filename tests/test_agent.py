from agent.agent import Backoff, ResultCache


def test_result_cache_drops_the_oldest_when_full():
    """Simple test for our command cache ring buffer"""
    cache = ResultCache(size=2)
    cache.put("a", {"status": "SUCCEEDED"})
    cache.put("b", {"status": "SUCCEEDED"})
    cache.put("c", {"status": "FAILED"})

    assert cache.get("a") is None  # oldest evicted
    assert cache.get("b") == {"status": "SUCCEEDED"}
    assert cache.get("c") == {"status": "FAILED"}


def test_backoff_basic_mechanism_boundary():
    backoff = Backoff(base=1, cap=8)
    upper_limits = [1, 2, 4, 8, 8]

    for upper_limit in upper_limits:
        delay_s = backoff.next_delay()
        assert (
            delay_s < upper_limit
        )  # TODO: revisit due to possible issues of float comparison
