from flask import Blueprint, request, jsonify
import datetime
import traceback
import re
import uuid
import os

from app.services.cosmos_service import CosmosService
from app.services.authentication_service import AuthenticationService
from app.services.user_validation_service import UserValidationService
from app.services.team_messaging_service import TeamsMessagingService
from app.services.azure_blob_service import AzureBlobService
from app.services.openai_service import OpenAIService
from app.services.dalle3_service import DallE3Service
from app.services.token_validation_service import TokenValidationService
from app.agents.agent_state import get_llm_response_from_state
from app.agents.agent_workflow import define_agent_workflow
from app.exceptions.custom_exceptions import DataAgreementException, InvalidVectorIndex, DefaultInteractionException

from app.config.set_logger import set_logger

from app.utils.util_url_generator import UtilUrlGenerator
from app.utils.util_helper_methods import HelperMethods

from app.config.constants import (COSMOS_HOST, COSMOS_KEY, COSMOS_DATABASE, COSMOS_USER_INTERACTIONS_CONTAINER, COSMOS_IMAGES_INFO_CONTAINER, COSMOS_REPLY_TO_ID_CONTAINER,
                              MICROSOFT_APP_TYPE, MICROSOFT_TENANT_ID, MICROSOFT_APP_ID, MICROSOFT_APP_SECRET, 
                              BLOB_ACCOUNT_NAME, BLOB_ACCOUNT_KEY, BLOB_CONTAINER_NAME, 
                              OPEN_AI_BASE_URL, OPEN_AI_KEY, OPEN_AI_DEPLOYMENT_NAME, OPEN_AI_VERSION, OPENAI_INTERACTION_LIST,
                              OPEN_AI_DALLE_DEPLOYMENT_NAME, ENTITY_INDEX_LIST, TOP_CHAT_HISTORY)
from app.utils.utils_openai_prompt import GENERAL_OPENAI_ERROR, INVALID_INDEX_ERROR_MESSAGE

bot_handler = Blueprint('teams', __name__)

logger = set_logger(name=__name__)
# Initialize services
cosmos_service = CosmosService(os.getenv(COSMOS_HOST), os.getenv(COSMOS_KEY), os.getenv(COSMOS_DATABASE), os.getenv(COSMOS_USER_INTERACTIONS_CONTAINER), os.getenv(COSMOS_IMAGES_INFO_CONTAINER), os.getenv(COSMOS_REPLY_TO_ID_CONTAINER))
token_validation_service = TokenValidationService(os.getenv(MICROSOFT_TENANT_ID))
authentication_service = AuthenticationService(os.getenv(MICROSOFT_TENANT_ID), os.getenv(MICROSOFT_APP_ID), os.getenv(MICROSOFT_APP_SECRET), token_validation_service)
user_validation_service = UserValidationService(os.getenv(MICROSOFT_TENANT_ID), os.getenv(MICROSOFT_APP_ID), os.getenv(MICROSOFT_APP_SECRET))
team_messaging_service = TeamsMessagingService()
azure_blob_service = AzureBlobService(os.getenv(BLOB_ACCOUNT_NAME), os.getenv(BLOB_ACCOUNT_KEY), os.getenv(BLOB_CONTAINER_NAME))
openai_service = OpenAIService(UtilUrlGenerator.create_open_ai_url(os.getenv(OPEN_AI_BASE_URL), os.getenv(OPEN_AI_DEPLOYMENT_NAME)), os.getenv(OPEN_AI_KEY), os.getenv(OPEN_AI_DEPLOYMENT_NAME), os.getenv(OPEN_AI_VERSION))
dalle3_service = DallE3Service(UtilUrlGenerator.create_open_ai_url(os.getenv(OPEN_AI_BASE_URL), os.getenv(OPEN_AI_DALLE_DEPLOYMENT_NAME)) , os.getenv(OPEN_AI_KEY), os.getenv(OPEN_AI_DALLE_DEPLOYMENT_NAME), os.getenv(OPEN_AI_VERSION))

