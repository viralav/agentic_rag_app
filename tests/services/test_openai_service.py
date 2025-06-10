import os
import unittest
from unittest import mock
from unittest.mock import AsyncMock, patch
import warnings
from openai import AsyncAzureOpenAI
from app.services.openai_service import OpenAIService  # Replace 'mymodule' with the actual module name where OpenAIService is defined

@mock.patch.dict(os.environ, {"APP_INSIGHTS_KEY" : "6e0925b6-e53c-49a9-a624-48c0a286a4aa"})
class TestOpenAIService(unittest.TestCase):

    @patch('app.services.openai_service.AsyncAzureOpenAI')
    def setUp(self, MockAsyncAzureOpenAI):
        # Mock AsyncAzureOpenAI client
        self.mock_client = AsyncMock()
        self.mock_chat_completions_create = AsyncMock()
        self.mock_client.chat.completions.create = self.mock_chat_completions_create

        # Set the return value of the mocked AsyncAzureOpenAI
        MockAsyncAzureOpenAI.return_value = self.mock_client

        # Initialize OpenAIService with dummy parameters
        self.openai_service = OpenAIService(
            base_url="dummy_base_url",
            api_key="dummy_api_key",
            deployment_name="dummy_deployment_name",
            api_version="dummy_api_version"
        )

    async def test_answer_query_success(self):
        # Arrange
        question = [{"role": "user", "content": "What is the capital of France?"}]
        expected_response = {"choices": [{"message": {"content": "The capital of France is Paris."}}]}
        self.mock_chat_completions_create.return_value = expected_response

        # Act
        response = await self.openai_service.answer_query(question)

        # Assert
        self.assertEqual(response, expected_response)
        self.mock_chat_completions_create.assert_called_once_with(
            model="dummy_deployment_name",
            messages=question
        )

    async def test_answer_query_exception(self):

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Arrange
            question = [{"role": "user", "content": "What is the capital of France?"}]
            self.mock_chat_completions_create.side_effect = Exception("API error")

            # Act
            response = await self.openai_service.answer_query(question)

            # Assert
            self.assertIsNone(response)
            self.mock_chat_completions_create.assert_called_once_with(
                model="dummy_deployment_name",
                messages=question
            )

if __name__ == '__main__':
    unittest.main()
