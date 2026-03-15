"""
Script wrapper around the tracker worker.

Example usage in cron:
    */15 * * * * /path/to/venv/bin/python -m scripts.run_tracker_once
"""

from app.workers.tracker import main

if __name__ == "__main__":
    main()
