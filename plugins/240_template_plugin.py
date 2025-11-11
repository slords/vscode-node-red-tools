"""
Template Plugin

Handles template extraction from various Node-RED template nodes:
- ui_template (Dashboard 2) - Vue components
- ui-template (Dashboard 1) - Angular templates
- template (core) - Mustache/HTML/JSON/YAML/etc templates

Extracts template content to appropriately named files for IDE support.
"""

from pathlib import Path
from typing import Optional


# Format to extension mapping for core template node
FORMAT_EXTENSIONS = {
    "handlebars": ".mustache",
    "html": ".html",
    "json": ".json",
    "yaml": ".yaml",
    "javascript": ".js",
    "css": ".css",
    "markdown": ".md",
    "python": ".py",
    "sql": ".sql",
    "c_cpp": ".cpp",
    "java": ".java",
    "text": ".txt",
}


class TemplatePlugin:
    """Plugin for handling template field extraction to files with appropriate extensions"""

    def get_name(self) -> str:
        return "template"

    def get_priority(self):
        return None  # Use filename prefix (240)

    def get_plugin_type(self) -> str:
        return "explode"

    def can_handle_node(self, node: dict) -> bool:
        """Check if this node has a template field"""
        node_type = node.get("type", "")
        # Handle ui_template, ui-template, or template nodes with template field
        return node_type in ["ui_template", "ui-template", "template"] and "template" in node

    def get_claimed_fields(self, node: dict):
        """Claim the template field"""
        return ["template"]

    def is_metadata_file(self, filename: str) -> bool:
        """Check if filename is a metadata file (not a primary node definition)"""
        # Template files are identifiable by their patterns
        return (
            filename.endswith(".vue")
            or filename.endswith(".ui-template.html")
            or ".template." in filename
        )

    def can_infer_node_type(self, node_dir: Path, node_id: str) -> Optional[str]:
        """Infer node type from files, returns None if can't infer"""
        # Check for Dashboard 2 (Vue)
        if (node_dir / f"{node_id}.vue").exists():
            return "ui_template"

        # Check for Dashboard 1 (Angular)
        if (node_dir / f"{node_id}.ui-template.html").exists():
            return "ui-template"

        # Check for core template node (has .template. in filename)
        for file in node_dir.glob(f"{node_id}.template.*"):
            return "template"

        return None

    def _get_template_extension(self, node: dict) -> str:
        """Determine appropriate file extension based on node type and format"""
        node_type = node.get("type", "")

        if node_type == "ui_template":
            # Dashboard 2 - Vue components
            return ".vue"
        elif node_type == "ui-template":
            # Dashboard 1 - Angular templates
            return ".ui-template.html"
        elif node_type == "template":
            # Core template node - use format field
            format_type = node.get("format", "handlebars")
            ext = FORMAT_EXTENSIONS.get(format_type, ".txt")
            return f".template{ext}"
        else:
            # Unknown template type - use generic
            return ".template.txt"

    def explode_node(self, node: dict, node_dir: Path, repo_root: Path) -> list:
        """Extract template field to appropriate file

        Returns:
            List of created filenames
        """
        try:
            node_id = node.get("id")
            template_content = node.get("template", "")
            created_files = []

            if template_content:
                extension = self._get_template_extension(node)
                template_file = node_dir / f"{node_id}{extension}"
                template_file.write_text(template_content)
                created_files.append(f"{node_id}{extension}")

            return created_files

        except Exception as e:
            print(f"⚠ Warning: template plugin failed for {node.get('id', 'unknown')}: {e}")
            return []

    def rebuild_node(
        self, node_id: str, node_dir: Path, skeleton: dict, repo_root: Path
    ) -> dict:
        """Rebuild template from file"""
        data = {}

        # Try to find template file by checking known patterns
        template_file = None

        # Check for Dashboard 2 (Vue)
        vue_file = node_dir / f"{node_id}.vue"
        if vue_file.exists():
            template_file = vue_file

        # Check for Dashboard 1 (Angular)
        if not template_file:
            ui_template_file = node_dir / f"{node_id}.ui-template.html"
            if ui_template_file.exists():
                template_file = ui_template_file

        # Check for core template node (any .template.* file)
        if not template_file:
            template_files = list(node_dir.glob(f"{node_id}.template.*"))
            if template_files:
                template_file = template_files[0]

        # Read template content if found
        if template_file and template_file.exists():
            data["template"] = template_file.read_text()
        elif skeleton and "template" in skeleton:
            # Skeleton has template field - preserve position with empty string
            data["template"] = ""

        return data
