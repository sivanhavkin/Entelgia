#!/usr/bin/env python3
"""
Entelgia Installation Script

This script automates the installation and setup process for Entelgia:
- Checks for Ollama installation (installs on Mac via Homebrew)
- Copies .env.example to .env if needed
- Prompts for LLM backend selection (Ollama or Grok)
- Prompts for API key configuration (MEMORY_SECRET_KEY and optional GROK_API_KEY)
- Installs Python dependencies

Usage:
    python scripts/install.py
"""

import sys
import platform
import subprocess
import shutil
import secrets
import string
import getpass
from pathlib import Path


def print_header(message):
    """Print a formatted header message."""
    print(f"\n{'=' * 60}")
    print(f"  {message}")
    print(f"{'=' * 60}\n")


def print_step(step_num, message):
    """Print a numbered step message."""
    print(f"[{step_num}] {message}")


def print_success(message):
    """Print a success message."""
    print(f"{message}")


def print_warning(message):
    """Print a warning message."""
    print(f"{message}")


def print_error(message):
    """Print an error message."""
    print(f"{message}")


def get_platform():
    """Detect the operating system platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


def check_command_exists(command):
    """Check if a command exists in PATH."""
    return shutil.which(command) is not None


def check_ollama_installed():
    """Check if Ollama is installed."""
    return check_command_exists("ollama")


def install_ollama_mac():
    """Install Ollama on macOS using Homebrew."""
    print("Attempting to install Ollama via Homebrew...")

    # Check if Homebrew is installed
    if not check_command_exists("brew"):
        print_error("Homebrew is not installed.")
        print("Please install Homebrew first from: https://brew.sh")
        print("Then run this script again.")
        return False

    try:
        print("Running: brew install ollama")
        result = subprocess.run(
            ["brew", "install", "ollama"], capture_output=True, text=True, timeout=300
        )

        if result.returncode == 0:
            print_success("Ollama installed successfully via Homebrew")
            return True
        else:
            print_error(f"Failed to install Ollama: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print_error("Installation timed out")
        return False
    except Exception as e:
        print_error(f"Error installing Ollama: {e}")
        return False


def print_ollama_instructions(os_type):
    """Print manual installation instructions for Ollama."""
    print_warning("Ollama is not installed.")
    print("\nPlease install Ollama manually:")

    if os_type == "linux":
        print("\nFor Linux:")
        print("  curl -fsSL https://ollama.com/install.sh | sh")
        print("\nOr visit: https://ollama.com/download/linux")
    elif os_type == "windows":
        print("\nFor Windows:")
        print("  Download the installer from: https://ollama.com/download/windows")
        print("  Or use WSL2 with the Linux installation method")

    print("\nAfter installing Ollama, run this script again.")


def setup_ollama():
    """Check for Ollama installation and attempt to install if needed."""
    print_step(1, "Checking Ollama installation...")

    if check_ollama_installed():
        print_success("Ollama is already installed")
        return True

    os_type = get_platform()

    if os_type == "mac":
        print_warning("Ollama not found")
        response = (
            input("Would you like to install Ollama via Homebrew? (y/n): ")
            .strip()
            .lower()
        )

        if response == "y":
            if install_ollama_mac():
                return True
            else:
                print("\nPlease install Ollama manually from: https://ollama.com")
                return False
        else:
            print_ollama_instructions(os_type)
            return False
    else:
        print_ollama_instructions(os_type)
        return False


def pull_ollama_model(model_name="qwen2.5:7b"):
    """Pull an Ollama model."""
    print(f"\nAttempting to pull Ollama model: {model_name}")
    print("This may take several minutes depending on your internet speed...")

    try:
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Stream output to show progress
        for line in iter(process.stdout.readline, ""):
            if line:
                print(line.rstrip())

        process.wait()

        if process.returncode == 0:
            print_success(f"Model '{model_name}' pulled successfully")
            return True
        else:
            print_error(f"Failed to pull model '{model_name}'")
            return False
    except FileNotFoundError:
        print_error("Ollama command not found")
        return False
    except Exception as e:
        print_error(f"Error pulling model: {e}")
        return False


def setup_ollama_model():
    """Prompt user to pull an Ollama model."""
    print_step("1.5", "Setting up Ollama model...")

    print("\nEntelgia requires an LLM model to run.")
    print("Recommended models (7B+ required for reliable performance):")
    print("  - qwen2.5:7b - Strong reasoning and instruction following [RECOMMENDED]")
    print("  - llama3.1:8b - Excellent general-purpose performance")
    print("  - mistral:latest - Balanced reasoning and conversational coherence")

    response = (
        input("\nWould you like to pull the qwen2.5:7b model now? (y/n): ")
        .strip()
        .lower()
    )

    if response == "y":
        return pull_ollama_model("qwen2.5:7b")
    else:
        print_warning("Skipping model download")
        print("You can pull a model later with: ollama pull qwen2.5:7b")
        return False  # Return False since model was not pulled


def setup_env_file():
    """Copy .env.example to .env if it doesn't exist."""
    print_step(2, "Setting up environment configuration...")

    # Get the parent directory (repository root)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    env_example = repo_root / ".env.example"
    env_file = repo_root / ".env"

    if not env_example.exists():
        print_error(".env.example file not found in current directory")
        print("Please run this script from the Entelgia repository root")
        return False

    if env_file.exists():
        print_success(".env file already exists")
        response = (
            input("Would you like to update the API key? (y/n): ").strip().lower()
        )
        if response != "y":
            return True
    else:
        try:
            shutil.copy(env_example, env_file)
            print_success("Created .env file from .env.example")
        except Exception as e:
            print_error(f"Failed to create .env file: {e}")
            return False

    return True


