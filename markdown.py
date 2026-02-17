import os

# Konfigurace - uprav podle potřeby
EXCLUDE_DIRS = {'.git', 'venv', '.venv', '__pycache__', '.idea', '.vscode'}
EXCLUDE_FILES = {'projekt_pro_ai.md', '.gitignore', 'users.json', 'markdown.py', 'diary.txt', 'pozn.txt', 'top50.txt'}
EXTENSIONS = {'.py', '.txt', '.yaml', '.yml', '.sql', '.html', '.css'}

def project_to_markdown(output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for root, dirs, files in os.walk('.'):
            # Odfiltrování nepotřebných složek
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if file in EXCLUDE_FILES or not any(file.endswith(ext) for ext in EXTENSIONS):
                    continue
                
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, '.')
                
                # Zápis do Markdownu
                outfile.write(f"## Soubor: {relative_path}\n")
                outfile.write(f"```{file.split('.')[-1]}\n") # detekce jazyka podle přípony
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        outfile.write(f.read())
                except Exception as e:
                    outfile.write(f"Chyba při čtení souboru: {e}")
                outfile.write("\n```\n\n")

if __name__ == "__main__":
    project_to_markdown('projekt_pro_ai.md')
    print("Hotovo! Tvůj kód je v souboru projekt_pro_ai.md")