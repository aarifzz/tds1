# app.py
from flask import Flask, request, jsonify
import os
import json
import base64
import time
import requests
from datetime import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- Configuration ---
STUDENT_SECRET = "cooliepowerhouse"
GITHUB_TOKEN = os.getenv('GITHUB_KEY')
GITHUB_USERNAME = "aarifzz"
GEMINI_API_KEY = "AIzaSyB7PguEC-dMlCrQ28ENLZxjbaT40nUfjgA"

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def exponential_backoff_post(url, data, max_retries=5):
    """POST with exponential backoff on failure."""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if response.status_code == 200:
                return response
            print(f"❌ Attempt {attempt + 1} failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} error: {e}")
        
        if attempt < max_retries - 1:
            delay = 2 ** attempt
            print(f"⏳ Retrying in {delay} seconds...")
            time.sleep(delay)
    
    return None

def generate_app_code(brief, attachments, checks, round_num, existing_code=None):
    """Use Gemini to generate the application code."""
    
    # Prepare attachments content
    attachments_text = ""
    if attachments:
        attachments_text = "\n\nAttachments:\n"
        for att in attachments:
            name = att.get("name", "file")
            content = att.get("content", "")
            if att.get("url", "").startswith("data:"):
                # Decode base64 data
                try:
                    data_url = att["url"]
                    if ";base64," in data_url:
                        encoded = data_url.split(";base64,")[1]
                        content = base64.b64decode(encoded).decode('utf-8')
                    att["content"] = content
                except Exception as e:
                    print(f"⚠️ Failed to decode attachment: {e}")
            attachments_text += f"\n### {name}\n```\n{content}\n```\n"
    
    # Prepare checks
    checks_text = "\n\nEvaluation Checks:\n"
    for check in checks:
        checks_text += f"- {check}\n"
    
    if round_num == 1 or not existing_code:
        # Round 1: Create new application
        prompt = f"""Create a complete, production-ready single-page web application based on this brief:

{brief}
{attachments_text}
{checks_text}

Requirements:
1. Create a single HTML file with embedded CSS and JavaScript
2. Make it fully functional and self-contained
3. Use modern, clean design (you can use Bootstrap CDN or Tailwind CDN)
4. Ensure all evaluation checks will pass
5. Add proper error handling
6. Make it responsive and user-friendly
7. Use semantic HTML and accessible markup

Return ONLY the complete HTML code, no explanations or markdown formatting."""
    else:
        # Round 2: Update existing application
        prompt = f"""Update the existing application based on this new requirement:

{brief}

Current application code:
```html
{existing_code}
```
{attachments_text}
{checks_text}

Requirements:
1. Modify the existing code to implement the new features
2. Maintain all existing functionality
3. Ensure all NEW evaluation checks will pass
4. Keep the code clean and well-organized
5. Update any UI elements as needed

Return ONLY the complete updated HTML code, no explanations or markdown formatting."""

    response = model.generate_content(prompt)
    code = response.text
    
    # Clean up markdown code blocks if present
    if "```html" in code:
        code = code.split("```html")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    
    return code

def generate_readme(task, brief, checks, round_num=1):
    """Generate a professional README.md."""
    
    checks_list = "\n".join([f"- {check}" for check in checks])
    
    readme = f"""# {task}

## Summary

This application was automatically generated to fulfill the following requirements:

{brief}

## Features

This single-page application provides:
- Clean, responsive user interface
- Real-time functionality
- Error handling and validation
- Cross-browser compatibility

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/{GITHUB_USERNAME}/{task}.git
   cd {task}
   ```

2. Open `index.html` in your web browser or visit the live demo

## Usage

Simply open the `index.html` file in a modern web browser. The application is fully self-contained and requires no build process or dependencies.

## Live Demo

🌐 [View Live Application](https://{GITHUB_USERNAME}.github.io/{task}/)

## Code Explanation

The application is built as a single HTML file containing:

- **HTML Structure**: Semantic markup for accessibility
- **CSS Styling**: Embedded styles using modern CSS features
- **JavaScript Logic**: Vanilla JavaScript for functionality
- **Error Handling**: Robust error handling throughout

## Evaluation Checks (Round {round_num})

This application satisfies the following checks:

{checks_list}

## License

MIT License - See LICENSE file for details

## Generated

This application was automatically generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} using Gemini API for LLM-assisted code generation.

---
*Last updated: Round {round_num} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    return readme

def get_file_from_repo(task, filename):
    """Get existing file content from GitHub repo."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/contents/{filename}",
            headers=headers
        )
        if response.status_code == 200:
            content = response.json()["content"]
            return base64.b64decode(content).decode('utf-8')
    except Exception as e:
        print(f"⚠️ Could not fetch {filename}: {e}")
    
    return None

def update_file_in_repo(task, filename, content, message):
    """Update or create a file in GitHub repo."""
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get current file SHA if it exists
    sha = None
    try:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/contents/{filename}",
            headers=headers
        )
        if response.status_code == 200:
            sha = response.json()["sha"]
    except:
        pass
    
    # Update or create file
    file_content = base64.b64encode(content.encode()).decode()
    file_data = {
        "message": message,
        "content": file_content
    }
    if sha:
        file_data["sha"] = sha
    
    response = requests.put(
        f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/contents/{filename}",
        headers=headers,
        json=file_data
    )
    
    if response.status_code in [201, 200]:
        return response.json()["commit"]["sha"]
    else:
        raise Exception(f"Failed to update {filename}: {response.text}")

