import json
from openai import AsyncAzureOpenAI
from app.exceptions.open_ai_limit_exceeded import OpenAILimitExceeded
from app.exceptions.responsible_ai_policy_violation import ResponsibleAIPolicyViolation

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class OpenAIService:
    def __init__(self, base_url, api_key, deployment_name, api_version):
        self.base_url = base_url
        self.api_key = api_key
        self.deployment_name = deployment_name
        self.api_version = api_version
        
        self.client = AsyncAzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            base_url=self.base_url
        )
        logger.info("OpenAIService initialized with base_url: %s, deployment_name: %s", base_url, deployment_name)

    async def answer_query(self, question):
        try:
            logger.info("Querying OpenAI with question: %s", question)
            response = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=question
            )
            logger.info("Received response from OpenAI for question: %s", question)
            logger.debug("OpenAI response: %s", response)
            return response
        
        except Exception as ex:
            logger.error("An error occurred in OpenAIService.answer_query: %s", str(ex), exc_info=True)
            if hasattr(ex, 'status_code') and ex.status_code == 400:
                error_message = json.loads(ex.response.content)["error"]["message"]
                prompt_content = json.loads(ex.request.content)["messages"][-1]["content"]
                logger.error("Responsible AI policy violation: %s", error_message)
                raise ResponsibleAIPolicyViolation(error_message, prompt_content)
            elif hasattr(ex, 'status_code') and ex.status_code == 429:
                error_message = json.loads(ex.response.content)["error"]["message"]
                logger.error("Open AI Limit Exceeded: %s", error_message)
                raise OpenAILimitExceeded(error_message)
            return None

    async def determine_input_type(self, user_input):
        prompt = (f"Determine whether the following user input indicates an intention to generate or create an image. "
                  f"If the input suggests creating or drawing an image, respond with 'image'. Otherwise, respond with 'text'.\n\n"
                  f"User input: {user_input}")
        try:
            logger.info("Querying OpenAI to determine input type with prompt: %s", prompt)
            response = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0
            )
            logger.info(f"Received response from OpenAI for input type determination. {response.choices[0].message.content}")
            logger.debug("OpenAI response: %s", response)
            return response.choices[0].message.content
        
        except Exception as ex:
            logger.error("An error occurred in OpenAIService.determine_input_type: %s", str(ex), exc_info=True)
            if hasattr(ex, 'status_code') and ex.status_code == 400:
                error_message = json.loads(ex.response.content)["error"]["message"]
                prompt_content = json.loads(ex.request.content)["messages"][-1]["content"]
                logger.error("Responsible AI policy violation: %s", error_message)
                raise ResponsibleAIPolicyViolation(error_message, user_input)

            return None
