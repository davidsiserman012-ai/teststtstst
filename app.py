from flask import Flask
import subprocess
import sys
import os

app = Flask(__name__)

@app.route('/')
def run_flood():
    # Run your flooder script
    result = subprocess.run(
        [sys.executable, 'cool.py', '--flood', '--auto', '--scores', '2', '--concurrency', '2', '--server', 'random'],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    return f"Flooder ran. Output:\n{result.stdout}\n\nErrors:\n{result.stderr}", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