def create_github_repo(task, app_code, readme_content):
    """Create GitHub repo, push code, enable Pages."""
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Create repository
    repo_data = {
        "name": task,
        "description": f"Auto-generated application for {task}",
        "private": False,
        "auto_init": False
    }
    
    response = requests.post(
        "https://api.github.com/user/repos",
        headers=headers,
        json=repo_data
    )
    
    if response.status_code not in [201, 422]:  # 422 = already exists
        raise Exception(f"Failed to create repo: {response.text}")
    
    repo_url = f"https://github.com/{GITHUB_USERNAME}/{task}"
    
    # 2. Create/update files using Contents API
    files = {
        "index.html": app_code,
        "README.md": readme_content,
        "LICENSE": """MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
    }
    
    commit_sha = None
    for filename, content in files.items():
        file_content = base64.b64encode(content.encode()).decode()
        file_data = {
            "message": f"Add {filename}",
            "content": file_content
        }
        
        response = requests.put(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/contents/{filename}",
            headers=headers,
            json=file_data
        )
        
        if response.status_code in [201, 200]:
            if filename == "index.html":
                commit_sha = response.json()["commit"]["sha"]
        else:
            print(f"⚠️ Warning: Failed to create {filename}: {response.text}")
    
    # 3. Enable GitHub Pages (main branch, root directory)
    pages_data = {
        "source": {
            "branch": "main",
            "path": "/"
        }
    }
    
    response = requests.post(
        f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/pages",
        headers=headers,
        json=pages_data
    )
    
    # Pages might already be enabled (409) or created (201)
    if response.status_code not in [201, 409]:
        print(f"⚠️ Pages setup warning: {response.status_code}")
    
    pages_url = f"https://{GITHUB_USERNAME}.github.io/{task}/"
    
    # Get latest commit if we don't have it
    if not commit_sha:
        response = requests.get(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{task}/commits/main",
            headers=headers
        )
        if response.status_code == 200:
            commit_sha = response.json()["sha"]
    
    return repo_url, commit_sha, pages_url

def update_github_repo(task, app_code, readme_content, round_num):
    """Update existing GitHub repo for round 2."""
    
    print(f"📝 Updating repository for round {round_num}...")
    
    # Update index.html
    commit_sha = update_file_in_repo(
        task, 
        "index.html", 
        app_code, 
        f"Update application for round {round_num}"
    )
    
    # Update README.md
    update_file_in_repo(
        task, 
        "README.md", 
        readme_content, 
        f"Update README for round {round_num}"
    )
    
    repo_url = f"https://github.com/{GITHUB_USERNAME}/{task}"
    pages_url = f"https://{GITHUB_USERNAME}.github.io/{task}/"
    
    return repo_url, commit_sha, pages_url

def process_task(data):
    """Main task processing pipeline."""
    
    email = data.get("email")
    task = data.get("task")
    round_num = data.get("round")
    nonce = data.get("nonce")
    brief = data.get("brief")
    checks = data.get("checks", [])
    attachments = data.get("attachments", [])
    evaluation_url = data.get("evaluation_url")
    
    print(f"\n🚀 Processing {task} (Round {round_num})")
    
    # For round 2, get existing code
    existing_code = None
    if round_num == 2:
        print("📖 Fetching existing code...")
        existing_code = get_file_from_repo(task, "index.html")
    
    # Generate app code using Gemini
    print("🤖 Generating application code with Gemini...")
    app_code = generate_app_code(brief, attachments, checks, round_num, existing_code)
    
    # Generate README
    print("📝 Generating README...")
    readme_content = generate_readme(task, brief, checks, round_num)
    
    # Create or update GitHub repo
    if round_num == 1:
        print("📦 Creating GitHub repository...")
        repo_url, commit_sha, pages_url = create_github_repo(
            task, app_code, readme_content
        )
    else:
        print("📦 Updating GitHub repository...")
        repo_url, commit_sha, pages_url = update_github_repo(
            task, app_code, readme_content, round_num
        )
    
    print(f"✅ Repository: {repo_url}")
    print(f"📄 Commit SHA: {commit_sha}")
    print(f"🌐 Pages URL: {pages_url}")
    
    # Wait for Pages to deploy
    print("⏳ Waiting for GitHub Pages to deploy...")
    time.sleep(10)
    
    # Submit to evaluation API
    print("📤 Submitting to evaluation API...")
    eval_data = {
        "email": email,
        "task": task,
        "round": round_num,
        "nonce": nonce,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url
    }
    
    response = exponential_backoff_post(evaluation_url, eval_data)
    
    if response and response.status_code == 200:
        print("✅ Successfully submitted to evaluation API")
    else:
        print("❌ Failed to submit to evaluation API after retries")
    
    return {
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url
    }

@app.route("/api/endpoint", methods=["POST"])
def receive_request():
    """Receives the instructor's JSON request."""
    
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "No JSON body received"}), 400

    # 1️⃣ Verify secret
    if data.get("secret") != STUDENT_SECRET:
        return jsonify({"error": "Invalid secret"}), 403

    # 2️⃣ Confirm receipt immediately
    print("\n✅ Received task request")
    print(json.dumps(data, indent=2))
    
    # 3️⃣ Process task
    try:
        # Quick validation
        required = ["email", "task", "round", "nonce", "brief", "evaluation_url"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400
        
        # Process the task
        result = process_task(data)
        
        return jsonify({
            "status": "ok",
            "message": f"Task '{data.get('task')}' completed for round {data.get('round')}",
            "result": result
        }), 200
        
    except Exception as e:
        print(f"❌ Error processing task: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 200  # Still return 200 to acknowledge receipt

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    # Validate environment variables
    if not GITHUB_TOKEN:
        print("⚠️ WARNING: GITHUB_TOKEN not set")
    if not GITHUB_USERNAME:
        print("⚠️ WARNING: GITHUB_USERNAME not set")
    if not GEMINI_API_KEY:
        print("⚠️ WARNING: GEMINI_API_KEY not set")
    
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
