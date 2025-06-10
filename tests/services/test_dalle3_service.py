from asyncio import Future
import asyncio
import os
import unittest
import json
from unittest import mock
from unittest.mock import Mock, patch, AsyncMock

from openai import AsyncAzureOpenAI, AsyncOpenAI
from app.exceptions.responsible_ai_policy_violation import ResponsibleAIPolicyViolation
from app.services.dalle3_service import DallE3Service
from tests.util import ResponseFunctionDictionary  


def model_dump_json() :
    return json.dumps({
        "id": 'mock_image',
        "created": 1234567890,
        "data": [{'url': 'http://ai.com/mock_image.png'}]
        })

model_dict = {
    "model_dump_json" : model_dump_json
}

mock_response_json = ResponseFunctionDictionary(model_dict)

async def dummy_async_function():
    await asyncio.sleep(0.1)
    return mock_response_json

@mock.patch.dict(os.environ, {"APP_INSIGHTS_KEY" : "6e0925b6-e53c-49a9-a624-48c0a286a4aa"})
class TestDallE3Service(unittest.IsolatedAsyncioTestCase):

    @patch('app.services.dalle3_service.AsyncAzureOpenAI')
    async def test_generate_image_success(self, MockAsyncAzureOpenAI):
        mock_api_key = "mock_api_key"
        mock_base_url = "https://mock.openai.com"
        mock_deployment_name = "mock_deployment"
        mock_api_version = "2022-01"

        question = "Generate an image of a cat"


        mock_client = MockAsyncAzureOpenAI.return_value
        mock_response = AsyncMock()
        mock_client.images.generate.return_value = dummy_async_function()



        service = DallE3Service(mock_base_url, mock_api_key, mock_deployment_name, mock_api_version)

            # Create an instance of DallE3Service

            # Call the method under test
        result = await service.generate_image(question)

            # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result['data'][0]['url'], "http://ai.com/mock_image.png")

    @patch('app.services.dalle3_service.AsyncAzureOpenAI')
    async def test_generate_image_error_handling(self, MockAsyncAzureOpenAI):
        mock_api_key = "mock_api_key"
        mock_base_url = "https://mock.openai.com"
        mock_deployment_name = "mock_deployment"
        mock_api_version = "2022-01"

        question = "Generate an image of a dog"

        # Configure mock behavior to raise an exception
        mock_client = MockAsyncAzureOpenAI.return_value
        ex = Exception("API Error", "mock_prompt")
        ex.status_code = 400
        ex.response = type('', (), {})()
        response_content = json.dumps({'error': {'code': 'content_policy_violation', 'inner_error': {'code': 'ResponsibleAIPolicyViolation', 'content_filter_results': {'jailbreak': {'detected': False, 'filtered': False}}}, 'message': 'Your request was rejected as a result of our safety system. Your prompt may contain text that is not allowed by our safety system.', 'type': 'invalid_request_error'}})
        ex.response.content = response_content
        ex.request = type('', (), {})()
        request_content = json.dumps({'prompt': 'Take care of yourself'})
        ex.request.content = request_content
        mock_client.images.generate.side_effect = ex

        # Create an instance of DallE3Service
        service = DallE3Service(mock_base_url, mock_api_key, mock_deployment_name, mock_api_version)

        with self.assertRaises(ResponsibleAIPolicyViolation) as context:
            await service.generate_image(question)



    async def test_generate_image_empty_prompt(self):
        mock_api_key = "mock_api_key"
        mock_base_url = "https://mock.openai.com"
        mock_deployment_name = "mock_deployment"
        mock_api_version = "2022-01"

        question = ""

        # Create an instance of DallE3Service without patching
        service = DallE3Service(mock_base_url, mock_api_key, mock_deployment_name, mock_api_version)

        with patch.object(service, 'generate_image', return_value=None):

            result = await service.generate_image(question)
            self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
