from mimi_lib.tools.registry import register_tool
from mimi_lib.utils.filesystem import read_file, write_file, list_directory, search_files, get_codebase_index

register_tool(
    "read_file",
    "Read a local file.",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
)(read_file)

register_tool(
    "write_file",
    "Write to a local file.",
    {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}
)(write_file)

register_tool(
    "list_directory",
    "List files in a directory.",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
)(list_directory)

register_tool(
    "search_files",
    "Search for files by pattern.",
    {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["path", "pattern"]}
)(search_files)

register_tool(
    "get_codebase_index",
    "Get an index of the codebase.",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
)(get_codebase_index)
