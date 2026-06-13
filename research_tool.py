import os
import cohere
import json
import wikipediaapi
import requests

from exa_py import Exa
from dotenv import load_dotenv
from cohere.types import TextAssistantMessageResponseContentItem

question = input("what would you like to research?\n")

if not question:
    print('no question asked')
    exit()

load_dotenv()

# clients
exa = Exa(os.getenv("EXA_API_KEY"))
co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))
wiki = wikipediaapi.Wikipedia(user_agent='research_tool (waylon.wang17@gmail.com)', language='en')

def wikipedia_search(query):
    '''
    background knowledge
    '''
    results = wiki.search(query, limit=1)
    if not results.pages:
        return [{'error': f'No wikipedia page found for {query}'}]

    page = next(iter(results.pages.values()))
    return [{"url": page.fullurl, "title": page.title, "summary": page.summary}]


def exa_func(prompt):
    '''
    up to date info
    '''
    response = exa.search(
        prompt,
        type="auto",
        contents={"highlights": True},
    )
    return [
        {"url": r.url, "title": r.title, "highlights": r.highlights}
        for r in response.results
    ]

functions_map = {"exa": exa_func,
                 "wikipedia": wikipedia_search} #maps string to function name so function can be called

tools = [
    {
        "type": "function",
        "function": {
            "name": "exa", #has to match key in functions_map
            "description": "searches the live web for current/recent information",
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
    {
        "type": "function",
        "function": {
            "name": "wikipedia",
            "description": "looks up background information on a topic from wikipedia",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "the topic to look up on wikipedia",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

messages = [
    {"role": "user", "content": question},
    # {"role": "user", "content": "Find the linkedin influencer with the most followers"}
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
        print(f"[tool call] {function_name}({tc.function.arguments})")  # debug to see which tool got called
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
