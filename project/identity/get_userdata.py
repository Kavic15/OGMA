import json

def get_IG_username_by_ID(user_id):
    try:
        with open('identity/users.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("The file users.json was not found.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in users.json.")
    
    users = data.get('users', [])
    
    if user_id < 0 or user_id >= len(users):
        raise ValueError("Invalid user ID provided.")
    
    user = users[user_id]
    social_media = user.get('social_media', {})
    instagram = social_media.get('instagram', {})
    username = instagram.get('username')
    
    if username is None:
        raise KeyError("Username not found for the given user ID.")
    
    return username

def get_IG_password_by_ID(user_id):
    try:
        with open('identity/users.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("The file users.json was not found.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in users.json.")
    
    users = data.get('users', [])
    
    if user_id < 0 or user_id >= len(users):
        raise ValueError("Invalid user ID provided.")
    
    user = users[user_id]
    social_media = user.get('social_media', {})
    instagram = social_media.get('instagram', {})
    password = instagram.get('password')
    
    if password is None:
        raise KeyError("Password not found for the given user ID.")
    
    return password