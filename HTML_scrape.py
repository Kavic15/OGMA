import requests

def get_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

# Get URL input from user
user_url = "https://www.instagram.com/p/CsxmtSZIdSS/?hl=en&img_index=1"
html_content = get_html(user_url)

if html_content.startswith("Error:"):
    print(html_content)
else:
    # Get filename input from user
    filename = "IG_post_HTML.html"
    
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(html_content)
        print(f"HTML content successfully saved to {filename}")
    except IOError as e:
        print(f"File error: {str(e)}")