def generate_secure_key(length=48):
    """Generate a cryptographically secure random key."""
    # Use a mix of letters, digits, and some special characters
    alphabet = string.ascii_letters + string.digits + "-_"
    key = "".join(secrets.choice(alphabet) for _ in range(length))
    return key


def update_api_key():
    """Prompt for API key and update .env file."""
    print_step(3, "Configuring API key...")

    # Get the parent directory (repository root)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    env_file = repo_root / ".env"

    if not env_file.exists():
        print_error(".env file does not exist")
        return False

    print("\nThe MEMORY_SECRET_KEY is used for cryptographic integrity protection.")
    print("It should be at least 32 characters long.")

    response = (
        input("\nWould you like to automatically generate a secure key? (y/n): ")
        .strip()
        .lower()
    )

    if response == "y":
        api_key = generate_secure_key(48)
        print_success("Generated secure 48-character key (saved to .env file)")
    else:
        manual_response = (
            input("Would you like to enter a custom MEMORY_SECRET_KEY? (y/n): ")
            .strip()
            .lower()
        )

        if manual_response != "y":
            print("Keeping existing configuration from .env.example")
            return True

        api_key = input("Enter your MEMORY_SECRET_KEY (min 32 characters): ").strip()

        if len(api_key) < 32:
            print_warning("Warning: Key is shorter than recommended 32 characters")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != "y":
                print("Keeping existing configuration from .env.example")
                return True

    try:
        # Read the current .env file
        with open(env_file, "r") as f:
            lines = f.readlines()

        # Update the MEMORY_SECRET_KEY line
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith("MEMORY_SECRET_KEY="):
                lines[i] = f"MEMORY_SECRET_KEY={api_key}\n"
                updated = True
                break

        # Write back to the file
        with open(env_file, "w") as f:
            f.writelines(lines)

        if updated:
            print_success("MEMORY_SECRET_KEY updated successfully")
        else:
            print_warning("MEMORY_SECRET_KEY line not found in .env")

        return True
    except Exception as e:
        print_error(f"Failed to update .env file: {e}")
        return False


def configure_grok_api_key():
    """Show Grok API key instructions and prompt the user to enter their key."""
    print_header("Grok (xAI) API Key Setup")

    print("To use Entelgia with Grok you need an xAI API key.\n")
    print("How to get a Grok API key:")
    print("  1. Go to https://console.x.ai and sign in with your X (Twitter) account.")
    print("  2. In the left sidebar click \"API Keys\".")
    print("  3. Click \"Create API Key\", give it a name, and copy the generated key.")
    print("  4. Paste the key when prompted below.\n")
    print("Available Grok models (configurable inside Config in the main script):")
    print("  - grok-3           (most capable, best reasoning)")
    print("  - grok-3-fast      (faster, slightly less capable)")
    print("  - grok-3-mini      (lightweight, low-cost)")
    print("  - grok-3-mini-fast (fastest, minimal cost)")
    print("  - grok-2-1212      (previous generation, stable)")

    grok_api_key = getpass.getpass("\nEnter your Grok API key (or press Enter to skip): ").strip()

    if not grok_api_key:
        print_warning("Skipping Grok API key entry.")
        print("You MUST add GROK_API_KEY to your .env file before running Entelgia with Grok.")
        return None

    return grok_api_key


def select_llm_backend():
    """Ask the user which LLM backend they want to use."""
    print_step("2.5", "Selecting LLM backend...")

    print("\nEntelgia supports two LLM backends:")
    print("  1. Ollama  - Run models locally on your machine (default, free, private)")
    print("  2. Grok    - Use xAI's hosted Grok API (requires an API key, cloud-based)")

    while True:
        choice = input("\nWhich backend would you like to use? [1=Ollama / 2=Grok] (default: 1): ").strip()
        if choice in ("", "1"):
            return "ollama"
        if choice == "2":
            return "grok"
        print_warning("Invalid choice. Please enter 1 for Ollama or 2 for Grok.")


