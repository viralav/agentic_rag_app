import datetime
from azure.cosmos import CosmosClient, PartitionKey

from app.config.set_logger import set_logger

logger = set_logger(name=__name__)

class CosmosService:
    def __init__(self, endpoint, key, database_name, user_interactions_container_name, images_info_container_name, reply_to_id_container_name):
        self.client = CosmosClient(endpoint, key)
        self.database = self.client.get_database_client(database_name)
        self.interactions_container = self.database.get_container_client(user_interactions_container_name)
        self.images_info_container = self.database.get_container_client(images_info_container_name)
        self.reply_to_id_container = self.database.get_container_client(reply_to_id_container_name)
        logger.info(f"CosmosService initialized for database: {database_name}")

    # Methods for user_interactions_container

    def get_interaction_state(self, user_id):
        try:
            query = f"SELECT c.state_of_welcome_message_sent FROM c WHERE c.user_id = '{user_id}'"
            result = list(self.interactions_container.query_items(query, partition_key=user_id))
            if result:
                state = result[0].get("state_of_welcome_message_sent")
                logger.debug(f"Interaction state for user_id {user_id}: {state}")
                return state
            else:
                logger.debug(f"No interaction state found for user_id {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching interaction state for user_id {user_id}: {str(e)}")
            return None

    def get_data_agreement_state(self, user_id):
        try:
            query = f"SELECT c.state_of_data_agreement FROM c WHERE c.user_id = '{user_id}'"
            result = list(self.interactions_container.query_items(query, partition_key=user_id))
            if result:
                state = result[0].get("state_of_data_agreement")
                logger.debug(f"Data agreement state for user_id {user_id}: {state}")
                return state
            else:
                logger.debug(f"No data agreement state found for user_id {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching data agreement state for user_id {user_id}: {str(e)}")
            return None

    def get_message_ids(self, user_id):
        try:
            query = f"SELECT c.teams_message_id FROM c WHERE c.user_id = '{user_id}'"
            message_id_list = list(self.interactions_container.query_items(query, partition_key=user_id))
            message_ids = [item.get('teams_message_id') for item in message_id_list]
            logger.debug(f"Message IDs for user_id {user_id}: {message_ids}")
            return message_ids
        except Exception as e:
            logger.error(f"Error fetching message IDs for user_id {user_id}: {str(e)}")
            return []

    def get_interaction_type(self, user_id):
        try:
            query = f"SELECT TOP 1 c.interaction_type FROM c WHERE c.user_id = '{user_id}' ORDER BY c.timestamp DESC"
            interaction_type_list = list(self.interactions_container.query_items(query, partition_key=user_id))
            if interaction_type_list:
                interaction_type = interaction_type_list[0].get('interaction_type')
                logger.debug(f"Latest interaction type for user_id {user_id}: {interaction_type}")
                return interaction_type
            else:
                logger.debug(f"No interaction type found for user_id {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching interaction type for user_id {user_id}: {str(e)}")
            return None

    def delete_conversation(self, user_id):
        try:
            response = self.interactions_container.delete_all_items_by_partition_key(user_id)
            logger.info(f"Deleted conversation history for user_id: {user_id}")
            return response
        except Exception as e:
            logger.error(f"Error deleting conversation history for user_id {user_id}: {str(e)}")
            return None

    def update_data_agreement_state(self, user_id, accepted=False, declined=False, deleted=False):
        try:
            if accepted:
                new_state = "accepted"
            elif declined:
                new_state = "declined"
            elif deleted:
                new_state = "deleted"
            else:
                raise ValueError("At least one state flag (accepted, declined, deleted) must be True")
            
            query = f"SELECT * FROM c WHERE c.user_id = '{user_id}'"
            result = list(self.interactions_container.query_items(query, partition_key=user_id))
            
            if result:
                item = result[0]
                item["timestamp"] = datetime.datetime.utcnow().isoformat()
                item["state_of_data_agreement"] = new_state
                self.interactions_container.upsert_item(body=item)
                logger.info(f"Updated data agreement state for user_id {user_id} to {new_state}")
            else:
                logger.debug(f"No item found to update for user_id {user_id}")
        except ValueError as ve:
            logger.error(f"Value error in updating data agreement state for user_id {user_id}: {str(ve)}")
        except Exception as e:
            logger.error(f"Error updating data agreement state for user_id {user_id}: {str(e)}")

    def insert_prompt_response_info(self, item):
        try:
            self.interactions_container.create_item(body=item)
            logger.info(f"Inserted prompt-response interaction for user_id: {item['user_id']}")
            return True
        except Exception as e:
            logger.error(f"Error inserting prompt-response interaction for user_id {item['user_id']}: {str(e)}")
            return False

    def insert_generated_image_info(self, item):
        try:
            self.images_info_container.create_item(body=item)
            logger.info(f"Inserted generated image info for user_id: {item['user_id']}")
            return True
        except Exception as e:
            logger.error(f"Error inserting generated image info for user_id {item['user_id']}: {str(e)}")
            return False

    def get_latest_conversations(self, user_id, top_n=3):
        try:
            query = f"SELECT TOP {top_n} c.prompt, c.response FROM c WHERE c.user_id = '{user_id}' ORDER BY c.timestamp DESC"
            result = list(self.interactions_container.query_items(query, partition_key=user_id))
            logger.debug(f"Latest {top_n} conversations for user_id {user_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"Error fetching latest conversations for user_id {user_id}: {str(e)}")
            return []

    def insert_reply_to_id(self, item) :
        try:
            self.reply_to_id_container.create_item(body=item)
            logger.info(f"Inserted reply_to_id info for user_id: {item['user_id']}")
            return True
        except Exception as e:
            logger.error(f"Error inserting reply_to_id  info for user_id {item['user_id']}: {str(e)}")
            return False  
    
    
    def get_reply_to_id(self, reply_to_id, user_id, prompt_input) :
        try:
            query = "SELECT c.id FROM c WHERE c.reply_to_id = @reply_to_id and c.prompt_input = @prompt_input"
            parameters = [{"name": "@reply_to_id", "value": reply_to_id},
                          {"name": "@prompt_input", "value": prompt_input}]
        
            result = list(self.reply_to_id_container.query_items(
            query=query,
            parameters=parameters,
            partition_key=user_id
            ))
        
            if result:
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error fetching reply_to_id {reply_to_id} for user_id {user_id}: {str(e)}")
            return None

    def delete_reply_to_id(self, reply_to_id, user_id):
        try:
            query = "SELECT c.id FROM c WHERE c.reply_to_id = @reply_to_id"
            parameters = [{"name": "@reply_to_id", "value": reply_to_id}]
            
            result = list(self.reply_to_id_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))
            
            if result:
                item_id = result[0]['id']
                
                self.reply_to_id_container.delete_item(
                    item=item_id,
                    partition_key=user_id
                )
                return True 
            else:
                return False
        
        except Exception as e:
            logger.error(f"Error deleting reply_to_id {reply_to_id} for user_id {user_id}: {str(e)}")
            return None