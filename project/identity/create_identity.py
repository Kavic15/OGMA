import unicodedata
import string
import random
from add_identity import add_identitiy
from czech_name_generator import generator

def create_identity(iterations):
    for i in range(iterations):
        gender = random.choice(['M', 'F'])
        print(gender)
        # Name
        name = generator.name_giver_czech("F",gender)
        normalized_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
        print(name)

        surname = generator.name_giver_czech("L",gender)
        normalized_surname = unicodedata.normalize('NFKD', surname).encode('ascii', 'ignore').decode('utf-8')
        print(normalized_surname)
        print(surname) 
        # Birth
        birthYear = random.randint(1950, 2012)
        birthMonth = random.randint(1, 12)
        month_days = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        birthDay = random.randint(1, month_days[birthMonth])

        # Format as YYYY-MM-DD string
        birth_date = f"{birthYear}-{birthMonth:02d}-{birthDay:02d}"
        print(birth_date)

        rand_num=''.join(str(random.randint(0, 9)) for _ in range(5))
        email=(str(normalized_name).lower() + "." + str(normalized_surname).lower() + rand_num + "@example.com")
        print(email)

        # Instagram username
        username = f"{normalized_name.lower()}.{normalized_surname.lower()}"
        print(username)

        # Password
        special_chars = '#!$@%'
        all_chars = string.ascii_letters + string.digits + special_chars
        password = ''.join(random.choices(all_chars, k=20))
        print(password)

        add_identitiy(
            name=name,
            surname=surname,
            birth_date=birth_date,
            email=email,
            username=username,
            password=password 
        )