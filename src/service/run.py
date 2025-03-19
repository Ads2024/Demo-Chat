from typing_extensions import override
from openai import AssistantEventHandler

class StreamlitEventHandler(AssistantEventHandler):
    """Custom Streamlit-compatible event handler for real-time streaming."""

    def __init__(self, output_area):
        """
        Initialize with a Streamlit output area.

        Args:
            output_area: A Streamlit placeholder or container for updating text.
        """
        super().__init__()  # Initialize the base class
        self.output_area = output_area
        self.current_text = ""

    def on_text_created(self, text):
        """Handle when the assistant starts responding."""
        self.current_text += "Assistant started responding:\n"
        self.output_area.text(self.current_text)

    def on_text_delta(self, delta, snapshot):
        """Stream text deltas dynamically to the UI."""
        self.current_text += delta.value
        self.output_area.text(self.current_text)

    def on_tool_call_created(self, tool_call):
        """Handle tool invocation events."""
        self.current_text += f"\n[Tool Invoked: {tool_call.type}]\n"
        self.output_area.text(self.current_text)