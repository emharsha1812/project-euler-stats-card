# api/euler-stats.py
from flask import Flask, request, make_response, render_template_string
import requests
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

app = Flask(__name__)

# Set up Jinja2 environment to load templates from the 'templates' directory
# Correct path relative to this file's location
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates') # Goes up one level from 'api' then into 'templates'
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml', 'svg']) # Enable autoescaping for SVG
)

def get_euler_stats(username):
    """Fetches and parses stats from Project Euler's .txt profile."""
    url = f"https://projecteuler.net/profile/{username}.txt"
    try:
        response = requests.get(url, timeout=10) # Add a timeout
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

        content = response.text.strip()
        lines = content.split('\n')

        if not lines:
            return None, "No data found in profile file"

        # Expected format (commas may vary slightly, check your own .txt):
        # Username,Country,Language,SolvedCount,Level,JoinedDate,LastSeen,SolvedIDs...
        main_stats_line = lines[0]
        parts = [p.strip() for p in main_stats_line.split(',')]

        # Find solved count and level (adjust indices if necessary)
        solved_count = None
        level = None
        try:
            # Heuristic: Find the first purely numeric entry after potential non-numeric ones
            # This is fragile if PE changes format. A more robust parser might be needed.
            potential_numbers = []
            for part in parts[1:]: # Skip username
                if part.isdigit():
                    potential_numbers.append(int(part))

            if len(potential_numbers) >= 2:
                 # Common order: SolvedCount, Level
                 # Check if the numbers make sense (e.g., level usually lower than solved count)
                 # This is just a guess - manual inspection of your .txt is best
                 solved_count = potential_numbers[0]
                 level = potential_numbers[1]
                 # A more reliable way might be to find specific preceding labels if format changes
            else:
                 # Fallback or specific known indices if the above fails
                 solved_count = int(parts[3]) # Assuming index 3 is Solved Count
                 level = int(parts[4])        # Assuming index 4 is Level

        except (IndexError, ValueError) as parse_error:
            print(f"Parsing error for {username}: {parse_error}. Data: {parts}")
            return None, "Could not parse stats"

        if solved_count is None or level is None:
             return None, "Could not find stats"

        # You could parse solved_ids here if needed for more complex cards
        # solved_ids_str = parts[7:] # Example index
        # solved_ids = [int(id) for id in solved_ids_str if id.isdigit()]

        stats = {
            'username': username, # Use the input username for display consistency
            'solved_count': solved_count,
            'level': level,
        }
        return stats, None # Return stats dictionary and no error

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, f"User '{username}' not found"
        else:
            print(f"HTTP Error for {username}: {e}")
            return None, "Project Euler request failed"
    except requests.exceptions.RequestException as e:
        print(f"Request Exception for {username}: {e}")
        return None, "Could not connect to Project Euler"
    except Exception as e: # Catch any other unexpected error during processing
        print(f"Unexpected error for {username}: {e}")
        return None, "An internal error occurred"

# Vercel runs this file, and Flask handles the routing within it.
# The route '/' here corresponds to the '/api/euler-stats' URL because
# Vercel routes requests to '/api/euler-stats' to the 'api/euler-stats.py' file.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>') # Catch all paths within this handler for Vercel
def handle_request(path):
    username = request.args.get('username')

    # Use the template loader
    template = jinja_env.get_template('card_template.svg')

    if not username:
        svg_content = template.render(error="Username required (?username=...)")
        response = make_response(svg_content)
        response.headers['Content-Type'] = 'image/svg+xml'
        response.status_code = 400 # Bad Request
        return response

    stats, error_message = get_euler_stats(username)

    if error_message:
        svg_content = template.render(error=error_message)
        status_code = 404 if "not found" in error_message.lower() else 500
    else:
        svg_content = template.render(**stats) # Pass stats dictionary as keyword args
        status_code = 200

    response = make_response(svg_content)
    response.headers['Content-Type'] = 'image/svg+xml'
    # Add caching headers - cache for 1 hour, allow stale while revalidating
    response.headers['Cache-Control'] = 'public, max-age=3600, s-maxage=3600, stale-while-revalidate=1800'
    response.status_code = status_code
    return response

# This part is mainly for local testing, Vercel uses a WSGI server
if __name__ == '__main__':
    app.run(debug=True)