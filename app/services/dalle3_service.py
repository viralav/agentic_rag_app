import os
from openai import AsyncAzureOpenAI
import json

from app.exceptions.open_ai_limit_exceeded import OpenAILimitExceeded
from app.exceptions.responsible_ai_policy_violation import ResponsibleAIPolicyViolation

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class DallE3Service:
    def __init__(self, base_url, api_key, deployment_name, api_version):
        self.base_url = base_url
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            base_url=self.base_url
        )
        self.deployment_name = deployment_name
        logger.info(f"DallE3Service initialized with base_url: {base_url}, deployment_name: {deployment_name}")

    async def generate_image(self, question):
        logger.info("Generating image for query: %s", question)
        try:
            result = await self.client.images.generate(
                model=self.deployment_name,
                prompt=question,
                n=1
            )
            logger.info("Image successfully generated for query: %s", question)
            json_response = json.loads(result.model_dump_json())
            logger.debug("Generated image response: %s", json_response)
            return json_response

        except Exception as ex:
            logger.error("An error occurred in DallE3Service.generate_image: %s", str(ex), exc_info=True)
            if ex.status_code == 400:
                error_message = json.loads(ex.response.content)["error"]["message"]
                prompt = json.loads(ex.request.content)["prompt"]
                logger.error("Responsible AI policy violation: %s", error_message)
                raise ResponsibleAIPolicyViolation(error_message, prompt)
            elif ex.status_code == 429:
                error_message = json.loads(ex.response.content)["error"]["message"]
                logger.error("Open AI Limit Exceeded: %s", error_message)
                raise OpenAILimitExceeded(error_message)
            return None
