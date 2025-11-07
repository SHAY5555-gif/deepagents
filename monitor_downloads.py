#!/usr/bin/env python3
"""Monitor download progress"""

import os
from pathlib import Path
import time

DOWNLOAD_DIR = Path("downloads/koach_course_1025")

def format_size(bytes_size):
    """Format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def get_download_stats():
    """Get current download statistics"""
    if not DOWNLOAD_DIR.exists():
        return {"completed": 0, "in_progress": 0, "total_size": 0, "files": []}

    completed = list(DOWNLOAD_DIR.glob("*.mp4"))
    in_progress = list(DOWNLOAD_DIR.glob("*.mp4.part"))

    files_info = []
    total_size = 0

    for f in completed:
        size = f.stat().st_size
        total_size += size
        files_info.append({
            "name": f.name,
            "size": format_size(size),
            "status": "DONE"
        })

    for f in in_progress:
        size = f.stat().st_size
        total_size += size
        files_info.append({
            "name": f.name.replace(".part", ""),
            "size": format_size(size),
            "status": "DOWNLOADING"
        })

    return {
        "completed": len(completed),
        "in_progress": len(in_progress),
        "total_size": format_size(total_size),
        "files": files_info
    }

# Print current stats
stats = get_download_stats()
print(f"\n{'='*70}")
print(f"Download Progress Monitor")
print(f"{'='*70}")
print(f"Completed: {stats['completed']}")
print(f"In Progress: {stats['in_progress']}")
print(f"Total Downloaded: {stats['total_size']}")
print(f"{'='*70}\n")

print("Files:")
for f in stats['files']:
    status_marker = "[OK]" if f['status'] == "DONE" else "[...]"
    print(f"  {status_marker} {f['name']:<50} {f['size']:>10}")

print(f"\n{'='*70}")