@bot_handler.route('/bot_handler', methods=['POST'])
async def incoming_handler():
    data = request.get_json()
    logger.info(f"Incoming data: {data}", extra=HelperMethods.add_logging_context(data))
    reply_to_id = data.get("replyToId", "")
    chat_scope = data.get("type", "")
    aad_object_id = data['from']['aadObjectId']
    tenant_id = data["channelData"]["tenant"]["id"]
    text = data.get("text", "")
    jwt_token = ""

    if (reply_to_id != "") :
        image_prompt = ""
        if "value" in data and "prompt-input" in data["value"] :
            image_prompt = data["value"]["prompt-input"]
        check_reply_to_id = cosmos_service.get_reply_to_id(reply_to_id, aad_object_id, image_prompt)
        if check_reply_to_id : 
            return ""
        else :
            cosmos_service.insert_reply_to_id({"id": str(uuid.uuid4()),
                                               "user_id": aad_object_id,
                                               "reply_to_id": reply_to_id,
                                               "prompt_input" : image_prompt,
                                               "timestamp": datetime.datetime.utcnow().isoformat()})

    if not user_validation_service.validate_tenant_id(tenant_id) or not user_validation_service.validate_user(aad_object_id):
        logger.error(f"Unauthorized access attempt. User ID: {aad_object_id}, Tenant ID: {tenant_id}", extra=HelperMethods.add_logging_context(data))
        return "Unauthorized access attempt", 403

    text = data.get("text", "")
    interaction_state = cosmos_service.get_interaction_state(aad_object_id)
    authentication_service.refresh_token_if_needed()
    jwt_token = authentication_service.get_current_token()
    logger.info(f"Interaction state fetched for user ID {aad_object_id} is {interaction_state}", extra=HelperMethods.add_logging_context(data))

    user_interaction_data = {
        "id": str(uuid.uuid4()),
        "conversation_id" : data["conversation"]["id"],
        "user_id": aad_object_id,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "state_of_welcome_message_sent": "sent",
        "state_of_data_agreement": "pending",
        "teams_message_id": data["id"],
        "metadata": {},
    }

    if not interaction_state and chat_scope != "event" and chat_scope != "conversationUpdate" :
        await team_messaging_service.send_welcome_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)
        logger.info(f"Welcome message sent for user ID {aad_object_id}", extra=HelperMethods.add_logging_context(data))
        cosmos_service.insert_prompt_response_info(user_interaction_data)
        logger.info(f"Interaction data written into DB for user ID {aad_object_id}", extra=HelperMethods.add_logging_context(data))
    elif chat_scope == "message":
        await bot_messaging_handler(data, text, aad_object_id, chat_scope, jwt_token)
    return ""

async def bot_messaging_handler(data, text, aad_object_id, chat_scope, jwt_token):
    logger.debug("Handling bot_messaging_handler", extra=HelperMethods.add_logging_context(data))
    try:
        action = get_action_from_data(data)
        logger.debug(f'Input action: {action}, Text: {text}', extra=HelperMethods.add_logging_context(data))

        if action == "confirm_accept" or text.rstrip() == "accept":
            await handle_confirm_accept(data, aad_object_id, jwt_token)
        elif action == "confirm_decline" or text.rstrip() == "decline":
            await handle_confirm_decline(data, aad_object_id, jwt_token)
        elif text.rstrip() == "delete":
            await handle_delete(data, jwt_token)
        elif action == "confirm_delete":
            await handle_confirm_delete(data, aad_object_id, jwt_token)
        else:
            await handle_default_interaction(data, aad_object_id, text, chat_scope, jwt_token)
    except Exception as error:
        logger.error("An error occurred in bot_messaging_handler", exc_info=True, extra=HelperMethods.add_logging_context(data))

def get_action_from_data(data):
    value_dict = data.get("value", {})
    return value_dict.get("action")

async def handle_confirm_accept(data, aad_object_id, jwt_token):
    logger.info(f"Handling confirm_accept for user ID {aad_object_id}", extra=HelperMethods.add_logging_context(data))
    await team_messaging_service.send_initial_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)
    cosmos_service.update_data_agreement_state(aad_object_id, accepted=True)

async def handle_confirm_decline(data, aad_object_id, jwt_token):
    logger.info(f"Handling confirm_decline for user ID {aad_object_id}", extra=HelperMethods.add_logging_context(data))
    await team_messaging_service.send_decline_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)
    cosmos_service.update_data_agreement_state(aad_object_id, declined=True)

async def handle_delete(data, jwt_token):
    logger.info("Handling delete action", extra=HelperMethods.add_logging_context(data))
    await team_messaging_service.send_confirm_delete_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)

