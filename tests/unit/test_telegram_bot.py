import pytest

telegram = pytest.importorskip("telegram")
import telegram_bot


@pytest.mark.unit
def test_rate_limiting_blocks_after_threshold(monkeypatch):
    telegram_bot.USER_REQUESTS.clear()

    times = iter([0, 1, 2, 3])
    monkeypatch.setattr(telegram_bot.time, "time", lambda: next(times))

    user_id = 123
    assert telegram_bot.is_rate_limited(user_id) is False
    assert telegram_bot.is_rate_limited(user_id) is False
    assert telegram_bot.is_rate_limited(user_id) is False
    assert telegram_bot.is_rate_limited(user_id) is True
