""" import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from flask import Flask
from app.api.bot_handler import bot_handler, bot_messaging_handler

class TestBotHandler(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(bot_handler)
        self.client = self.app.test_client()

    @patch('app.api.blueprints.bot_handler.user_validation_service.validate_tenant_id')
    @patch('app.api.blueprints.bot_handler.user_validation_service.validate_user')
    @patch('app.api.blueprints.bot_handler.cosmos_service.get_interaction_state')
    @patch('app.api.blueprints.bot_handler.authentication_service.refresh_token_if_needed')
    @patch('app.api.blueprints.bot_handler.authentication_service.get_current_token')
    @patch('app.api.blueprints.bot_handler.team_messaging_service.send_welcome_message', new_callable=AsyncMock)
    @patch('app.api.blueprints.bot_handler.cosmos_service.insert_prompt_response_info')
    async def test_incoming_handler_welcome_message(self, insert_prompt_response_info, send_welcome_message, get_current_token, refresh_token_if_needed, get_interaction_state, validate_user, validate_tenant_id):
        validate_tenant_id.return_value = True
        validate_user.return_value = True
        get_interaction_state.return_value = None
        get_current_token.return_value = 'test_token'
        
        response = await self.client.post('/bot_handler', json={
            "type": "message",
            "from": {"aadObjectId": "test_user"},
            "channelData": {"tenant": {"id": "test_tenant"}},
            "text": "hello",
            "serviceUrl": "http://test_service",
            "conversation": {"id": "test_conversation"},
            "id": "test_message_id"
        })

        self.assertEqual(response.status_code, 200)
        send_welcome_message.assert_called_once_with('http://test_service', 'test_conversation', 'test_token')
        insert_prompt_response_info.assert_called_once()
    
    @patch('app.api.blueprints.bot_handler.user_validation_service.validate_tenant_id')
    @patch('app.api.blueprints.bot_handler.user_validation_service.validate_user')
    async def test_incoming_handler_unauthorized(self, validate_user, validate_tenant_id):
        validate_tenant_id.return_value = False
        validate_user.return_value = False

        response = await self.client.post('/bot_handler', json={
            "type": "message",
            "from": {"aadObjectId": "test_user"},
            "channelData": {"tenant": {"id": "test_tenant"}},
            "text": "hello"
        })

        self.assertEqual(response.status_code, 403)

    @patch('app.api.blueprints.bot_handler.get_action_from_data')
    @patch('app.api.blueprints.bot_handler.handle_confirm_accept', new_callable=AsyncMock)
    @patch('app.api.blueprints.bot_handler.handle_confirm_decline', new_callable=AsyncMock)
    @patch('app.api.blueprints.bot_handler.handle_delete', new_callable=AsyncMock)
    @patch('app.api.blueprints.bot_handler.handle_confirm_delete', new_callable=AsyncMock)
    @patch('app.api.blueprints.bot_handler.handle_default_interaction', new_callable=AsyncMock)
    async def test_bot_messaging_handler(self, handle_default_interaction, handle_confirm_delete, handle_delete, handle_confirm_decline, handle_confirm_accept, get_action_from_data):
        data = {
            "type": "message",
            "from": {"aadObjectId": "test_user"},
            "channelData": {"tenant": {"id": "test_tenant"}},
            "text": "hello",
            "serviceUrl": "http://test_service",
            "conversation": {"id": "test_conversation"},
            "id": "test_message_id"
        }

        get_action_from_data.return_value = "confirm_accept"
        await bot_messaging_handler(data, data['text'], data['from']['aadObjectId'], data['type'], 'test_token')
        handle_confirm_accept.assert_called_once()

        get_action_from_data.return_value = "confirm_decline"
        await bot_messaging_handler(data, data['text'], data['from']['aadObjectId'], data['type'], 'test_token')
        handle_confirm_decline.assert_called_once()

        get_action_from_data.return_value = None
        data['text'] = 'delete'
        await bot_messaging_handler(data, data['text'], data['from']['aadObjectId'], data['type'], 'test_token')
        handle_delete.assert_called_once()

        get_action_from_data.return_value = "confirm_delete"
        await bot_messaging_handler(data, data['text'], data['from']['aadObjectId'], data['type'], 'test_token')
        handle_confirm_delete.assert_called_once()

        get_action_from_data.return_value = None
        data['text'] = 'default'
        await bot_messaging_handler(data, data['text'], data['from']['aadObjectId'], data['type'], 'test_token')
        handle_default_interaction.assert_called_once()

if __name__ == '__main__':
    unittest.main()
 """