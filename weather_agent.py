import os
import json
import cohere
from cohere.types import TextAssistantMessageResponseContentItem
from dotenv import load_dotenv

load_dotenv()

co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))

def get_weather(location):
    # Implement your tool calling logic here
    return [{"temperature": "20C"}]
    # Return a list of objects e.g. [{"url": "abc.com", "text": "..."}, {"url": "xyz.com", "text": "..."}]


functions_map = {"get_weather": get_weather}

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "gets the weather of a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "the location to get weather, example: San Fransisco, CA",
                    }
                },
                "required": ["location"],
            },
        },
    },
]

messages = [
    {"role": "user", "content": "What's the weather in Toronto?"}
]

#co.chat calls cohere chat api 
response = co.chat(
    model="command-a-plus-05-2026", messages=messages, tools=tools
)

print(response)

if response.message.tool_calls:
    messages.append(response.message)
    for tc in response.message.tool_calls:
        if not tc.function:
            continue
        function_name = tc.function.name
        function_arguments = json.loads(tc.function.arguments)
        function_to_call = functions_map[function_name]
        tool_result = function_to_call(**function_arguments)
        tool_content = []
        for data in tool_result:
            tool_content.append(
                {
                    "type": "document",
                    "document": {"data": json.dumps(data)},
                }
            )
            # Optional: add an "id" field in the "document" object, otherwise IDs are auto-generated
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_content,
            }
        )

response = co.chat(
    model="command-a-plus-05-2026", messages=messages, tools=tools
)

if response.message.content:
    for item in response.message.content:
        if isinstance(item, TextAssistantMessageResponseContentItem):
            print(item.text)
            break

#UNEEDED FOR THIS SINCE ITS TOO SIMPLE
# if response.message.citations:
#     for citation in response.message.citations:
#         print(citation, "\n")

