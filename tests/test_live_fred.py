from lemp_macro.live_fred import PRIORITY_SERIES


def test_priority_series_are_unique():
    ids = [item.series_id for item in PRIORITY_SERIES]
    assert len(ids) == len(set(ids))
    assert len(ids) == 10


def test_series_have_explanations():
    assert all(item.interpretation for item in PRIORITY_SERIES)
    assert all(item.category for item in PRIORITY_SERIES)
