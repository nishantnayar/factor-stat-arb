"""
Run script for Streamlit Trading System UI
Supports both single-file and multipage configurations
"""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging before running Streamlit
from src.shared.logging import setup_logging  # noqa: E402

setup_logging(service_name="streamlit_ui")


def run_streamlit():
    """Run Streamlit with correct settings for multipage app"""
    try:
        # Check if we're in the right directory
        if not os.path.exists("streamlit_ui/streamlit_app.py"):
            print("Error: streamlit_ui/streamlit_app.py not found.")
            print("Please run this script from the project root directory.")
            return
        
        # Run streamlit with multipage support
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "streamlit_ui/streamlit_app.py",
            "--server.address", "localhost",
            "--server.port", "8501",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\nStreamlit app stopped.")
    except Exception as e:
        print(f"Error running Streamlit: {e}")


def run_with_custom_config():
    """Run Streamlit with custom configuration"""
    try:
        # Create custom config if it doesn't exist
        config_dir = os.path.expanduser("~/.streamlit")
        os.makedirs(config_dir, exist_ok=True)
        
        config_file = os.path.join(config_dir, "config.toml")
        with open(config_file, "w") as f:
                f.write("""
[server]
headless = false
port = 8501
address = "localhost"

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#1a1a1a"
backgroundColor = "#FAFAF8"
secondaryBackgroundColor = "#F5F4F0"
textColor = "#1a1a1a"
font = "sans serif"
""")
        
        run_streamlit()
    except Exception as e:
        print(f"Error with custom config: {e}")
        run_streamlit()


if __name__ == "__main__":
    print("Starting Streamlit Trading System...")
    print("Multipage app structure:")
    print("   - Main app: streamlit_ui/streamlit_app.py")
    print("   - Pages: streamlit_ui/pages/")
    print("   - Navigation: Automatic sidebar menu")
    print("   - Session State: Enabled for data sharing")
    print()
    
    run_with_custom_config()
