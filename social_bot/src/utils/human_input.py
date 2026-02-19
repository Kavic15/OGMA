import time
import random

def delay(min_seconds=1.0, max_seconds=3.0):
    """Náhodná prodleva mezi akcemi."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_typing(locator, text):
    """
    Simuluje psaní člověka pro Playwright Locator s variabilním zpožděním.
    Slouží jako alternativa k nativnímu locator.press_sequentially(text, delay=150),
    pokud je vyžadována vyšší úroveň simulace (zcela náhodné pauzy mezi znaky).
    """
    try:
        locator.fill("") # Vyčištění pole před zápisem
        for char in text:
            # press_sequentially jednoho znaku s náhodnou mezní pauzou
            locator.press_sequentially(char, delay=int(random.uniform(10, 50)))
            time.sleep(random.uniform(0.05, 0.25))
    except Exception as e:
        print(f"[DEBUG] Chyba při human_typing: {e}")

def random_mouse_movement(page=None):
    """
    Generuje náhodné pohyby myší napříč viewportem.
    Využívá Playwright page.mouse API pro zvýšení důvěryhodnosti (stealth).
    """
    if not page:
        return
        
    try:
        viewport = page.viewport_size
        if not viewport:
            # Fallback hodnoty, pokud viewport není detekován
            width, height = 1280, 720
        else:
            width = viewport['width']
            height = viewport['height']
            
        # Provede 2 až 5 náhodných křivek/pohybů
        for _ in range(random.randint(2, 5)):
            target_x = random.randint(0, width)
            target_y = random.randint(0, height)
            
            # steps určuje plynulost (počet mezikroků při pohybu kurzoru)
            page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
            time.sleep(random.uniform(0.1, 0.4))
            
    except Exception:
        pass