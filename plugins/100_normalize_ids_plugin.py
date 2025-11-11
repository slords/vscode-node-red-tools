"""
Normalize IDs Plugin

Pre-explode plugin that normalizes random Node-RED IDs to functional names.
"""

import re
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to lowercase slug format"""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "_", text)
    return text.strip("_")


def abbreviate_type(node_type: str) -> str:
    """Abbreviate common node types"""
    abbreviations = {
        "function": "func",
        "inject": "inject",
        "debug": "debug",
        "switch": "switch",
        "change": "change",
        "template": "tmpl",
        "http request": "http",
        "http in": "http_in",
        "http response": "http_out",
        "mqtt in": "mqtt_in",
        "mqtt out": "mqtt_out",
        "delay": "delay",
        "trigger": "trigger",
        "exec": "exec",
        "file": "file",
        "file in": "file_in",
        "tcp": "tcp",
        "udp": "udp",
        "websocket": "ws",
        "link in": "link_in",
        "link out": "link_out",
        "link call": "link_call",
        "comment": "comment",
        "subflow": "subflow",
        "tab": "tab",
    }

    if node_type in abbreviations:
        return abbreviations[node_type]

    for full, abbr in abbreviations.items():
        if node_type.startswith(full):
            return abbr

    return slugify(node_type)


def derive_name_from_function(func_code: str) -> str:
    """Derive a meaningful name from function code if no name is set"""
    if not func_code:
        return "unnamed"

    # Check if this is an action definition
    action_match = re.search(
        r'const\s+(actionDef|cmdDef)\s*=\s*\{[\s\S]*?name:\s*["\']([^"\']+)["\']',
        func_code,
    )
    if action_match:
        return action_match.group(2)

    lines = func_code.strip().split("\n")
    code_lines = [
        l.strip() for l in lines if l.strip() and not l.strip().startswith("//")
    ]

    if not code_lines:
        return "unnamed"

    first_line = code_lines[0]

    var_match = re.search(r"(?:var|let|const)\s+(\w+)", first_line)
    if var_match:
        return var_match.group(1)

    func_match = re.search(r"(\w+)\s*\(", first_line)
    if func_match:
        func_name = func_match.group(1)
        if func_name not in ["if", "for", "while", "switch", "return"]:
            return func_name

    msg_match = re.search(r"msg\.(\w+)\s*=", first_line)
    if msg_match:
        return f"set_{msg_match.group(1)}"

    return "unnamed"


def derive_node_name(node: dict) -> str:
    """Derive a meaningful name for a node"""
    if "name" in node and node["name"]:
        return slugify(node["name"])

    if node.get("type") == "function" and "func" in node:
        derived = derive_name_from_function(node["func"])
        if derived != "unnamed":
            return derived

    if node.get("type") == "inject":
        if "topic" in node and node["topic"]:
            return slugify(node["topic"])
        if "payload" in node:
            payload = str(node["payload"])
            if len(payload) < 20 and payload:
                return slugify(payload)

    if node.get("type") == "switch" and "property" in node:
        prop = node["property"].replace("msg.", "")
        return f"check_{slugify(prop)}"

    if node.get("type") == "change" and "rules" in node and node["rules"]:
        rule = node["rules"][0]
        if "to" in rule:
            return f"set_{slugify(str(rule['to']))[:20]}"

    return "unnamed"


def generate_new_id(node: dict, used_ids: set) -> str:
    """Generate a new functional ID for a node"""
    node_type = node.get("type", "unknown")

    if node_type == "tab":
        base_name = slugify(node.get("label", "flow"))
        prefix = "tab"
    elif node_type.startswith("subflow"):
        base_name = slugify(node.get("name", node.get("label", "subflow")))
        prefix = "subflow"
    else:
        type_abbr = abbreviate_type(node_type)
        name = derive_node_name(node)
        base_name = name
        prefix = type_abbr

    if base_name and base_name != "unnamed":
        new_id = f"{prefix}_{base_name}"
    else:
        new_id = prefix

    if new_id in used_ids:
        counter = 2
        while f"{new_id}_{counter}" in used_ids:
            counter += 1
        new_id = f"{new_id}_{counter}"

    used_ids.add(new_id)
    return new_id


def update_wires(nodes: list, id_map: dict):
    """Update all wire references with new IDs"""
    for node in nodes:
        if "wires" in node:
            for wire_array in node["wires"]:
                for i, wire_id in enumerate(wire_array):
                    if wire_id in id_map:
                        wire_array[i] = id_map[wire_id]

        if "z" in node and node["z"] in id_map:
            node["z"] = id_map[node["z"]]

        if "links" in node and isinstance(node["links"], list):
            for i, link_id in enumerate(node["links"]):
                if link_id in id_map:
                    node["links"][i] = id_map[link_id]

        if "scope" in node and isinstance(node["scope"], list):
            for i, scope_id in enumerate(node["scope"]):
                if scope_id in id_map:
                    node["scope"][i] = id_map[scope_id]

        if node.get("type") == "subflow" or node.get("type", "").startswith("subflow:"):
            if "in" in node and isinstance(node["in"], list):
                for in_config in node["in"]:
                    if "wires" in in_config and isinstance(in_config["wires"], list):
                        for wire in in_config["wires"]:
                            if "id" in wire and wire["id"] in id_map:
                                wire["id"] = id_map[wire["id"]]

            if "out" in node and isinstance(node["out"], list):
                for out_config in node["out"]:
                    if "wires" in out_config and isinstance(out_config["wires"], list):
                        for wire in out_config["wires"]:
                            if "id" in wire and wire["id"] in id_map:
                                wire["id"] = id_map[wire["id"]]

            if "env" in node and isinstance(node["env"], list):
                for env_var in node["env"]:
                    if "value" in env_var and isinstance(env_var["value"], str):
                        if env_var["value"] in id_map:
                            env_var["value"] = id_map[env_var["value"]]


def normalize_flow_ids(flow_data: list) -> tuple[list, dict]:
    """Normalize all node IDs in the flow. Returns (flow_data, id_map)"""
    id_map = {}
    used_ids = set()

    for node in flow_data:
        old_id = node.get("id")
        if old_id:
            new_id = generate_new_id(node, used_ids)
            id_map[old_id] = new_id
            node["id"] = new_id

    update_wires(flow_data, id_map)

    return flow_data, id_map


class NormalizeIdsPlugin:
    """Plugin for normalizing node IDs before explode"""

    def get_name(self) -> str:
        return "normalize-ids"

    def get_priority(self):
        return None  # Use filename prefix (10)

    def get_plugin_type(self) -> str:
        return "pre-explode"

    def process_flows_pre_explode(self, flow_data: list, repo_root: Path) -> list:
        """Normalize all node IDs in the flow"""
        # Run normalize
        normalized_flow, id_map = normalize_flow_ids(flow_data)

        if id_map:
            print(f"   Normalized {len(id_map)} node IDs")

        return normalized_flow
