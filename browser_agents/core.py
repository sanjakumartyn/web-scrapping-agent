"""Core browser agent utilities using browser-use and LangChain LLM."""
import os
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent  # type: ignore
from langchain_google_genai import ChatGoogleGenerativeAI

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() in ("1", "true", "yes")


async def run_browser_task(task: str, max_steps: int = 15) -> str:
    """Run a browser-use Agent asynchronously with the provided task.

    Args:
        task: Natural language instructions for the browser agent.
        max_steps: Max navigation/interaction steps for the agent.

    Returns:
        The agent result as plain text, or empty string on failure.

    This wraps agent execution in try/except and returns an empty string
    with a printed warning on error to avoid crashing the pipeline.
    """
    try:
        # Create LLM instance for the agent
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            temperature=0.2,
            google_api_key=GOOGLE_API_KEY
        )

        # Create the browser agent. API for browser_use may vary; pass
        # sensible defaults: task, llm, headless and max_steps.
        agent = Agent(task=task, llm=llm, headless=BROWSER_HEADLESS, max_steps=max_steps)

        # Run the agent asynchronously and return its text output
        if asyncio.iscoroutinefunction(agent.run):
            result = await agent.run()
        else:
            # fallback if run is synchronous
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, agent.run)

        return str(result or "")
    except Exception as e:
        print(f"run_browser_task: agent failed: {e}")
        return ""
