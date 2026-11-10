"""Run one self-test component in its own isolated process."""
import json
import sys


def main():
    if sys.argv[1:] == ['panel']:
        from runtime.selftest_support.panel import run_panel_check
        checks = [run_panel_check()]
    elif sys.argv[1:] == ['visca']:
        from runtime.selftest_support.visca import run_checks
        checks = run_checks()
    else:
        raise ValueError('Unknown self-test component')
    print(json.dumps(checks))


if __name__ == '__main__':
    main()
