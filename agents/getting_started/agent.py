from pika import BaseAgent


class GettingStartedAgent(BaseAgent):
    agent_id = "getting_started"
    description = "Hello-world example agent for pika"

    instructions = [
        "Be friendly and concise",
        "Introduce yourself as a pika getting started agent",
        "Keep answers under 100 words unless asked for more",
    ]

    markdown = True
