import aiohttp
import os

from app.config.constants import IMAGE_EXPIRY_ICON, IMAGE_EXPIRY_MESSAGE
from ..utils.util_adaptive_cards import (
    spinning_wheel_adaptive_card_json,
    confirm_delete_adaptive_card_json,
    delete_message_adaptive_card_json,
    data_agreement_card_json,
    prompt_example_json,
    image_prompt,
    followup_prompt
)

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class TeamsMessagingService:
    async def send_message(self, service_url, conversation_id, jwt_token, payload):
        endpoint = f"{service_url}/v3/conversations/{conversation_id}/activities"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }
        logger.debug(f"Sending message to endpoint: {endpoint} with payload: {payload}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(endpoint, headers=headers, json=payload) as response:
                    response_data = await response.json()
                    logger.debug(f"Response from Teams: {response_data}")
                    response.raise_for_status()
                    return response_data.get("id")
            except aiohttp.ClientResponseError as ex:
                logger.error(f"Client response error while sending message: {ex}")
                raise  # Re-raise the exception for the test to catch it
            except Exception as ex:
                logger.error(f"Unexpected error while sending message: {ex}")
                raise  # Raising the exception to indicate failure in sending message

    async def update_message(self, service_url, conversation_id, activity_id, jwt_token, payload):
        endpoint = f"{service_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        }
        logger.debug(f"Updating message at endpoint: {endpoint} with payload: {payload}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.put(endpoint, headers=headers, json=payload) as response:
                    response_data = await response.json()
                    logger.debug(f"Response from Teams: {response_data}")
                    response.raise_for_status()
                    return response_data.get("id")
            except aiohttp.ClientResponseError as ex:
                logger.error(f"Client response error while updating message: {ex}")
                raise  # Re-raise the exception for the test to catch it
            except Exception as ex:
                logger.error(f"Unexpected error while updating message: {ex}")
                raise  # Raising the exception to indicate failure in updating message

    async def send_loading_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending loading message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": spinning_wheel_adaptive_card_json,
                }
            ],
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)
    

    async def send_openai_response(self, service_url, conversation_id, activity_id, message_text, jwt_token):
        logger.info(f"Sending OpenAI response to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "text": message_text,
        }
        return await self.update_message(service_url, conversation_id, activity_id, jwt_token, payload)

    async def send_welcome_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending welcome message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": data_agreement_card_json,
                }
            ],
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_initial_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending initial message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": prompt_example_json,
                }
            ],
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_decline_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending decline message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "text": "🙏 Thank you for letting us know. If you change your mind, please type '**accept**' in this chat to start using our service. We're happy to help!"
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_pending_reminder_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending pending reminder message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "text": "🙏 Dear User, Your data agreement is still **pending**. Please type '**accept**' in this chat to start using our service. We're happy to help!"
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_confirm_delete_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending confirm delete message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": confirm_delete_adaptive_card_json,
                }
            ],
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_deleted_confirmation_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending deleted confirmation message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": delete_message_adaptive_card_json,
                }
            ],
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def delete_conversation_history(self, service_url, conversation_id, message_id, jwt_token):
        logger.info(f"Deleting conversation history for conversation: {conversation_id}, message: {message_id}")
        endpoint = f"{service_url}/v3/conversations/{conversation_id}/activities/{message_id}"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.delete(endpoint, headers=headers) as response:
                    response.raise_for_status()
                    logger.info(f"Successfully deleted conversation history for message: {message_id}")
            except aiohttp.ClientResponseError as ex:
                logger.error(f"Client response error while deleting message: {ex}")
                raise  # Re-raise the exception for the test to catch it
            except Exception as ex:
                logger.error(f"Unexpected error while deleting message: {ex}")
                raise  # Raising the exception to indicate failure in deleting message

    async def send_please_select_usecase_message(self, service_url, conversation_id, jwt_token):
        logger.info(f"Sending please select usecase message to conversation: {conversation_id}")
        payload = {
            "type": "message",
            "text": "🙏 Please select an Usecase applicable for your query from Usecase dropdown!"
        }
        return await self.send_message(service_url, conversation_id, jwt_token, payload)

    async def send_image_card_response(self, service_url, conversation_id, activity_id, image_url, text, description, jwt_token):
        logger.info(f"Sending image card response to conversation: {conversation_id}")
        image_prompt["body"][0]["items"][0]["url"] = image_url
        image_prompt["body"][0]["items"][1]["value"] = text
        if os.getenv(IMAGE_EXPIRY_ICON):
            image_prompt["body"][0]["items"][2]["columns"][0]["items"][0]["url"] = os.getenv(IMAGE_EXPIRY_ICON)
        if os.getenv(IMAGE_EXPIRY_MESSAGE):
            image_prompt["body"][0]["items"][2]["columns"][1]["items"][0]["text"] = os.getenv(IMAGE_EXPIRY_MESSAGE)
        image_prompt["actions"][0]["url"] = image_url

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": image_prompt,
                }
            ],
        }
        return await self.update_message(service_url, conversation_id, activity_id, jwt_token, payload)
    
    async def send_followup_card_response(self, service_url, conversation_id, activity_id, followup_questions_list, jwt_token):
        logger.info(f"Sending follow up card response to conversation: {conversation_id}")
        logger.debug(f"The followup questions list looks like below: {followup_questions_list}")
        
        for idx, question in enumerate(followup_questions_list):
            followup_prompt["actions"].append({
                "type": "Action.Submit",
                "title": question,
                "data": {
                    "follow_up_question": question
                },
                "style": "positive",
                "wrap": True
            })

        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": followup_prompt,
                }
            ],
        }
        return await self.update_message(service_url, conversation_id, activity_id, jwt_token, payload)
