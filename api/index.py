import os
import sys

# Add backend/src to Python path so we can import the app
sys.path.append(os.path.join(os.getcwd(), 'backend', 'src'))

from eula.main import app
