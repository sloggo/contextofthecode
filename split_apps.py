import os
import sys
import shutil

def create_directory_structure():
    """Create the directory structure for split applications."""
    # Create webapp directory
    if not os.path.exists('webapp'):
        os.makedirs('webapp')
        os.makedirs('webapp/src')
        os.makedirs('webapp/instance')
    
    # Create collector directory
    if not os.path.exists('collector'):
        os.makedirs('collector')
        os.makedirs('collector/src')
        os.makedirs('collector/logs')
    
    # Copy .env file to both directories
    if os.path.exists('.env'):
        shutil.copy('.env', 'webapp/.env')
        shutil.copy('.env', 'collector/.env')
    
    print("Directory structure created successfully.")

def split_applications():
    """Split the application into webapp and collector."""
    # Create directory structure
    create_directory_structure()
    
    # Copy common files
    common_dirs = ['src/utils', 'src/database']
    for dir_path in common_dirs:
        if os.path.exists(dir_path):
            # Copy to webapp
            webapp_path = os.path.join('webapp', dir_path)
            if not os.path.exists(webapp_path):
                os.makedirs(os.path.dirname(webapp_path), exist_ok=True)
                shutil.copytree(dir_path, webapp_path)
            
            # Copy to collector
            collector_path = os.path.join('collector', dir_path)
            if not os.path.exists(collector_path):
                os.makedirs(os.path.dirname(collector_path), exist_ok=True)
                shutil.copytree(dir_path, collector_path)
    
    # Copy webapp-specific files
    webapp_dirs = ['src/web_app']
    for dir_path in webapp_dirs:
        if os.path.exists(dir_path):
            webapp_path = os.path.join('webapp', dir_path)
            if not os.path.exists(webapp_path):
                os.makedirs(os.path.dirname(webapp_path), exist_ok=True)
                shutil.copytree(dir_path, webapp_path)
    
    # Copy collector-specific files
    collector_dirs = ['src/collector']
    for dir_path in collector_dirs:
        if os.path.exists(dir_path):
            collector_path = os.path.join('collector', dir_path)
            if not os.path.exists(collector_path):
                os.makedirs(os.path.dirname(collector_path), exist_ok=True)
                shutil.copytree(dir_path, collector_path)
    
    # Copy run.py to webapp
    if os.path.exists('run.py'):
        shutil.copy('run.py', 'webapp/run.py')
    
    # Copy run_collector.py to collector
    if os.path.exists('run_collector.py'):
        shutil.copy('run_collector.py', 'collector/run_collector.py')
    
    # Create requirements.txt for webapp
    with open('webapp/requirements.txt', 'w') as f:
        f.write("""Flask==2.3.3
Flask-SQLAlchemy==3.1.1
marshmallow==3.20.1
python-dotenv==1.0.0
psycopg2-binary==2.9.9
pydantic==2.5.2
pydantic-settings==2.1.0
""")
    
    # Create requirements.txt for collector
    with open('collector/requirements.txt', 'w') as f:
        f.write("""requests==2.31.0
python-dotenv==1.0.0
psutil==5.9.8
pydantic==2.5.2
pydantic-settings==2.1.0
""")
    
    print("Applications split successfully.")
    print("\nTo run the webapp:")
    print("  cd webapp")
    print("  pip install -r requirements.txt")
    print("  python run.py")
    print("\nTo run the collector:")
    print("  cd collector")
    print("  pip install -r requirements.txt")
    print("  python run_collector.py")

if __name__ == '__main__':
    split_applications()