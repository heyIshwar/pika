from pika.agent import BaseAgent


class ResearchAgent(BaseAgent):
    agent_id = "research_agent"
    description = "Researches topics and returns concise summaries with sources"

    instructions = [
        "Always search for at least 3 sources before answering when possible",
        "Include URLs of sources in your response",
        "Keep summaries under 200 words unless asked for more",
        "If uncertain, say so",
    ]

    markdown = True
    add_datetime_to_context = True
