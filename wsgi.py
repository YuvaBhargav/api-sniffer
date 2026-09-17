import sys
import os

# Set project working directory for PythonAnywhere WSGI server
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Import Flask application object required by PythonAnywhere WSGI
from app import flask_app as application
