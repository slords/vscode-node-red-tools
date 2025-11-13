"""
Info Plugin

Handles info field extraction to .md files for all nodes.
This plugin runs on all nodes that have an info field.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional


class InfoPlugin:
    """Plugin for handling info field extraction to .md files"""

    def get_name(self) -> str:
        return "info"

    def get_priority(self) -> Optional[int]:
        return None  # Use filename prefix (250)

    def get_plugin_type(self) -> str:
        return "explode"

    def can_handle_node(self, node: Dict[str, Any]) -> bool:
        """Check if this node has an info field (even if empty in skeleton)"""
        return "info" in node

    def get_claimed_fields(self, node: Dict[str, Any]) -> List[str]:
        """Claim the info field"""
        return ["info"]

    def explode_node(self, node: Dict[str, Any], node_dir: Path) -> List[str]:
        """Extract info field to .md file

        Returns:
            List of created filenames
        """
        try:
            node_id: str = node.get("id")
            info_content: str = node.get("info", "")
            created_files: List[str] = []

            if info_content:
                md_file: Path = node_dir / f"{node_id}.md"
                md_file.write_text(info_content)
                created_files.append(f"{node_id}.md")

            return created_files

        except Exception as e:
            print(f"⚠ Warning: info plugin failed for {node.get('id', 'unknown')}: {e}")
            return []

    def rebuild_node(
        self, node_id: str, node_dir: Path, skeleton: Dict[str, Any]
    ) -> Dict[str, str]:
        """Rebuild info from .md file"""
        data: Dict[str, str] = {}

        md_file: Path = node_dir / f"{node_id}.md"
        if md_file.exists():
            data["info"] = md_file.read_text()
        elif skeleton and "info" in skeleton:
            # Skeleton has info field - preserve position with empty string
            data["info"] = ""

        return data