async def handle_default_interaction(data, aad_object_id, input_text, chat_scope, jwt_token):
    logger.debug("Handling default interaction", extra=HelperMethods.add_logging_context(data))
    data_agreement_state = cosmos_service.get_data_agreement_state(aad_object_id) #"accepted"#
    if data_agreement_state == "accepted":
        activity_id = await team_messaging_service.send_loading_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)
        logger.debug(f"the provided object id is as below: {aad_object_id}")
        chathistory = cosmos_service.get_latest_conversations(aad_object_id, top_n=TOP_CHAT_HISTORY)
        logger.debug(f"The chat history is as below: {chathistory}")
        ####################################################################

        aad_object_id = data["from"]["aadObjectId"]
        tenantid = data["conversation"]["tenantId"]
        user_query = data["text"] if data.get("text") else data["value"]["follow_up_question"]
        bool_upload_index = True #data["bool_upload_index"]
        loading_message_id = None
        try:


            user_query_cleaned = re.sub(r"\s+", " ", user_query)
            try:
                agentic_app = define_agent_workflow().compile()
                # graph_img = agentic_app.get_graph().draw_mermaid_png()
                # with open("graph_image.png", "wb") as f:
                #     f.write(graph_img)
                inputs = {
                    "user_id": aad_object_id,
                    "raw_query": user_query_cleaned,
                    "ambiguity_status": "",
                    "datasource": "",
                    "chat_history": chathistory,
                    "bool_upload_index": bool_upload_index,
                    "allowed_index": ENTITY_INDEX_LIST,
                    "vector_doc": [],
                    "assessment": [],
                    "rephrased_query": "",
                    "filenames": [],
                    "final_answer": "",
                    "awaiting_user_input": False,
                    "error_occurred": False,
                    "image_answer": {},
                    "data": data
                }
                response_message_id, message_text = await stream_updates(
                    agentic_app, inputs, data, loading_message_id, jwt_token, activity_id
                )

                prompt_response_document = {
                    "id": str(uuid.uuid4()),
                    "user_id": data['from']['aadObjectId'],
                    "timestamp_prompted": data["timestamp"],
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "teams_message_id": data["id"],
                    "prompt": user_query_cleaned,
                    "response": message_text,
                    "conversation_type": data["type"],
                    "conversation_id" : data["conversation"]["id"]
                }
                logger.info(f"started update of prompt response")
                cosmos_service.insert_prompt_response_info(prompt_response_document)
                logger.info(f"Prompt response information inserted into Cosmos DB for user ID {data['from']['aadObjectId']}", extra=HelperMethods.add_logging_context(data))

            except Exception as error:
                logger.error("### Error in fetching llm response for query: %s", user_query, traceback.format_exception(error))
                logger.error("Exception: %s", traceback.format_exc())
                llm_response = GENERAL_OPENAI_ERROR
                await team_messaging_service.send_openai_response(
                    data["serviceUrl"],
                    data["conversation"]["id"],
                    loading_message_id,
                    llm_response,
                    jwt_token
                )

        except DataAgreementException as error:
            logger.warning("### Data agreement exception: %s", str(error))
            await team_messaging_service.send_decline_message(
                data["serviceUrl"], data["conversation"]["id"], jwt_token
            )

        except InvalidVectorIndex:
            await team_messaging_service.send_openai_response(
                data["serviceUrl"],
                data["conversation"]["id"],
                loading_message_id,
                INVALID_INDEX_ERROR_MESSAGE,
                jwt_token
            )
        except Exception as error:
            logger.error(
                "### Error in handle_default_interaction %s", str(traceback.format_exc())
            )
            raise DefaultInteractionException(
                "### Failed to handle_default_interaction"
            ) from error
        ####### not needed ###### await get_openai_response(data, input_text, activity_id, aad_object_id, chat_scope, jwt_token)
        ####################################################################
    elif data_agreement_state == "declined":
        await team_messaging_service.send_decline_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)
    else:
        await team_messaging_service.send_pending_reminder_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)

async def handle_confirm_delete(data, aad_object_id, jwt_token):
    logger.info(f"Handling confirm_delete for user ID {aad_object_id}", extra=HelperMethods.add_logging_context(data))
    cosmos_service.delete_conversation(aad_object_id)
    await team_messaging_service.send_deleted_confirmation_message(data["serviceUrl"], data["conversation"]["id"], jwt_token)

async def get_openai_response(data, text, activity_id, aad_object_id, chat_scope, jwt_token):
    logger.debug("Handling get_openai_response", extra=HelperMethods.add_logging_context(data))
    input_type = ''
    if text == '' and "value" in data and "prompt-input" in data["value"] :
        text = data["value"]["prompt-input"]
    try:
        input_type = await openai_service.determine_input_type(text)
    except Exception as ex:
        await print_error_message_to_user(ex, data, activity_id)
    if input_type == "text" :
        await process_conversation_query(data, activity_id,)
    elif input_type == "image" :
        await process_image_query(data, text, activity_id)


