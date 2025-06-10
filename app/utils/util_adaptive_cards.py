import json 


with open("app/resources/adaptive_cards/spinning_wheel.json", "r") as file:
    spinning_wheel_adaptive_card_json = json.load(file)

with open("app/resources/adaptive_cards/confirm_delete.json", "r") as file:
    confirm_delete_adaptive_card_json = json.load(file)

with open("app/resources/adaptive_cards/confirmation_message_delete.json", "r") as file:
    delete_message_adaptive_card_json = json.load(file)

with open("app/resources/adaptive_cards/welcome_data_agreement.json", "r") as file:
    data_agreement_card_json = json.load(file)

with open("app/resources/adaptive_cards/prompt_example.json", "r") as file:
    prompt_example_json = json.load(file)

with open("app/resources/adaptive_cards/image_prompt.json", "r") as file:
    image_prompt = json.load(file)

with open("app/resources/adaptive_cards/followup_prompt.json", "r") as file:
    followup_prompt = json.load(file)