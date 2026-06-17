import os
import cohere
import json
import wikipediaapi

from exa_py import Exa
from dotenv import load_dotenv
from cohere.types import TextAssistantMessageResponseContentItem #helps check "is this specific item a plain text response"

load_dotenv()

# clients
exa = Exa(os.getenv("EXA_API_KEY"))
co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))
wiki = wikipediaapi.Wikipedia(user_agent='research_tool (waylon.wang17@gmail.com)', language='en')

question = ""  #for tests

def wikipedia_search(query):
    '''
    background knowledge, reranked to pick the most relevant page
    '''
    results = wiki.search(query, limit=5)
    if not results.pages:
        return [{'error': f'No wikipedia page found for {query}'}]

    pages = list(results.pages.values())
    documents = []
    for page in pages:
        document_text = page.title + " " + page.summary
        documents.append(document_text)

    rerank_response = co.rerank(model="rerank-v4.0-pro", query=query, documents=documents, top_n=1)

    best = rerank_response.results[0]
    page = pages[best.index]
    return [{"url": page.fullurl, "title": page.title, "summary": page.summary, "relevance_score": best.relevance_score}]


def exa_func(prompt):
    '''
    up to date info, reranked to surface the most relevant results
    '''
    response = exa.search(
        prompt,
        type="auto",
        contents={"highlights": True},
    )

    results = []
    for r in response.results:
        results.append({"url": r.url, "title": r.title, "highlights": r.highlights})

    if not results:
        return results

    documents = []
    for r in results:
        highlights_text = ""
        for highlight in r["highlights"]:
            highlights_text = highlights_text + " " + highlight
        document_text = r["title"] + highlights_text
        documents.append(document_text)
    rerank_response = co.rerank(model="rerank-v4.0-pro", query=prompt, documents=documents, top_n=min(3, len(documents)))

    reranked = []
    for item in rerank_response.results:
        result = results[item.index]
        result["relevance_score"] = item.relevance_score
        reranked.append(result)

    return reranked

def save_notes(filename, content):
    '''
    saves to cohere/notes for traceback
    '''
    filename = os.path.basename(filename) #strip any path separators so files can't be written outside notes/
    os.makedirs("notes", exist_ok=True)
    path = os.path.join("notes", filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f'# Research Question\n\n{question}\n\n---\n\n{content}')
    return [{"status": "saved", "path": path}]

functions_map = {"exa": exa_func,
                 "wikipedia": wikipedia_search,
                 "save_notes": save_notes} #maps string to function name so function can be called

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
    {
        "type": "function",
        "function": {
            "name": "save_notes",
            "description": "saves research findings to a local markdown file for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "name of the file to save, e.g. 'eiffel_tower.md'",
                    },
                    "content": {
                        "type": "string",
                        "description": "the markdown content to write to the file",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
]

if __name__ == "__main__":
    question = input("What would you like to research?\n")

    if not question:
        print('no question asked')
        exit()

    #system prompt for saving token consumption
    messages = [
        {
            "role": "system",
            "content": """You are a research assistant with access to three tools:
- wikipedia: use first for background context and established facts
- exa: use for current events and recent information
- save_notes: use last to save a comprehensive markdown report of your findings

Start with wikipedia for background. Only call exa if it's actually needed for current information. Then synthesize and save.""",
        },
        {"role": "user", "content": question},
        # {"role": "user", "content": "Find the linkedin influencer with the most followers"}
    ]

    #send users question + available tools to model so it can decide if it needs to call tools
    response = co.chat(
        model="command-a-plus-05-2026", messages=messages, tools=tools
    )

    #loop until the model stops asking for tool calls, with a safety cap on iterations
    max_iterations = 5
    for _ in range(max_iterations):
        if not response.message.tool_calls:
            break

        messages.append(response.message) #append message asking for tool in messages
        for tc in response.message.tool_calls: #loops through all tool calls
            function_name = tc.function.name #inside of tools => function => name
            print(f"[tool call] {function_name}")  # debug to see which tool got called
            function_arguments = json.loads(tc.function.arguments) #parse argument from json string into python dict. Model generates '{"prompt": "linkedin influencer with most followers"}' and json.laod changes to {"prompt": "linkedin influencer with most followers"}
            function_to_call = functions_map[function_name] #look up python function by name
            tool_result = function_to_call(**function_arguments) #unpack argument dict as keyword args converts {"prompt": "linkedin influencer with most followers"} to prompt=linkedin influencer with most followers
            tool_content = []
            for data in tool_result:
                '''
                converts tools raw results into coheres chat api format
                '''
                tool_content.append(
                    {
                        "type": "document", #document is the type for external info injected into convo
                        "document": {"data": json.dumps(data)}, #json.dump serializes back to json
                    }
                )
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
    else:
        print("no response :(")