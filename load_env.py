import os

def load_env_file(file_path='.env'):
    """Load environment variables from a .env file"""
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. Using system environment variables.")
    except Exception as e:
        print(f"Error loading {file_path}: {e}")

# Load environment variables when this module is imported
load_env_file()