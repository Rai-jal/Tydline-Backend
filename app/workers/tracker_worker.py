"""
Backwards-compatibility shim — module was renamed to app.workers.tracker.
Use:  python -m app.workers.tracker
"""

from app.workers.tracker import main, run_tracker_cycle  # noqa: F401

if __name__ == "__main__":
    main()
