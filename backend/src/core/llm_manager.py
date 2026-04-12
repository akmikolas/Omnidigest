"""
LLM Management Service.
Handles dynamic selection of LLM models from the database and automatic failover.
LLM 管理服务。处理从数据库动态选择 LLM 模型以及自动故障转移。
"""
import logging
import asyncio
import json
import re
import instructor
from openai import AsyncOpenAI
from httpx import AsyncClient, Timeout
from .database import DatabaseManager
from ..config import settings

logger = logging.getLogger(__name__)

class LLMManager:
    """
    Manages multiple LLM providers and handles automatic switching on failure.
    管理多个 LLM 提供商并在故障时处理自动切换。
    """
    def __init__(self, db: DatabaseManager):
        """
        Initializes the LLMManager with a database connection and sets up internal state.
        使用数据库连接初始化 LLMManager 并设置内部状态。

        Args:
            db (DatabaseManager): The database manager instance for model fetching. / 用于获取模型的数据库管理器实例。
        """
        self.db = db
        self._current_model = None
        self._client = None
        self._http_client = None
        self._lock = asyncio.Lock()

    async def close(self):
        """
        Closes the underlying HTTP client to release connections.
        关闭底层 HTTP 客户端以释放连接。
        """
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._client = None

    async def _refresh_client(self, exclude_ids=None):
        """
        Fetches the highest priority active model and initializes the OpenAI client.
        获取优先级最高的活动模型并初始化 OpenAI 客户端。
        """
        models = await asyncio.to_thread(self.db.get_active_llm_models)
        
        # Filter out excluded IDs (models that failed in this session)
        if exclude_ids:
            models = [m for m in models if str(m['id']) not in exclude_ids]
        if not models:
            logger.warning("No active LLM models found in DB. Falling back to settings.")
            model = {
                "id": None,
                "name": "Settings Fallback",
                "api_key": settings.llm_api_key,
                "base_url": settings.llm_base_url,
                "model_name": settings.llm_model_name
            }
        else:
            model = models[0]
            # Ensure UUID is string if it comes as a UUID object
            if model.get('id'):
                model['id'] = str(model['id'])

        logger.info(f"Switching to LLM Model: {model.get('name')} ({model.get('model_name')})")

        # Close old client before creating new one to prevent connection leaks
        if self._http_client:
            await self._http_client.aclose()

        http_client = AsyncClient(timeout=Timeout(60.0, connect=10.0))
        self._http_client = http_client
        # Keep native AsyncOpenAI client as default to not break unstructured calls
        self._client = AsyncOpenAI(
            api_key=model['api_key'],
            base_url=model['base_url'],
            http_client=http_client
        )
        self._current_model = model

    def _clean_json_output(self, content: str) -> str:
        """
        Cleans JSON output from LLMs, stripping Markdown blocks and potential XML-like tags (common in Qwen).
        清洗 LLM 输出的 JSON，去除 Markdown 块和可能存在的类似 XML 的标签（常见于 Qwen）。
        """
        if not content:
            return ""
        
        # 1. Strip Markdown code blocks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        content = content.strip()
        
        # 2. Handle DashScope/Qwen XML-like noise (e.g. <tool_call>...</tool_call>)
        # If we see <tool_call>, try to extract arguments from inside it
        if "<tool_call>" in content:
            # Regex to find <parameter=...>(.*)</parameter> patterns inside <tool_call>
            # However, DashScope often returns a custom structure.
            # If it's the XML format seen in the 400 error, we might need a specific fix.
            # For now, let's try to find the first '{' and last '}' if they exist
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return match.group(0)
            
            # If no JSON found but there's a parameter list, we might have to reconstruct it
            # But normally instructor.Mode.JSON avoids this XML stuff.
        
        return content

    async def get_client_and_model(self, exclude_ids=None):
        """
        Returns the current client and model metadata. Refreshes if needed or if current is excluded.
        返回当前的客户端和模型元数据。如果需要或当前模型被排除，则刷新。
        """
        async with self._lock:
            # Refresh if no client exists OR if the current model is in exclude_ids
            if not self._client or (self._current_model and str(self._current_model.get('id')) in (exclude_ids or [])):
                await self._refresh_client(exclude_ids=exclude_ids)
            return self._client, self._current_model

    async def chat_completion_structured(self, response_model, messages, temperature=0.7, max_retries=3, service_name="default", **kwargs):
        """
        Instructor-powered structured chat completion with automatic retry and failover.
        使用 Instructor 进行的结构化输出，具备自动重试和故障转移功能。

        Args:
            response_model: A Pydantic BaseModel class for the expected output structure.
            messages (list): List of message dictionaries.
            temperature (float): Sampling temperature.
            max_retries (int): Number of retries via Instructor internal mechanism.
            service_name (str): Identifier for the calling service to track token usage.
            **kwargs: Additional arguments for the API.

        Returns:
            An instance of the provided response_model.
        """
        max_attempts = 3
        last_error = None
        excluded_ids = set()

        for attempt in range(max_attempts):
            client, model = await self.get_client_and_model(exclude_ids=excluded_ids)
            model_id = model.get('id')
            base_url = model.get('base_url', '')
            model_name = model.get('model_name', '')
            
            # Provider-specific mode selection
            # Some providers (like DashScope/Qwen) are strictly OpenAI-compatible but fail on TOOLS mode.
            # We default to instructor.Mode.JSON for these for maximum stability.
            is_dashscope = "dashscope" in base_url.lower() or "aliyuncs.com" in base_url.lower()
            is_minimax = "minimaxi" in base_url.lower()

            # Determine best instructor mode
            mode = instructor.Mode.TOOLS
            if is_dashscope:
                # Use MD_JSON or JSON for DashScope/Qwen models
                mode = instructor.Mode.MD_JSON
            elif is_minimax:
                # MiniMax API works better with plain JSON mode
                mode = instructor.Mode.JSON

            # Patch native client with Instructor locally for this call
            instructor_client = instructor.from_openai(client, mode=mode)

            try:
                response, raw_completion = await instructor_client.chat.completions.create_with_completion(
                    model=model_name,
                    response_model=response_model,
                    messages=messages,
                    temperature=temperature,
                    max_retries=max_retries,
                    **kwargs
                )
                
                # Success! Reset failure count if it's a DB-tracked model
                if model_id:
                    await asyncio.to_thread(self.db.reset_llm_failure, model_id)
                
                # Record token usage asynchronously
                if hasattr(raw_completion, 'usage') and raw_completion.usage:
                    # Get cached tokens if available (DashScope supports this)
                    cached_tokens = 0
                    if hasattr(raw_completion.usage, 'cached_tokens'):
                        cached_tokens = raw_completion.usage.cached_tokens or 0
                    elif hasattr(raw_completion.usage, 'prompt_token_details'):
                        # Some providers return cached details in prompt_token_details
                        details = raw_completion.usage.prompt_token_details
                        if details and hasattr(details, 'cached_tokens'):
                            cached_tokens = details.cached_tokens or 0
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.db.record_token_usage,
                            service_name,
                            model['model_name'],
                            raw_completion.usage.prompt_tokens,
                            raw_completion.usage.completion_tokens,
                            cached_tokens
                        )
                    )
                
                return response

            except Exception as e:
                last_error = e
                logger.error(f"Structured LLM Error with model '{model.get('name')}': {e}")
                
                # Report failure to DB
                if model_id:
                    await asyncio.to_thread(self.db.increment_llm_failure, model_id, str(e))
                    excluded_ids.add(str(model_id))
                
                # Invalidate client and model to force a switch on next attempt
                async with self._lock:
                    self._client = None
                    self._current_model = None

                if attempt < max_attempts - 1:
                    logger.info(f"Retrying structured LLM completion (Attempt {attempt + 2}/{max_attempts})...")
                    await asyncio.sleep(1)
                
        raise last_error

    async def chat_completion(self, messages, temperature=0.7, return_full_response=False, service_name="default", **kwargs):
        """
        Wrapper for chat completions with automatic retry and failover.
        chat completions 的包装器，具有自动重试和故障转移功能。

        Args:
            messages (list): List of message dictionaries. / 消息字典列表。
            temperature (float): Sampling temperature. / 采样温度。
            return_full_response (bool): If True, returns the full ChatCompletion object. / 如果为 True，则返回完整的 ChatCompletion 对象。
            service_name (str): Identifier for the calling service to track token usage.
            **kwargs: Additional arguments for the OpenAI API. / OpenAI API 的其他参数。

        Returns:
            str | ChatCompletion: The generated message content OR the full response object. / 生成的消息内容或完整的响应对象。
        """
        max_attempts = 3
        last_error = None
        excluded_ids = set()

        for attempt in range(max_attempts):
            client, model = await self.get_client_and_model(exclude_ids=excluded_ids)
            model_id = model.get('id')
            
            try:
                response = await client.chat.completions.create(
                    model=model['model_name'],
                    messages=messages,
                    temperature=temperature,
                    **kwargs
                )
                
                # Success! Reset failure count if it's a DB-tracked model
                if model_id:
                    await asyncio.to_thread(self.db.reset_llm_failure, model_id)
                
                # Record token usage asynchronously
                if hasattr(response, 'usage') and response.usage:
                    # Get cached tokens if available (DashScope supports this)
                    cached_tokens = 0
                    if hasattr(response.usage, 'cached_tokens'):
                        cached_tokens = response.usage.cached_tokens or 0
                    elif hasattr(response.usage, 'prompt_token_details'):
                        # Some providers return cached details in prompt_token_details
                        details = response.usage.prompt_token_details
                        if details and hasattr(details, 'cached_tokens'):
                            cached_tokens = details.cached_tokens or 0
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.db.record_token_usage,
                            service_name,
                            model['model_name'],
                            response.usage.prompt_tokens,
                            response.usage.completion_tokens,
                            cached_tokens
                        )
                    )
                
                if return_full_response:
                    return response
                return response.choices[0].message.content or ""

            except Exception as e:
                last_error = e
                logger.error(f"LLM Error with model '{model.get('name')}': {e}")
                
                # Report failure to DB
                if model_id:
                    # Threshold for deactivation is 5 by default
                    await asyncio.to_thread(self.db.increment_llm_failure, model_id, str(e))
                    excluded_ids.add(str(model_id))
                
                # Invalidate client and model to force a switch on next attempt
                async with self._lock:
                    self._client = None
                    self._current_model = None

                if attempt < max_attempts - 1:
                    logger.info(f"Retrying LLM completion (Attempt {attempt + 2}/{max_attempts})...")
                    await asyncio.sleep(1) # Brief pause before retry
                
        # If all attempts fail
        raise last_error
