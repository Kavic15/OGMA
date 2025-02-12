import json

def load_config(file_path="config.json"):
    with open(file_path, "r") as file:
        return json.load(file)