async def process_image_query(data, text, activity_id):
    logger.info("Processing image query", extra=HelperMethods.add_logging_context(data))
    service_url = data["serviceUrl"]
    conversation_id = data["conversation"]["id"]
    try:
        response = await dalle3_service.generate_image(text)
        blob_name = azure_blob_service.upload_file(response["data"][0]["url"])
        signed_url = azure_blob_service.generate_sas_url(blob_name)
        revised_prompt = response["data"][0]["revised_prompt"]
        logger.info(f"Image generated and uploaded to blob storage. Blob URL: {signed_url}", extra=HelperMethods.add_logging_context(data))

        authentication_service.refresh_token_if_needed()
        jwt_token = authentication_service.get_current_token()

        await team_messaging_service.send_image_card_response(service_url, conversation_id, activity_id, signed_url, text, revised_prompt, jwt_token)

        prompt_response_document = {
            "id": str(uuid.uuid4()),
            "user_id": data['from']['aadObjectId'],
            "timestamp_prompted": data["timestamp"],
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "teams_message_id": data["id"],
            "prompt": text,
            "revised_prompt": revised_prompt,
            "image_name": blob_name,
            "conversation_type": data["type"],
            "conversation_id" : conversation_id
        }

        cosmos_service.insert_generated_image_info(prompt_response_document)
        logger.info(f"Generated image information inserted into Cosmos DB for user ID {data['from']['aadObjectId']}", extra=HelperMethods.add_logging_context(data))

    except Exception as ex:
       await print_error_message_to_user(ex, data, activity_id)

async def process_conversation_query(data, activity_id):
    logger.info("Processing conversation query", extra=HelperMethods.add_logging_context(data))
    user_id = data['from']['aadObjectId']
    latest_conversations = cosmos_service.get_latest_conversations(user_id, top_n=3)
    reversed_conversations = list(reversed(latest_conversations))
    if "text" in data :
        text = data["text"]
    elif "value" in data and "prompt-input" in data["value"] :
        text = data["value"]["prompt-input"]
        reply_to_id = data.get("replyToId", "")
        if (reply_to_id != ""):
            cosmos_service.delete_reply_to_id(reply_to_id, user_id)

    latest_conversation = reversed_conversations.pop() if reversed_conversations else None

    messages = [
        {"role": "system", "content": "You are an AI assistant powered by GPT-4-o. You can provide detailed information, generate creative text, and engage in informative conversations"}
    ]

    if latest_conversation and "prompt" in latest_conversation and "response" in latest_conversation:
        messages.append({"role": "user", "content": latest_conversation["prompt"]})
        messages.append({"role": "assistant", "content": latest_conversation["response"]})
    messages.append({"role": "user", "content": text})
    service_url = data["serviceUrl"]
    conversation_id = data["conversation"]["id"]
    try:
        openai_response = await openai_service.answer_query(messages)
        authentication_service.refresh_token_if_needed()
        jwt_token = authentication_service.get_current_token()
        await team_messaging_service.send_openai_response(service_url, conversation_id, activity_id, openai_response.choices[0].message.content, jwt_token)
        prompt_response_document = {
        "id": str(uuid.uuid4()),
        "user_id": data['from']['aadObjectId'],
        "timestamp_prompted": data["timestamp"],
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "teams_message_id": data["id"],
        "prompt": text,
        "response": openai_response.choices[0].message.content,
        "prompt_tokens": openai_response.usage.prompt_tokens,
        "completion_tokens": openai_response.usage.completion_tokens,
        "total_tokens": openai_response.usage.total_tokens,
        "conversation_type": data["type"],
        "conversation_id" : conversation_id
        }
        cosmos_service.insert_prompt_response_info(prompt_response_document)
        logger.info(f"Prompt response information inserted into Cosmos DB for user ID {data['from']['aadObjectId']}", extra=HelperMethods.add_logging_context(data))

    except Exception as ex:
        await print_error_message_to_user(ex, data, activity_id)

