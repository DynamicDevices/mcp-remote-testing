"""
Change Tracking and Reversion for Remote Devices

Tracks changes made to devices for debugging purposes and enables reverting them.

Copyright (C) 2025 Dynamic Devices Ltd
License: GPL-3.0-or-later
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from lab_testing.config import CACHE_DIR
from lab_testing.utils.logger import get_logger

logger = get_logger()

# Change log file location
CHANGES_DIR = CACHE_DIR / "changes"
CHANGES_DIR.mkdir(parents=True, exist_ok=True)


class ChangeTracker:
    """Tracks changes made to devices"""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.changes_file = CHANGES_DIR / f"{device_id}_changes.json"
        self.changes: List[Dict[str, Any]] = []
        self._load_changes()

    def _load_changes(self):
        """Load existing changes from file"""
        if self.changes_file.exists():
            try:
                with self.changes_file.open("r") as f:
                    data = json.load(f)
                    self.changes = data.get("changes", [])
            except Exception as e:
                logger.warning(f"Failed to load changes for {self.device_id}: {e}")
                self.changes = []

    def _save_changes(self):
        """Save changes to file"""
        try:
            data = {
                "device_id": self.device_id,
                "last_updated": datetime.utcnow().isoformat(),
                "changes": self.changes
            }
            with self.changes_file.open("w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save changes for {self.device_id}: {e}")

    def record_change(
        self,
        change_type: str,
        description: str,
        command: Optional[str] = None,
        files_modified: Optional[List[str]] = None,
        revert_command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a change made to the device.
        
        Args:
            change_type: Type of change (ssh_command, file_edit, package_install, config_change, etc.)
            description: Human-readable description
            command: Command that was executed
            files_modified: List of files that were modified
            revert_command: Command to revert this change (if available)
            metadata: Additional metadata
            
        Returns:
            Change ID
        """
        change_id = f"{int(time.time())}_{len(self.changes)}"
        change = {
            "id": change_id,
            "timestamp": datetime.utcnow().isoformat(),
            "type": change_type,
            "description": description,
            "command": command,
            "files_modified": files_modified or [],
            "revert_command": revert_command,
            "reverted": False,
            "metadata": metadata or {}
        }

        self.changes.append(change)
        self._save_changes()
        logger.info(f"Recorded change {change_id} for {self.device_id}: {description}")

        return change_id

    def get_changes(self, include_reverted: bool = False) -> List[Dict[str, Any]]:
        """Get all changes, optionally including reverted ones"""
        if include_reverted:
            return self.changes
        return [c for c in self.changes if not c.get("reverted", False)]

    def get_change(self, change_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific change by ID"""
        for change in self.changes:
            if change["id"] == change_id:
                return change
        return None

    def revert_change(self, change_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Revert a specific change.
        
        Args:
            change_id: ID of change to revert
            force: Force revert even if already reverted
            
        Returns:
            Result dictionary
        """
        change = self.get_change(change_id)
        if not change:
            return {"error": f"Change {change_id} not found"}

        if change.get("reverted") and not force:
            return {"error": f"Change {change_id} already reverted"}

        if not change.get("revert_command"):
            return {"error": f"Change {change_id} has no revert command"}

        # Mark as reverted (actual revert must be executed separately via SSH)
        change["reverted"] = True
        change["reverted_at"] = datetime.utcnow().isoformat()
        self._save_changes()

        return {
            "success": True,
            "change_id": change_id,
            "revert_command": change["revert_command"],
            "message": "Change marked for reversion. Execute revert_command to complete."
        }

    def revert_all(self) -> Dict[str, Any]:
        """Revert all non-reverted changes"""
        pending = [c for c in self.changes if not c.get("reverted", False)]
        revert_commands = []

        for change in reversed(pending):  # Revert in reverse order
            if change.get("revert_command"):
                revert_commands.append({
                    "change_id": change["id"],
                    "description": change["description"],
                    "revert_command": change["revert_command"]
                })
                change["reverted"] = True
                change["reverted_at"] = datetime.utcnow().isoformat()

        self._save_changes()

        return {
            "success": True,
            "reverted_count": len(revert_commands),
            "revert_commands": revert_commands,
            "message": f"Marked {len(revert_commands)} changes for reversion"
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of changes"""
        total = len(self.changes)
        reverted = sum(1 for c in self.changes if c.get("reverted", False))
        pending = total - reverted

        return {
            "device_id": self.device_id,
            "total_changes": total,
            "reverted": reverted,
            "pending": pending,
            "last_change": self.changes[-1] if self.changes else None
        }


def get_tracker(device_id: str) -> ChangeTracker:
    """Get or create a change tracker for a device"""
    return ChangeTracker(device_id)


def record_ssh_command(device_id: str, command: str, description: Optional[str] = None) -> str:
    """
    Record an SSH command execution.
    
    Args:
        device_id: Device identifier
        command: Command that was executed
        description: Optional description
        
    Returns:
        Change ID
    """
    tracker = get_tracker(device_id)
    desc = description or f"SSH command: {command[:50]}"
    return tracker.record_change(
        change_type="ssh_command",
        description=desc,
        command=command,
        metadata={"command_length": len(command)}
    )


def record_file_backup(device_id: str, file_path: str, backup_path: str) -> str:
    """
    Record a file backup (for later restoration).
    
    Args:
        device_id: Device identifier
        file_path: Original file path
        backup_path: Backup file path
        
    Returns:
        Change ID
    """
    tracker = get_tracker(device_id)
    return tracker.record_change(
        change_type="file_backup",
        description=f"Backed up {file_path} to {backup_path}",
        files_modified=[file_path],
        revert_command=f"cp {backup_path} {file_path}",
        metadata={"original_file": file_path, "backup_file": backup_path}
    )

