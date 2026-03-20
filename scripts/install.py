#!/usr/bin/env python3
"""
Entelgia Installation Script

This script automates the installation and setup process for Entelgia.
At the start you will choose your LLM backend:

  - Ollama  (local, open-source models)
  - Grok    (xAI cloud API — requires a GROK_API_KEY)

Only the steps relevant to your chosen backend are shown.

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


def configure_grok_api_key(required=False):
    """Show Grok API key instructions and prompt the user to enter their key.

    Args:
        required: When True the user must provide a key (Grok backend was chosen).
    """
    print_header("Grok (xAI) API Key Setup")

    print("To use Entelgia with Grok you need an xAI API key.\n")
    print("How to get a Grok API key:")
    print("  1. Go to https://console.x.ai and sign in with your X (Twitter) account.")
    print("  2. In the left sidebar click \"API Keys\".")
    print("  3. Click \"Create API Key\", give it a name, and copy the generated key.")
    print("  4. Paste the key when prompted below.\n")
    print("Available Grok models (you will select at Entelgia startup):")
    print("  - grok-4.20-multi-agent    (multi-agent capable, latest)")
    print("  - grok-4-1-fast-reasoning  (fast reasoning, high performance)")

    prompt = "\nEnter your Grok API key: " if required else "\nEnter your Grok API key (or press Enter to skip): "

    while True:
        grok_api_key = getpass.getpass(prompt).strip()

        if grok_api_key:
            return grok_api_key

        if required:
            print_warning("A Grok API key is required when using the Grok backend.")
            retry = input("Try again? (y/n): ").strip().lower()
            if retry != "y":
                print("Installation cancelled. Add GROK_API_KEY to .env manually and re-run.")
                return None
        else:
            print_warning("Skipping Grok API key entry.")
            print("Add GROK_API_KEY to your .env file before using Grok.")
            return None


def update_grok_api_key_in_env(grok_api_key: str) -> bool:
    """Write GROK_API_KEY into the .env file."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    env_file = repo_root / ".env"

    if not env_file.exists():
        print_error(".env file does not exist")
        return False

    try:
        with open(env_file, "r") as f:
            lines = f.readlines()

        key_updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith("GROK_API_KEY="):
                lines[i] = f"GROK_API_KEY={grok_api_key}\n"
                key_updated = True
                break

        if not key_updated:
            lines.append(f"GROK_API_KEY={grok_api_key}\n")

        with open(env_file, "w") as f:
            f.writelines(lines)

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


def print_next_steps(backend, model_pulled=False):
    """Print instructions for next steps after installation."""
    print_header("Installation Complete!")

    print("Next steps:")

    if backend == "ollama":
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

    else:  # grok
        print("\n1. Ensure your GROK_API_KEY is set in the .env file.")

        print("\n2. Run Entelgia:")
        print("   python examples/demo_enhanced_dialogue.py")
        print("   or")
        print("   python Entelgia_production_meta.py")

        print("\n   Entelgia will ask you to confirm the Grok backend and model at startup.")

    print("\n" + "=" * 60)
    print("For more information, see the README.md file")
    print("=" * 60 + "\n")


def choose_backend():
    """Ask the user to choose between Ollama and Grok before anything else."""
    print_header("Choose Your LLM Backend")

    print("Entelgia supports two LLM backends:\n")
    print("  1. Ollama  — runs models locally on your machine (free, private)")
    print("               Requires Ollama to be installed.")
    print("  2. Grok    — uses xAI's cloud API (requires a GROK_API_KEY)\n")

    while True:
        choice = input("Which backend would you like to use? [1=Ollama / 2=Grok]: ").strip()
        if choice in ("1", "ollama"):
            return "ollama"
        if choice in ("2", "grok"):
            return "grok"
        print_warning("Please enter 1 (Ollama) or 2 (Grok).")


def main():
    """Main installation flow."""
    print_header("Entelgia Installation Script")

    # Check Python version
    print("Checking Python version...")
    if not verify_python_version():
        sys.exit(1)

    print_success("All checks passed\n")

    # Step 0: Choose backend — shown before any backend-specific work
    backend = choose_backend()

    model_pulled = False

    if backend == "ollama":
        # Step 1: Check/install Ollama
        ollama_installed = setup_ollama()
        if not ollama_installed:
            print("\nInstallation paused. Please install Ollama and run this script again.")
            sys.exit(1)

        # Step 1.5: Pull Ollama model
        model_pulled = setup_ollama_model()

    # Step 2: Setup .env file
    if not setup_env_file():
        print_error("Failed to setup .env file")
        sys.exit(1)

    # Step 3: Update MEMORY_SECRET_KEY
    if not update_api_key():
        print_error("Failed to update API key")
        sys.exit(1)

    # Step 3.5: Grok API key — required when Grok is chosen, skipped for Ollama
    if backend == "grok":
        print_step("3.5", "Grok API key setup (required for the Grok backend)...")
        grok_api_key = configure_grok_api_key(required=True)
        if not grok_api_key:
            sys.exit(1)
        if not update_grok_api_key_in_env(grok_api_key):
            print_error("Failed to save GROK_API_KEY to .env")
            sys.exit(1)

    # Step 4: Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies")
        sys.exit(1)

    # Print next steps (backend-specific)
    print_next_steps(backend, model_pulled)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
