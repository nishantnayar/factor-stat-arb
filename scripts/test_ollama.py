"""
Test script to verify Ollama installation and connectivity
Run this after installing Ollama to ensure everything works
"""

import os
import sys
from typing import Optional

import requests

# ASCII markers (project encoding rules)
CHECK = "[OK]"
CROSS = "[X]"
WARN = "[!]"
INFO = "[i]"
TEST = "[TEST]"
PACKAGE = "[PKG]"
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")  # Set UTF-8 for console if needed


def test_ollama_connection() -> bool:
    """Test if Ollama API is accessible"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"{CHECK} Ollama API is running")
            return True
        else:
            print(f"{CROSS} Ollama API returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"{CROSS} Cannot connect to Ollama API. Is Ollama running?")
        print("   Start Ollama by opening the Ollama app or running 'ollama serve'")
        return False
    except Exception as e:
        print(f"{CROSS} Error connecting to Ollama: {e}")
        return False


def test_ollama_python_client() -> bool:
    """Test if ollama Python package is installed and working"""
    try:
        import ollama
        print(f"{CHECK} Ollama Python package is installed")
        return True
    except ImportError:
        print(f"{CROSS} Ollama Python package not found")
        print("   Install it with: pip install ollama")
        return False


def list_installed_models() -> Optional[list]:
    """List all installed Ollama models"""
    try:
        import ollama
        models_response = ollama.list()
        
        model_list = []
        
        # Handle different response structures
        # ollama.list() returns a ListResponse object with a 'models' attribute
        if hasattr(models_response, 'models'):
            # It's a ListResponse object
            models = models_response.models
        elif isinstance(models_response, dict):
            # If it's a dict, check for 'models' key
            if 'models' in models_response:
                models = models_response['models']
            else:
                # Maybe the response itself is the models list
                models = models_response
        elif isinstance(models_response, list):
            # If it's directly a list
            models = models_response
        else:
            # Try to use the response directly (might be iterable)
            try:
                models = list(models_response)
            except:
                models = []
        
        # Extract model names
        for model in models:
            model_name = None
            
            # ollama Model objects have a 'model' attribute (not 'name')
            if hasattr(model, 'model'):
                model_name = model.model
            elif hasattr(model, 'name'):
                # Fallback for 'name' attribute
                model_name = model.name
            elif isinstance(model, dict):
                # Try different possible key names
                model_name = (
                    model.get('model') or 
                    model.get('name') or 
                    model.get('model_name')
                )
            elif isinstance(model, str):
                model_name = model
            
            # Clean up model name (remove tag if present, keep base name)
            if model_name:
                # Extract just the base name (e.g., 'phi3:latest' -> 'phi3')
                base_name = model_name.split(':')[0].strip()
                if base_name and base_name not in model_list:
                    model_list.append(base_name)
        
        if model_list:
            print(f"\n{PACKAGE} Installed models ({len(model_list)}):")
            for model in model_list:
                print(f"   - {model}")
            return model_list
        else:
            print(f"\n{WARN}  No models found in response")
            print("   Response structure:", type(models_response))
            # Try alternative method using direct API call
            try:
                import requests
                api_response = requests.get("http://localhost:11434/api/tags", timeout=5)
                if api_response.status_code == 200:
                    api_data = api_response.json()
                    if 'models' in api_data:
                        api_models = [m.get('name', 'unknown') for m in api_data['models']]
                        if api_models:
                            print(f"   Found {len(api_models)} models via API:")
                            for m in api_models:
                                print(f"   - {m}")
                            return api_models
            except Exception as api_e:
                print(f"   Alternative API check also failed: {api_e}")
            
            print("   Install a model with: ollama pull phi3")
            return []
            
    except Exception as e:
        print(f"{CROSS} Error listing models: {e}")
        import traceback
        try:
            error_trace = traceback.format_exc()
            # Try to print traceback, but handle encoding issues
            print(f"   Error details: {str(e)}")
        except:
            print(f"   Error occurred (details unavailable due to encoding)")
        return None


def test_model_inference(model_name: str = "llama3") -> bool:
    """Test if a specific model can generate responses"""
    try:
        import ollama
        
        print(f"\n{TEST} Testing model: {model_name}")
        print("   Sending test query...")
        
        response = ollama.chat(
            model=model_name,
            messages=[{
                'role': 'user',
                'content': 'Say "Hello, Ollama is working!" if you can read this.'
            }]
        )
        
        if response and 'message' in response:
            content = response['message']['content']
            print(f"{CHECK} Model response received:")
            print(f"   {content[:100]}...")
            return True
        else:
            print(f"{CROSS} Unexpected response format")
            return False
            
    except Exception as e:
        print(f"{CROSS} Error testing model: {e}")
        if "model" in str(e).lower() and "not found" in str(e).lower():
            print(f"   Model '{model_name}' not found. Install it with:")
            print(f"   ollama pull {model_name}")
        return False


def main():
    """Run all Ollama tests"""
    print("=" * 60)
    print("Ollama Installation Test")
    print("=" * 60)
    
    # Test 1: API Connection
    print("\n1. Testing Ollama API connection...")
    api_ok = test_ollama_connection()
    
    if not api_ok:
        print(f"\n{CROSS} Ollama API is not accessible. Please:")
        print("   1. Install Ollama from https://ollama.com/download")
        print("   2. Start Ollama (it should run automatically after installation)")
        print("   3. Run this test again")
        sys.exit(1)
    
    # Test 2: Python Package
    print("\n2. Testing Ollama Python package...")
    package_ok = test_ollama_python_client()
    
    if not package_ok:
        print(f"\n{CROSS} Ollama Python package not installed.")
        print("   Install it with: pip install ollama")
        sys.exit(1)
    
    # Test 3: List Models
    print("\n3. Checking installed models...")
    models = list_installed_models()
    
    # Test 4: Model Inference
    # Try common model names if listing failed
    test_models = []
    if models:
        test_models = [m.split(':')[0] for m in models]  # Remove tag if present
    else:
        # If listing failed, try common model names
        print("\n   Model listing failed, trying common models...")
        test_models = ['phi3', 'llama3', 'mistral', 'llama3.1']
    
    inference_ok = False
    working_model = None
    
    for test_model in test_models:
        print(f"\n4. Testing model inference with '{test_model}'...")
        if test_model_inference(test_model):
            inference_ok = True
            working_model = test_model
            break
    
    if inference_ok:
        print("\n" + "=" * 60)
        print(f"{CHECK} All tests passed! Ollama is ready to use.")
        if working_model:
            print(f"{CHECK} Working model: {working_model}")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print(f"{WARN}  Ollama is installed but model inference failed.")
        print("   Make sure you've installed a model:")
        print("   ollama pull phi3")
        print("=" * 60)


if __name__ == "__main__":
    main()

