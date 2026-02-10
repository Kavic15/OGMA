from src.core.base_bot import BaseBot
import time
import os

# Jednoduchý test, zda se vytvoří profil
print("--- TEST ZAČÍNÁ ---")

# Inicializace bota (použije ID "test_user")
try:
    bot = BaseBot(headless=False, user_id="test_user")
    
    print("Otevírám Google...")
    bot.page.get("https://www.google.com")
    
    print("Čekám 5 sekund (nyní zkontroluj složku profiles/test_user)...")
    time.sleep(5)
    
    print("Zavírám bota...")
    bot.close()
    print("--- TEST DOKONČEN ---")
    
    # Kontrola
    profile_dir = os.path.join(os.getcwd(), 'profiles', 'test_user')
    if os.path.exists(profile_dir) and len(os.listdir(profile_dir)) > 0:
        print(f"✅ ÚSPĚCH! Složka profilu není prázdná: {profile_dir}")
        print(f"Počet souborů/složek: {len(os.listdir(profile_dir))}")
    else:
        print(f"❌ CHYBA! Složka profilu je stále prázdná: {profile_dir}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")