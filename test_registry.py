from tools.registry import (
    TOOLS,
    execute_tool,
    get_tool_descriptions,
)

print("Registered tools:")
print(get_tool_descriptions())

print("\nCurrent time test:")
print(execute_tool("get_current_time"))

print("\nUnknown tool test:")
print(execute_tool("does_not_exist"))