def update_env_backend(backend: str, grok_api_key: str = "") -> bool:
    """Write LLM_BACKEND (and optionally GROK_API_KEY) into the .env file."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    env_file = repo_root / ".env"

    if not env_file.exists():
        print_error(".env file does not exist")
        return False

    try:
        with open(env_file, "r") as f:
            lines = f.readlines()

        backend_updated = False
        grok_key_updated = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("LLM_BACKEND="):
                lines[i] = f"LLM_BACKEND={backend}\n"
                backend_updated = True
            elif grok_api_key and stripped.startswith("GROK_API_KEY="):
                lines[i] = f"GROK_API_KEY={grok_api_key}\n"
                grok_key_updated = True

        if not backend_updated:
            lines.append(f"LLM_BACKEND={backend}\n")
        if grok_api_key and not grok_key_updated:
            lines.append(f"GROK_API_KEY={grok_api_key}\n")

        with open(env_file, "w") as f:
            f.writelines(lines)

        print_success(f"LLM backend set to: {backend}")
        if grok_api_key:
            print_success("GROK_API_KEY saved to .env")
        return True
    except Exception as e:
        print_error(f"Failed to update .env file: {e}")
        return False


def install_dependencies():
    """Install Python dependencies from requirements.txt."""
    print_step(4, "Installing Python dependencies...")

    # Get the parent directory (repository root)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    requirements = repo_root / "requirements.txt"

    if not requirements.exists():
        print_error("requirements.txt not found in current directory")
        print("Please run this script from the Entelgia repository root")
        return False

    try:
        print("Running: pip install -r requirements.txt")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            print_success("Dependencies installed successfully")
            return True
        else:
            print_error("Failed to install dependencies")
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print_error("Installation timed out")
        return False
    except Exception as e:
        print_error(f"Error installing dependencies: {e}")
        return False


def verify_python_version():
    """Check if Python version is 3.10 or higher."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print_error(
            f"Python 3.10+ is required. "
            f"Current version: {version.major}.{version.minor}"
        )
        return False
    print_success(
        f"Python version {version.major}.{version.minor}.{version.micro} is compatible"
    )
    return True


def print_next_steps(model_pulled=False, backend="ollama"):
    """Print instructions for next steps after installation."""
    print_header("Installation Complete!")

    print("Next steps:")

    if backend == "grok":
        print("\n1. Make sure your GROK_API_KEY is set in the .env file.")
        print("   You can verify with: grep GROK_API_KEY .env")
        step_run = "2"
    else:
        print("\n1. Start Ollama (if not already running):")
        print("   ollama serve")

        if not model_pulled:
            print("\n2. Pull a model if not pulled automatically (e.g., qwen2.5:7b):")
            print("   ollama pull qwen2.5:7b")
            step_verify = "3"
            step_run = "4"
        else:
            step_verify = "2"
            step_run = "3"

        print(f"\n{step_verify}. Verify Ollama is working:")
        print('   ollama run qwen2.5:7b "hello"')

    print(f"\n{step_run}. Run Entelgia:")
    print("   python examples/demo_enhanced_dialogue.py")
    print("   or")
    print("   python Entelgia_production_meta.py")

    print("\n" + "=" * 60)
    print("For more information, see the README.md file")
    print("=" * 60 + "\n")


def main():
    """Main installation flow."""
    print_header("Entelgia Installation Script")

    # Check Python version
    print("Checking Python version...")
    if not verify_python_version():
        sys.exit(1)

    print_success("All checks passed\n")

    # Step 2: Setup .env file first so backend selection can update it
    if not setup_env_file():
        print_error("Failed to setup .env file")
        sys.exit(1)

    # Step 2.5: Select LLM backend
    backend = select_llm_backend()

    model_pulled = False
    if backend == "ollama":
        # Step 1: Check/install Ollama
        ollama_installed = setup_ollama()
        if not ollama_installed:
            print("\nInstallation paused. Please install Ollama and run this script again.")
            sys.exit(1)

        # Step 1.5: Pull Ollama model
        model_pulled = setup_ollama_model()

        if not update_env_backend("ollama"):
            print_error("Failed to update .env with backend setting")
            sys.exit(1)

    elif backend == "grok":
        print("\nSkipping Ollama setup — Grok backend selected.")
        grok_api_key = configure_grok_api_key()
        if not update_env_backend("grok", grok_api_key or ""):
            print_error("Failed to update .env with Grok settings")
            sys.exit(1)
        if not grok_api_key:
            print_warning(
                "\nReminder: set GROK_API_KEY in your .env before running Entelgia."
            )

    # Step 3: Update MEMORY_SECRET_KEY
    if not update_api_key():
        print_error("Failed to update API key")
        sys.exit(1)

    # Step 4: Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies")
        sys.exit(1)

    # Print next steps
    print_next_steps(model_pulled, backend)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
