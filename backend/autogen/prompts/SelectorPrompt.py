selector_description = """Responsible for selecting the appropriate agent to perform the next task based on the conversation context and the roles of each agent.
"""

selector_prompt = """Select an agent to perform task.
{{roles}}

Current conversation context:
{{history}}

Read the above conversation, then select an agent from {{participants}} to perform the next task.
Make sure the planner agent has assigned tasks before other agents start working.
Only select one agent.
"""

# selector_prompt = """Select an agent to perform task.
# {{roles}}

# Current conversation context:
# {{history}}

# Usually, select the Search agent after the Planning agent has assigned tasks, and select the Transaction agent after the Search agent has verified the price and availability of the selected flight or hotel.
# Read the above conversation, then select an agent from {{participants}} to perform the next task.
# Make sure the planner agent has assigned tasks before other agents start working.
# Only select one agent.
# """