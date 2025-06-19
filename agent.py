import os
from smolagents import CodeAgent, InferenceClientModel, OpenAIServerModel, WebSearchTool
from tools import storePipelineTool, pipelineStatusTool, pipelineTriggerTool, validatePipelineTool, pipelineRescanTool, testPipelineTool

# get the model
model = OpenAIServerModel(
    model_id="gemini-2.5-flash",
    api_key=os.getenv("GOOGLE_GEMINI_API_KEY"),
    # Google Gemini OpenAI-compatible API base URL
    api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# Initialize the agent
agent = CodeAgent(
    model=model,
    tools=[storePipelineTool, validatePipelineTool, 
        pipelineStatusTool, pipelineTriggerTool,
        pipelineRescanTool, testPipelineTool],
    stream_outputs=False,
    additional_authorized_imports=[],
)

# read the prompt
with open("./prompt.md", 'r', encoding='utf-8') as file:
    prompt = file.read()

# Run the agent
response = agent.run(prompt)
print(response)

