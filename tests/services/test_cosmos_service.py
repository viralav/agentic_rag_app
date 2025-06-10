import os
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
from app.services.cosmos_service import CosmosService  # Replace with your actual module name
from azure.cosmos import CosmosClient, PartitionKey


@mock.patch.dict(os.environ, {"APP_INSIGHTS_KEY" : "6e0925b6-e53c-49a9-a624-48c0a286a4aa"})
class TestCosmosService(unittest.TestCase):

    @patch('app.services.cosmos_service.CosmosClient') 
    def setUp(self, MockCosmosClient):
        # Mock CosmosClient and container clients
        self.mock_client = MagicMock()
        self.mock_db = MagicMock()
        self.mock_interactions_container = MagicMock()
        self.mock_images_info_container = MagicMock()
        self.reply_to_id_container_name = MagicMock()
        MockCosmosClient.return_value = self.mock_client
        
        # Replace CosmosClient and container clients with mock objects
        self.cosmos_service = CosmosService(
            endpoint="dummy_endpoint",
            key="dummy_key",
            database_name="dummy_database",
            user_interactions_container_name="dummy_user_interactions_container",
            images_info_container_name="dummy_images_info_container",
            reply_to_id_container_name="dummy_reply_to_id_container"
        )
        self.cosmos_service.client = self.mock_client
        self.cosmos_service.database = self.mock_db
        self.cosmos_service.interactions_container = self.mock_interactions_container
        self.cosmos_service.images_info_container = self.mock_images_info_container
        self.cosmos_service.reply_to_id_container = self.reply_to_id_container_name


    def test_get_interaction_state(self):
        user_id = "test_user"
        mock_result = [{"state_of_welcome_message_sent": "sent"}]
        self.mock_interactions_container.query_items.return_value = mock_result
        
        state = self.cosmos_service.get_interaction_state(user_id)
        
        self.assertEqual(state, "sent")
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT c.state_of_welcome_message_sent FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )

    def test_get_interaction_state_no_result(self):
        user_id = "test_user"
        self.mock_interactions_container.query_items.return_value = []
        
        state = self.cosmos_service.get_interaction_state(user_id)
        
        self.assertIsNone(state)
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT c.state_of_welcome_message_sent FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )

    def test_get_data_agreement_state(self):
        user_id = "test_user"
        mock_result = [{"state_of_data_agreement": "accepted"}]
        self.mock_interactions_container.query_items.return_value = mock_result
        
        state = self.cosmos_service.get_data_agreement_state(user_id)
        
        self.assertEqual(state, "accepted")
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT c.state_of_data_agreement FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )

    def test_get_message_ids(self):
        user_id = "test_user"
        mock_result = [{"teams_message_id": "msg_id_1"}, {"teams_message_id": "msg_id_2"}]
        self.mock_interactions_container.query_items.return_value = mock_result
        
        message_ids = self.cosmos_service.get_message_ids(user_id)
        
        self.assertEqual(message_ids, ["msg_id_1", "msg_id_2"])
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT c.teams_message_id FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )

    def test_get_interaction_type(self):
        user_id = "test_user"
        mock_result = [{"interaction_type": "type_A"}]
        self.mock_interactions_container.query_items.return_value = mock_result
        
        interaction_type = self.cosmos_service.get_interaction_type(user_id)
        
        self.assertEqual(interaction_type, "type_A")
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT TOP 1 c.interaction_type FROM c WHERE c.user_id = '{user_id}' ORDER BY c.timestamp DESC",
            partition_key=user_id
        )

    def test_delete_conversation(self):
        user_id = "test_user"
        self.mock_interactions_container.delete_all_items_by_partition_key.return_value = True
        
        response = self.cosmos_service.delete_conversation(user_id)
        
        self.assertTrue(response)
        self.mock_interactions_container.delete_all_items_by_partition_key.assert_called_once_with(user_id)

    def test_update_data_agreement_state_accepted(self):
        user_id = "test_user"
        self.mock_interactions_container.query_items.return_value = [{"user_id": "test_user"}]
        
        self.cosmos_service.update_data_agreement_state(user_id, accepted=True)
        
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT * FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )
        self.mock_interactions_container.upsert_item.assert_called_once()

    def test_update_data_agreement_state_declined(self):
        user_id = "test_user"
        self.mock_interactions_container.query_items.return_value = [{"user_id": "test_user"}]
        
        self.cosmos_service.update_data_agreement_state(user_id, declined=True)
        
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT * FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )
        self.mock_interactions_container.upsert_item.assert_called_once()

    def test_update_data_agreement_state_deleted(self):
        user_id = "test_user"
        self.mock_interactions_container.query_items.return_value = [{"user_id": "test_user"}]
        
        self.cosmos_service.update_data_agreement_state(user_id, deleted=True)
        
        self.mock_interactions_container.query_items.assert_called_once_with(
            f"SELECT * FROM c WHERE c.user_id = '{user_id}'",
            partition_key=user_id
        )
        self.mock_interactions_container.upsert_item.assert_called_once()

    def test_insert_prompt_response_info(self):
        item = {"user_id": "test_user", "response": "test_response"}
        
        result = self.cosmos_service.insert_prompt_response_info(item)
        
        self.assertTrue(result)
        self.mock_interactions_container.create_item.assert_called_once_with(body=item)


    def test_insert_generated_image_info(self):
        item = {"user_id": "test_user", "image_url": "test_image_url"}
        
        result = self.cosmos_service.insert_generated_image_info(item)
        
        self.assertTrue(result)
        self.mock_images_info_container.create_item.assert_called_once_with(body=item)

if __name__ == '__main__':
    unittest.main()