async def print_error_message_to_user(ex, data, activity_id):
    service_url = data["serviceUrl"]
    conversation_id = data["conversation"]["id"]
    authentication_service.refresh_token_if_needed()
    jwt_token = authentication_service.get_current_token()
    logger.error(f"An error occurred in process_image_query: {ex}", exc_info=True, extra=HelperMethods.add_logging_context(data))
    error_message = ""
    if hasattr(ex, 'type') and ex.type == 'ResponsibleAIPolicyViolation':
        error_message = ex.description
    elif hasattr(ex, 'type') and ex.type == 'OpenAILimitExceeded':
        error_message = ex.description
    else:
        error_message = """An Error occurred while processing your request 🙁 🙁 🙁
                <br/><br/>
                Please try again 🤖 🤖 🤖"""

    await team_messaging_service.send_openai_response(service_url, conversation_id, activity_id, error_message, jwt_token)

async def stream_updates(agentic_app, inputs, data, message_id, jwt_token, activity_id):
    last_valid_response = None
    last_valid_node = None
    async for output in agentic_app.astream(
        inputs, {"recursion_limit": 8}, stream_mode="updates"
    ):
        for key, value in output.items():
            logger.debug(f"Processing node: {key}")

            if key in (
                "vector_generate",
                "web_based_answer",
            ):
                message_text = get_llm_response_from_state(value)

                if message_text:
                    last_valid_response = message_text
                    last_valid_node = key

            if key in (
                "followup_ambiguous_queries",
                "generate_followup_question",
            ):
                message_text = get_llm_response_from_state(value)

                followup_questions_list = re.findall(r'`([^`]*)`', message_text)

                final_answer_id = await team_messaging_service.send_followup_card_response(
                    data["serviceUrl"], 
                    data["conversation"]["id"], 
                    activity_id, 
                    followup_questions_list,
                    jwt_token
                )
                return final_answer_id, "".join(followup_questions_list)

            if key in ("image_based_answer", ):
                logger.info(f"The value provided for this node is as below: {value}")
                revised_prompt = value["final_answer"]["revised_prompt"]
                prompt_response_document = {
                    "id": str(uuid.uuid4()),
                    "user_id": data['from']['aadObjectId'],
                    "timestamp_prompted": data["timestamp"],
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "teams_message_id": data["id"],
                    "prompt": data["text"],
                    "revised_prompt": revised_prompt,
                    "image_name": value["final_answer"]["blob_name"],
                    "conversation_type": data["type"],
                    "conversation_id" : data["conversation"]["id"]
                }

                cosmos_service.insert_generated_image_info(prompt_response_document)
                logger.info(f"Generated image information inserted into Cosmos DB for user ID {data['from']['aadObjectId']}", extra=HelperMethods.add_logging_context(data))

                final_answer_id = await team_messaging_service.send_image_card_response(
                    data["serviceUrl"], 
                    data["conversation"]["id"], 
                    activity_id, 
                    value["final_answer"]["signed_url"], 
                    data["text"], 
                    revised_prompt, 
                    jwt_token
                )
                return final_answer_id, data["text"]
            
            if "error_occurred" in value and value["error_occurred"]:
                logger.debug(f"Error state detected: {value['error_occurred']}")
                logger.info(f"Sending Error response from node: {last_valid_node}")
                if value["final_answer"]:
                    error_message = value["final_answer"]
                else:
                    error_message = "An error occurred while processing your request. Would you like to try again or ask something else?"
                final_answer_id = await team_messaging_service.send_openai_response(
                    data["serviceUrl"], 
                    data["conversation"]["id"], 
                    activity_id, 
                    value["final_answer"], 
                    jwt_token
                )
                return final_answer_id, error_message

    if last_valid_response:

        prompt_response_document = {
            "id": str(uuid.uuid4()),
            "user_id": data['from']['aadObjectId'],
            "timestamp_prompted": data["timestamp"],
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "teams_message_id": data["id"],
            "prompt": data["text"]  if data.get("text") else data["value"]["follow_up_question"],
            "response": last_valid_response,
            "conversation_type": data["type"],
            "conversation_id" : data["conversation"]["id"]
        }
        cosmos_service.insert_prompt_response_info(prompt_response_document)
        logger.info(f"Prompt response information inserted into Cosmos DB for user ID {data['from']['aadObjectId']}", extra=HelperMethods.add_logging_context(data))

        logger.info(f"Sending final response from node: {last_valid_node}")
        final_answer_id = await team_messaging_service.send_openai_response(
            data["serviceUrl"], 
            data["conversation"]["id"], 
            activity_id, 
            last_valid_response, 
            jwt_token
        )
        return final_answer_id, last_valid_response
    logger.warning("No response generated in workflow")
    return message_id, "No response generated in workflow"