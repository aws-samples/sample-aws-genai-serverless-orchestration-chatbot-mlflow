"""
Final resolution node for conversation completion.

This module handles conversation finalization, session management,
and cleanup after successful order processing.
"""

import logging
import os
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import mlflow  # type: ignore
from dotenv import load_dotenv  # type: ignore
from langgraph.graph import END  # type: ignore
from mlflow.entities import SpanType  # type: ignore
from static import static

# from backend import tools_config
from tools_config.agent_tool import tool_config as agent_tool_config
from utils import utils


# Get the absolute path to the backend directory
current_dir = os.getcwd()  # Get current working directory
backend_path = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(backend_path)

# Load environment variables from .env file
load_dotenv()

# configure logging
logger = logging.getLogger()
logger.setLevel("INFO")


@mlflow.trace(span_type=SpanType.AGENT)
def node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolution node for processing final conversation interactions and handling farewells.

    This node handles:
    1. Processing final messages and responses
    2. Tool execution and response handling
    3. Farewell detection and session termination
    4. State management and transcript updates

    Args:
        state (Dict[str, Any]): Current conversation state containing:
            - session_id: Unique session identifier
            - messages: List of conversation messages
            - transcript: Conversation history
            - other state variables

    Returns:
        Dict[str, Any]: Updated state dictionary containing:
            - messages: Updated conversation messages
            - transcript: Updated conversation history
            - session_end: Boolean indicating if session should end
            - next_node: Next node in conversation flow (typically END)

    """
    print('\n <=============== Node: resolution =====================> \n')

    session_id = state.get('session_id')
    messages = state.get('messages', [])
    transcript = state.get('transcript', [])

    # Configure API call parameters
    inference_config = {"temperature": static.TEMPERATURE, "maxTokens": static.MAX_TOKENS}
    additional_model_fields = {"top_k": static.TOP_K}
    request_metadata = {'string': 'string'}

    # Create a temporary messages array without the last assistant message
    temp_messages = messages[:-1] if messages and messages[-1]['role'] == 'assistant' else messages.copy()

    # Process message
    response, message, stop_reason = utils.process_message(
        messages=temp_messages,
        model_id=os.getenv('MODELID_CHAT'),
        formatted_system_prompt=static.SYSTEM_PROMPT_RESOLUTION.format(persona=static.PERSONA, transcript=transcript), 
        tool_config=agent_tool_config,
        inference_config=inference_config,
        additional_model_fields=additional_model_fields,
        request_metadata=request_metadata
    )
    # Safely handle content
    if response and 'output' in response and 'message' in response['output']:
        content_list = response['output']['message']['content']
        if content_list:  # Check if content list is not empty
            content = content_list[0]
            if 'text' in content:
                reply_text = utils.extract_reply(content['text'])
                if reply_text:
                    transcript.append({'assistant': reply_text})
                    state['transcript'] = transcript
                # Only append if the last message isn't already from assistant
                if not messages or messages[-1]['role'] != 'assistant':
                    messages.append(message)
                    state['messages'] = messages
                # If this is a final response (contains <reply>), stop processing
                if '<reply>' in content['text']:
                    stop_reason = None
        else:
            logger.warning(f"Empty content received from Bedrock for session {session_id}")
            # Don't append empty messages to avoid Bedrock validation errors

    # execute function tool dynamically
    while stop_reason == "tool_use":
        tool_response = utils.use_tool(messages)
        if tool_response:
            messages.append(tool_response)
        else:
            # If tool execution fails, break immediately
            logger.warning(f"Tool execution failed for session {session_id}, ending conversation")
            stop_reason = None
            break
        state['messages'] = messages
            
        # After any successful tool execution, get final response from LLM
        temp_messages = messages.copy()
        response, message, stop_reason = utils.process_message(
            messages=temp_messages,
            model_id=os.getenv('MODELID_CHAT'),
            formatted_system_prompt=static.SYSTEM_PROMPT_RESOLUTION.format(persona=static.PERSONA, transcript=transcript),
            tool_config=agent_tool_config,
            inference_config=inference_config,
            additional_model_fields=additional_model_fields,
            request_metadata=request_metadata
        )
        
        if response and 'output' in response and 'message' in response['output']:
            content_list = response['output']['message']['content']
            if content_list:  # Check if content list is not empty
                content = content_list[0]
                if 'text' in content:
                    reply_text = utils.extract_reply(content['text'])
                    if reply_text:
                        transcript.append({'assistant': reply_text})
                        state['transcript'] = transcript
                    # Only append if the last message isn't already from assistant
                    if not messages or messages[-1]['role'] != 'assistant':
                        messages.append(message)
                        state['messages'] = messages
                    # If this is a final response (contains <reply>), stop processing
                    if '<reply>' in content['text']:
                        stop_reason = None
            else:
                logger.warning(f"Empty content received from Bedrock for session {session_id}")
                # Don't append empty messages to avoid Bedrock validation errors

    # Check for farewell phrases in the last user message
    last_user_message = ""
    for msg in reversed(messages):
        if msg['role'] == 'user':
            content = msg['content'][0]
            if 'text' in content:
                last_user_message = content['text'].lower()
                break
    
    farewell_phrases = ["that's all thanks", "i'm all set", "bye", "goodbye", "thank you", "thanks"]
    
    if any(phrase in last_user_message for phrase in farewell_phrases):
        state['session_end'] = True
    # Set next_node to END since this is the final node
    state['next_node'] = END

    return state
