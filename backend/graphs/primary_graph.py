"""
LangGraph workflow definition for conversation orchestration.

This module defines the primary conversation flow graph with nodes for
entry intent, order confirmation, and resolution handling.
"""

import os
import sys

from dotenv import load_dotenv  # type: ignore
from langgraph.graph import END  # type: ignore
from langgraph.graph import START
from langgraph.graph import StateGraph
from typing_extensions import TypedDict  # type: ignore


# Get the absolute path to the backend directory
current_dir = os.getcwd()  # Get current working directory
backend_path = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(backend_path)

# Load environment variables from .env file
load_dotenv()

#import nodes
from nodes import entry_intent
from nodes import order_confirmation
from nodes import resolution


class State(TypedDict):
    # Messages tracked in the conversation history
    messages: list
    # Transcription attributes tracks updates posted by the agent
    transcript: list
    # Session Id is the unique identifier attribute of the conversation
    session_id: str
    # Order number
    order_number: str
    # tracks in the conversation is still active
    session_end: bool
    # tracks the current node in the conversation
    current_turn: int
    # tracks the next node in the conversation
    next_node: str
    # track status of the confirmation
    order_confirmed: bool
    # track status of the ordes elegibles
    order_info_found: bool


# Define nodes and edges
graph_builder = StateGraph(State)

# add nodes
graph_builder.add_node("entry_intent", entry_intent.node)
graph_builder.add_node("order_confirmation", order_confirmation.node)
graph_builder.add_node("resolution", resolution.node)


def initial_router(state):
    if state.get('order_confirmed'):
        state['next_node'] = 'resolution'
    elif state.get('order_info_found'):
        state['next_node'] = 'order_confirmation'
    else:
        state['next_node'] = 'entry_intent'
    return state['next_node']


# Add edges with routing logic
graph_builder.add_conditional_edges(
    START,
    initial_router,
    {
        'entry_intent': 'entry_intent',
        'order_confirmation': 'order_confirmation',
        'resolution': 'resolution'
    }
)

graph_builder.add_conditional_edges(
    'entry_intent',
    lambda x: x["next_node"],
    {
        'order_confirmation': 'order_confirmation',
        '__end__': END
    }
)

graph_builder.add_conditional_edges(
    'order_confirmation',
    lambda x: x["next_node"],
    {
        'resolution': 'resolution',
        '__end__': END
    }
)

graph_builder.add_edge('resolution', END)

graph = graph_builder.compile()
graph = graph_builder.compile()
