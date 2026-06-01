import subprocess
import sys

print("Installing requirements  modules...")
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)

print("Installing Playwright browsers...")
subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)

print("\n Setup complete! Run 'python main.py' to start MARK XXV.")

# use vertualenv to create a virtual environment and install dependencies
# python -m venv venv
# source venv/bin/activate (Linux/Mac) or venv\Scripts\activate
# pip install -r requirements.txt
