"""
General utility functions for the chatbot backend.

This module provides common helper functions for data processing,
Bedrock API interactions, tool execution, and shared functionality across the application.
"""

import json
import logging
import os
import re
import secrets
import time

import boto3
import mlflow
import psycopg2
from mlflow.entities import SpanType

from .rds_utils import CustomJSONEncoder, get_db_connection

bedrock_client = boto3.client(service_name="bedrock-runtime")


# logger = logging.getLogger()
# logger.setLevel("INFO")

def extract_reply(text):
    """Extract the reply text from the given text wrapped in <reply> tags."""
    pattern = r"<reply>(.*?)</reply>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None  # Return None if no <reply> tags found


@mlflow.trace(span_type=SpanType.CHAT_MODEL)
def process_message(
    messages,
    model_id,
    formatted_system_prompt,
    tool_config: dict = None,
    inference_config: dict = {},
    additional_model_fields: dict = {},
    request_metadata: dict = {}
):
    """Process the given messages and generate a response using the Bedrock model."""
    max_retries = 4
    base_delay = 1  # Base delay in seconds
    
    for retry in range(max_retries):
        try:
            system_prompts = [{"text": formatted_system_prompt}]
            formatted_messages = messages

            # Check if toolUse.input is a dictionary or a JSON string
            for message in formatted_messages:
                if isinstance(message, dict) and message.get("role") == "assistant":
                    for content in message.get("content", []):
                        if "toolUse" in content:
                            input_value = content["toolUse"]["input"]
                            if isinstance(input_value, str):
                                # If it's a string, parse it as JSON
                                content["toolUse"]["input"] = json.loads(input_value)
                            elif isinstance(input_value, dict):
                                # If it's already a dictionary, no need to parse
                                pass
                            else:
                                # Handle other types or raise an error if needed
                                raise ValueError(
                                    "Unexpected type for toolUse.input: %s" % type(input_value)
                                )

            response = bedrock_client.converse(
                modelId=model_id,
                messages=formatted_messages,
                system=system_prompts,
                toolConfig=tool_config,
                inferenceConfig=inference_config,
                additionalModelRequestFields=additional_model_fields,
            )

            message = response["output"]["message"]
            stop_reason = response.get("stopReason")
            return response, message, stop_reason

        except Exception as e:
            if retry == max_retries - 1:
                raise e
            
            # Calculate exponential delay with jitter
            delay = (2 ** retry) * base_delay + secrets.SystemRandom().uniform(0, 0.1)
            print(f'\n ------- RETRY {retry + 1} with delay {delay:.2f}s ---------- \n')
            time.sleep(delay)


def _process_tool_call(tool_name, tool_input):
    """Process the tool call based on the given tool name and input."""
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            if tool_name == "get_user":
                key = tool_input["key"]
                value = tool_input["value"]
                
                # Whitelist of allowed column names to prevent SQL injection
                allowed_columns = {"id", "name", "email", "phone", "username"}
                column_name = key.lower()
                if column_name not in allowed_columns:
                    error_msg = f"Invalid search field: {key}"
                    logging.error("SQL injection attempt detected - invalid column: %s", key)
                    raise ValueError(error_msg)
                
                # Use parameterized query with validated column name
                query = f"SELECT * FROM customers WHERE {column_name} = %s"
                # logging.info("Executing query: %s with value: %s", query, value)
                cursor.execute(query, (value,))
                user = cursor.fetchone()
                if user:
                    user_dict = dict(
                        zip(["id", "name", "email", "phone", "username"], user)
                    )
                    # logging.info("User found: %s", user_dict)
                    return user_dict
                else:
                    # logging.info("Couldn't find a user with %s of %s", key, value)
                    return f"Couldn't find a user with {key} of {value}"
            elif tool_name == "get_order_by_id":
                order_id = tool_input["order_id"]
                query = "SELECT * FROM orders WHERE id = %s"
                # logging.info("Executing query: %s with order_id: %s", query, order_id)
                cursor.execute(query, (order_id,))
                order = cursor.fetchone()
                if order:
                    order_dict = dict(
                        zip(
                            [
                                "id",
                                "customer_id",
                                "product",
                                "quantity",
                                "price",
                                "status",
                            ],
                            order,
                        )
                    )
                    # logging.info("Order found: %s", order_dict)
                    return order_dict
                else:
                    # logging.info("Order not found with ID: %s", order_id)
                    return None
            elif tool_name == "get_customer_orders":
                customer_id = tool_input["customer_id"]
                query = "SELECT * FROM orders WHERE customer_id = %s"
                # logging.info(
                #     "Executing query: %s with customer_id: %s", query, customer_id
                # )
                cursor.execute(query, (customer_id,))
                orders = cursor.fetchall()
                orders_list = [
                    dict(
                        zip(
                            [
                                "id",
                                "customer_id",
                                "product",
                                "quantity",
                                "price",
                                "status",
                            ],
                            order,
                        )
                    )
                    for order in orders
                ]
                # logging.info("Customer orders found: %s", orders_list)
                return orders_list
            elif tool_name == "cancel_order":
                order_id = tool_input["order_id"]
                query = "UPDATE orders SET status = 'Cancelled' WHERE id = %s AND status = 'Processing'"
                print(f'\n ------- CANCEL ORDER: {order_id} ---------- \n')
                print(f'\n ------- QUERY: {query.format(order_id)} ----------- \n')
                print('Cancel successful: Mockup function not real implementation')
                # # logging.info("Executing query: %s with order_id: %s", query, order_id)
                # cursor.execute(query, (order_id,))
                # if cursor.rowcount > 0:
                #     connection.commit()
                #     # logging.info("Order %s cancelled successfully", order_id)
                return "Cancelled the order"
            elif tool_name == "update_order":
                order_id = tool_input["order_id"]
                print(f'\n ------- UPDATE ORDER: {order_id} ---------- \n')
                print('Update successful: Mockup function not real implementation')
                return "Order Updated"
    except (Exception, psycopg2.DatabaseError) as error:
        # logging.exception("Error processing tool call: %s", error)
        raise RuntimeError(
            "An error occurred while processing the database operation. "
            "Please try again or contact support if the issue persists."
        )
    finally:
        if connection:
            connection.close()


@mlflow.trace(span_type=SpanType.TOOL)
def use_tool(messages):
    """Use the appropriate tool based on the last message in the given messages."""

    # logger.info("Model wants to use a tool")
    # logger.info("Messages: %s", json.dumps(messages, indent=2))
    tool_use = messages[-1]["content"][-1].get("toolUse")
    # logging.info("Tool Use: %s", json.dumps(tool_use, indent=2))
    if tool_use:
        tool_name = tool_use["name"]
        tool_input = tool_use["input"]
        # logging.info("Tool Name: %s", tool_name)
        # logging.info("Tool Input: %s", json.dumps(tool_input, indent=2))

        # Process the tool call
        tool_result = _process_tool_call(tool_name, tool_input)
        # logging.info("Tool Result: %s", tool_result)
        message = {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use["toolUseId"],
                        "content": [
                            {"text": json.dumps(tool_result, cls=CustomJSONEncoder)}
                        ],
                        "status": "success",
                    }
                }
            ],
        }

        # logging.info("Message after tool use: %s", json.dumps(message, indent=2))
        return message

    else:
        logging.error("Tool use object not found in the response")
