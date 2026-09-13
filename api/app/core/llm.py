from openai import AsyncOpenAI
from .config import OPENAI_API_BASE, OPENAI_API_KEY

# Async client for the OpenAI-compatible LLM endpoint (base_url points at a
# third-party provider, e.g. Alibaba Model Studio's compatible-mode API).
llm_client = AsyncOpenAI(base_url=OPENAI_API_BASE, api_key=OPENAI_API_KEY)
