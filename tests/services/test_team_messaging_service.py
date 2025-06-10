import os
import unittest
from unittest import mock
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.team_messaging_service import TeamsMessagingService

# Mock the utility functions imported from util_adaptive_cards
spinning_wheel_adaptive_card_json = MagicMock()
confirm_delete_adaptive_card_json = MagicMock()
delete_message_adaptive_card_json = MagicMock()
data_agreement_card_json = MagicMock()
prompt_example_json = MagicMock()
display_image = MagicMock()
image_prompt = MagicMock()

@mock.patch.dict(os.environ, {"APP_INSIGHTS_KEY" : "6e0925b6-e53c-49a9-a624-48c0a286a4aa"})
class TestTeamsMessagingService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.service = TeamsMessagingService()
        self.service_url = "https://dummy_service_url"
        self.conversation_id = "dummy_conversation_id"
        self.jwt_token = "dummy_jwt_token"
        self.activity_id = "dummy_activity_id"
        self.message_text = "dummy_message_text"
        self.image_url = "https://dummy_image_url"
        self.text = "dummy_text"
        self.description = "dummy_description"
        self.payload = {"type": "message", "text": self.message_text}

    @patch('aiohttp.ClientSession')
    async def test_send_message_success(self, MockClientSession):
        # Arrange
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"id": "123"})
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response
        MockClientSession.return_value.__aenter__.return_value = mock_session

        # Act
        result = await self.service.send_message(self.service_url, self.conversation_id, self.jwt_token, self.payload)

        # Assert
        self.assertEqual(result, "123")
        MockClientSession.assert_called_once()
        mock_session.post.assert_called_once_with(
            f"{self.service_url}/v3/conversations/{self.conversation_id}/activities",
            headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
            json=self.payload
        )
        mock_response.raise_for_status.assert_called_once()


    @patch('app.services.team_messaging_service.spinning_wheel_adaptive_card_json', new=spinning_wheel_adaptive_card_json)
    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_loading_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_loading_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": spinning_wheel_adaptive_card_json
                }]
            }
        )

    @patch('app.services.team_messaging_service.data_agreement_card_json', new=data_agreement_card_json)
    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_welcome_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_welcome_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": data_agreement_card_json
                }]
            }
        )

    @patch('app.services.team_messaging_service.prompt_example_json', new=prompt_example_json)
    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_initial_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_initial_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": prompt_example_json
                }]
            }
        )

    @patch.object(TeamsMessagingService, 'update_message', new_callable=AsyncMock)
    async def test_send_openai_response(self, mock_update_message):
        # Arrange
        mock_update_message.return_value = "message_id"

        # Act
        result = await self.service.send_openai_response(self.service_url, self.conversation_id, self.activity_id, self.message_text, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_update_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.activity_id, self.jwt_token, {
                "type": "message",
                "text": self.message_text,
            }
        )

    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_decline_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_decline_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "text": "🙏 Thank you for letting us know. If you change your mind, please type '**accept**' in this chat to start using our service. We're happy to help!"
            }
        )

    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_pending_reminder_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_pending_reminder_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "text": "🙏 Dear User, Your data agreement is still **pending**. Please type '**accept**' in this chat to start using our service. We're happy to help!"
            }
        )

    @patch('app.services.team_messaging_service.confirm_delete_adaptive_card_json', new=confirm_delete_adaptive_card_json)
    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_confirm_delete_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_confirm_delete_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": confirm_delete_adaptive_card_json
                }]
            }
        )

    @patch('app.services.team_messaging_service.delete_message_adaptive_card_json', new=delete_message_adaptive_card_json)
    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_deleted_confirmation_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_deleted_confirmation_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": delete_message_adaptive_card_json
                }]
            }
        )

    @patch('aiohttp.ClientSession')
    async def test_delete_conversation_history_success(self, MockClientSession):
        # Arrange
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.delete.return_value.__aenter__.return_value = mock_response
        MockClientSession.return_value.__aenter__.return_value = mock_session

        # Act
        await self.service.delete_conversation_history(self.service_url, self.conversation_id, self.activity_id, self.jwt_token)

        # Assert
        MockClientSession.assert_called_once()
        mock_session.delete.assert_called_once_with(
            f"{self.service_url}/v3/conversations/{self.conversation_id}/activities/{self.activity_id}",
            headers={"Authorization": f"Bearer {self.jwt_token}"}
        )
        mock_response.raise_for_status.assert_called_once()

    @patch.object(TeamsMessagingService, 'send_message', new_callable=AsyncMock)
    async def test_send_please_select_usecase_message(self, mock_send_message):
        # Arrange
        mock_send_message.return_value = "message_id"

        # Act
        result = await self.service.send_please_select_usecase_message(self.service_url, self.conversation_id, self.jwt_token)

        # Assert
        self.assertEqual(result, "message_id")
        mock_send_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.jwt_token, {
                "type": "message",
                "text": "🙏 Please select an Usecase applicable for your query from Usecase dropdown!"
            }
        )

    @patch('app.services.team_messaging_service.image_prompt', new=image_prompt)
    @patch.object(TeamsMessagingService, 'update_message', new_callable=AsyncMock)
    async def test_send_image_card_response(self, mock_update_message):
        # Arrange
        mock_update_message.return_value = "message_id"
        image_prompt["body"][0]["url"] = self.image_url
        image_prompt["body"][1]["text"] = self.description
        image_prompt["body"][2]["value"] = self.text
        image_prompt["actions"][0]["url"] = self.image_url

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": image_prompt,
                }
            ],
        }

        # Act
        result = await self.service.send_image_card_response(
            self.service_url, self.conversation_id, self.activity_id, self.image_url, self.text, self.description, self.jwt_token
        )

        # Assert
        self.assertEqual(result, "message_id")
        mock_update_message.assert_called_once_with(
            self.service_url, self.conversation_id, self.activity_id, self.jwt_token, payload
        )

if __name__ == '__main__':
    unittest.main()
