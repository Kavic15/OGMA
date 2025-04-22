import json

def add_identitiy(
        name, surname, email, birth_date,
        username, password,
        filename='identity.users.json'):
    # Load existing data from the JSON file
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"users": []}
    
    # Determine the next available ID
    users = data.get('users', [])
    if users:
        max_id = max(user['ID'] for user in users)
    else:
        max_id = 0
    new_id = max_id + 1
    
    # Create the new user dictionary
    new_user = {
        "ID": new_id,
        "name": str( name),
        "surname": str(surname),
        "email": email,
        "birth_date": birth_date,
        "social_media": {
            "instagram": {
                "username": username,
                "password": password
            },
            "facebook": {
                "username": username,
                "password": password
            },
            "x": {
                "username": username,
                "password": password
            }
        }
    }
    
    # Append the new user and save to file
    data['users'].append(new_user)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)