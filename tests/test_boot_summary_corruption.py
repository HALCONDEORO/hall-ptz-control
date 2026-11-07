"""A damaged history entry must not break splash statistics."""
import json

import pytest

from application.boot_metrics import BootStatistics


@pytest.mark.parametrize('bad', [None, [], 'bad', 4,
                               {'duration_ms': None}, {'duration_ms': 'slow'},
                               {'duration_ms': []}, {'duration_ms': {}},
                               {'duration_ms': float('inf')},
                               {'duration_ms': float('-inf')},
                               {'duration_ms': float('nan')},
                               {'duration_ms': -1}, {'duration_ms': True}])
def test_summary_skips_bad_entry_and_retains_valid_boot(tmp_path, bad):
    path = tmp_path / 'boot_stats.json'
    good = {'duration_ms': 1250, 'success': True, 'timestamp': '2026-11-07T09:00:00'}
    path.write_text(json.dumps([good, bad]))
    assert BootStatistics(path).get_summary() == {
        'total_boots': 1, 'successful': 1, 'success_rate': '100.0%',
        'avg_duration_ms': 1250, 'last_boot': good['timestamp'],
    }


@pytest.mark.parametrize('durations', [[1e308, 1e308], [10**400, 10**400 + 2]])
def test_summary_average_does_not_overflow_on_finite_values(tmp_path, durations):
    from fractions import Fraction
    path = tmp_path / 'boot_stats.json'
    path.write_text(json.dumps([{'duration_ms': value} for value in durations]))
    expected = int(sum(Fraction(value) for value in durations) / len(durations))
    assert BootStatistics(path).get_summary()['avg_duration_ms'] == expected
