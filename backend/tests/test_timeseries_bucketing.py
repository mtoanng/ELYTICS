from datetime import datetime, timedelta, timezone

import pytest

from backend.services.timeseries import compute_bucket_seconds


@pytest.mark.parametrize(
    "window,target_points,expected_bucket",
    [
        (timedelta(minutes=10), 600, 1),
        (timedelta(minutes=50), 600, 5),
        (timedelta(hours=20), 1200, 60),
        (timedelta(hours=100), 1200, 300),
        (timedelta(days=50), 1200, 3600),
        (timedelta(days=1200), 1200, 86400),
    ],
)
def test_compute_bucket_seconds_uses_nearest_standard_buckets(window, target_points, expected_bucket):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + window
    assert compute_bucket_seconds(start, end, target_points) == expected_bucket


def test_compute_bucket_seconds_prefers_larger_bucket_on_tie():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(seconds=300)
    # 300/100 -> raw bucket 3s, equidistant from 1s and 5s. Pick 5s.
    assert compute_bucket_seconds(start, end, 100) == 5


@pytest.mark.parametrize(
    "window,target_points,error_message",
    [
        (timedelta(minutes=5), 99, "target_points"),
        (timedelta(minutes=5), 5001, "target_points"),
        (timedelta(minutes=0), 100, "start must be before end"),
    ],
)
def test_compute_bucket_seconds_validates_inputs(window, target_points, error_message):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + window
    with pytest.raises(ValueError, match=error_message):
        compute_bucket_seconds(start, end, target_points)
