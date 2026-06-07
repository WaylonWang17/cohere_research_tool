import os
import cohere
import json

from exa_py import Exa
from dotenv import load_dotenv
from cohere.types import TextAssistantMessageResponseContentItem

load_dotenv()

exa = Exa(os.getenv("EXA_API_KEY"))
co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))

def exa_func(prompt):
    response = exa.search(
        prompt,
        type="auto",
        contents={"highlights": True},
    )
    return [
        {"url": r.url, "title": r.title, "highlights": r.highlights}
        for r in response.results
    ]

functions_map = {"exa": exa_func} #maps string to function name so function can be called

tools = [
    {
        "type": "function",
        "function": {
            "name": "exa", #has to match key in functions_map
            "description": "does research",
            #parameters is a schema that must have type object
            "parameters": {
                "type": "object",
                #properties tells us the named fields that object can contain which is just prompt
                "properties": {
                    # our prompt whatever it ends up being has to be type string
                    "prompt": {
                        "type": "string",
                        "description": "the prompt that we're looking to do research on",
                    }
                },
                "required": ["prompt"],
            },
        },
    },
]

messages = [
    {"role": "user", "content": "Find the linkedin influencer with the most followers"}
]

#send users question + available tools to model so it can decide if it needs to call tools
response = co.chat(
    model="command-a-plus-05-2026", messages=messages, tools=tools
)

#checks to see if model used tool call
if response.message.tool_calls:
    messages.append(response.message) #append message asking for tool in messages
    for tc in response.message.tool_calls: #loops through all tool calls
        function_name = tc.function.name #inside of tools => function => name
        function_arguments = json.loads(tc.function.arguments) #parse argument from json string into python dict. Model generates '{"prompt": "linkedin influencer with most followers"}' and json.laod changes to {"prompt": "linkedin influencer with most followers"}
        function_to_call = functions_map[function_name] #look up python function by name 
        tool_result = function_to_call(**function_arguments) #unpack argument dict as keyword args converts {"prompt": "linkedin influencer with most followers"} to prompt=linkedin influencer with most followers
        tool_content = []
        for data in tool_result:
            tool_content.append(
                {
                    "type": "document",
                    "document": {"data": json.dumps(data)}, #json.dump serializes back to json
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

#original question + tool call + tools response and now cohere agent will form a response with all this info 
response = co.chat(
    model="command-a-plus-05-2026", messages=messages, tools=tools
)

if response.message.content:
    for item in response.message.content:
        if isinstance(item, TextAssistantMessageResponseContentItem):
            print(item.text)
            break
