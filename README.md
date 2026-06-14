# cohere research tool

# core features
- cohere command a plus model
- system prompt for saving token usage
- 3 tool calls
    - exa tool for up to date research
    - wikipedia api for background knowledge
    - save notes of research (markdown)
- agentic loop for thinking (max iterations = 5)
- simple ui on separate branch
    - to run streamlit ui 
        - .\venv\Scripts\Activate.ps1 
        - streamlit run streamlit_app.py

agentic systems
1. define functions for tools
2. create a function map used to map string to actual function name
3. tools schema
4. messages
5. initial cohere bot call (sending question + available tools)
6. see if any tools were called
7. second cohere bot call (og question + available tools + what tool gave back to us)
8. cohere bot reads everything and formulates a response
9. sends us response