import json
import os

def get_user_email(user_id):
    """Retrieve user email from users.json"""
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("The file users.json was not found.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in users.json.")
    
    users = data.get('users', [])
    
    if user_id < 0 or user_id >= len(users):
        raise ValueError("Invalid user ID provided.")
    
    user = users[user_id]
    email = user.get('email')
    
    if email is None:
        raise KeyError("Email not found for the given user ID.")
    
    return email

def get_IG_username_by_ID(user_id):
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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

def get_FB_username_by_ID(user_id):
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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
    facebook = social_media.get('facebook', {})
    username = facebook.get('username')
    
    if username is None:
        raise KeyError("Username not found for the given user ID.")
    
    return username

def get_FB_password_by_ID(user_id):
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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
    facebook = social_media.get('facebook', {})
    password = facebook.get('password')
    
    if password is None:
        raise KeyError("Password not found for the given user ID.")
    
    return password

def get_X_username_by_ID(user_id):
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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
    X = social_media.get('X', {})
    username = X.get('username')
    
    if username is None:
        raise KeyError("Username not found for the given user ID.")
    
    return username

def get_X_password_by_ID(user_id):
    try:
        current_dir = os.path.dirname(__file__)
        json_path = os.path.join(current_dir, 'users.json')
        
        with open(json_path, 'r') as file:
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
    X = social_media.get('X', {})
    password = X.get('password')
    
    if password is None:
        raise KeyError("Password not found for the given user ID.")
    
    return password