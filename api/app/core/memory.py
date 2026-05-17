"""
Conversation summarisation memory module for agent framework.
- Stores full conversation history
- Maintains rolling summary for context injection
- Practical, visible, enterprise-relevant, demo-friendly
"""
from typing import List, Dict, Any

class ConversationMemory:
    def __init__(self, max_history: int = 20, max_summary_tokens: int = 1024):
        self.history: List[Dict[str, Any]] = []
        self.summary: str = ""
        self.max_history = max_history
        self.max_summary_tokens = max_summary_tokens

    def add_turn(self, user: str, message: str, agent: str = None, agent_response: str = None):
        turn = {"user": user, "message": message}
        if agent is not None:
            turn["agent"] = agent
        if agent_response is not None:
            turn["agent_response"] = agent_response
        self.history.append(turn)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_recent_history(self) -> List[Dict[str, Any]]:
        return self.history[-self.max_history:]

    def summarise(self, summariser_fn):
        # summariser_fn should take a list of turns and return a summary string
        self.summary = summariser_fn(self.get_recent_history())
        return self.summary

    def get_summary(self) -> str:
        return self.summary

    def clear(self):
        self.history.clear()
        self.summary = ""
