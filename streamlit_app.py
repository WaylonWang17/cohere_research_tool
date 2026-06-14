import os
import json
import cohere
import wikipediaapi
import streamlit as st

from exa_py import Exa
from dotenv import load_dotenv
from cohere.types import TextAssistantMessageResponseContentItem

load_dotenv()


@st.cache_resource
def get_clients():
    exa = Exa(os.getenv("EXA_API_KEY"))
    co = cohere.ClientV2(os.getenv("COHERE_API_KEY"))
    wiki = wikipediaapi.Wikipedia(user_agent="research_tool (waylon.wang17@gmail.com)", language="en")
    return exa, co, wiki


exa, co, wiki = get_clients()


def wikipedia_search(query):
    results = wiki.search(query, limit=1)
    if not results.pages:
        return [{"error": f"No wikipedia page found for {query}"}]

    page = next(iter(results.pages.values()))
    return [{"url": page.fullurl, "title": page.title, "summary": page.summary}]


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


def make_save_notes(question):
    def save_notes(filename, content):
        filename = os.path.basename(filename)  # strip any path separators so files can't be written outside notes/
        os.makedirs("notes", exist_ok=True)
        path = os.path.join("notes", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Research Question\n\n{question}\n\n---\n\n{content}")
        return [{"status": "saved", "path": path}]

    return save_notes


tools = [
    {
        "type": "function",
        "function": {
            "name": "exa",
            "description": "searches the live web for current/recent information",
            "parameters": {
                "type": "object",
                "properties": {
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


def run_agent(question, status):
    functions_map = {
        "exa": exa_func,
        "wikipedia": wikipedia_search,
        "save_notes": make_save_notes(question),
    }

    messages = [
        {
            "role": "system",
            "content": """You are a research assistant with access to three tools:
- wikipedia: use first for background context and established facts
- exa: only use if the question needs current/recent information that wikipedia can't provide (e.g. news, recent events, up-to-date data) - skip it otherwise
- save_notes: use last to save a comprehensive markdown report of your findings

Start with wikipedia for background. Only call exa if it's actually needed for current information. Then synthesize and save.""",
        },
        {"role": "user", "content": question},
    ]

    response = co.chat(model="command-a-plus-05-2026", messages=messages, tools=tools)

    max_iterations = 5
    saved_path = None
    for _ in range(max_iterations):
        if not response.message.tool_calls:
            break

        messages.append(response.message)
        for tc in response.message.tool_calls:
            function_name = tc.function.name
            status.write(f"🔧 calling `{function_name}`")
            function_arguments = json.loads(tc.function.arguments)
            function_to_call = functions_map[function_name]
            tool_result = function_to_call(**function_arguments)

            if function_name == "save_notes" and tool_result and "path" in tool_result[0]:
                saved_path = tool_result[0]["path"]

            tool_content = [
                {"type": "document", "document": {"data": json.dumps(data)}}
                for data in tool_result
            ]
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_content,
                }
            )

        response = co.chat(model="command-a-plus-05-2026", messages=messages, tools=tools)

    final_text = ""
    if response.message.content:
        for item in response.message.content:
            if isinstance(item, TextAssistantMessageResponseContentItem):
                final_text = item.text
                break

    return final_text, saved_path


st.title("Research Assistant")

question = st.text_input("What would you like to research?")

if st.button("Research") and question:
    status = st.container()
    with st.spinner("Researching..."):
        answer, saved_path = run_agent(question, status)

    st.markdown(answer)

    if saved_path:
        st.success(f"Notes saved to `{saved_path}`")
        with open(saved_path, "r", encoding="utf-8") as f:
            st.download_button("Download notes", f.read(), file_name=os.path.basename(saved_path))
