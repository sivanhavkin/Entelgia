import os

# Validation check functions

# 1. Check if project directory exists

def check_project_directory():
    if not os.path.exists('.'):  # Assuming current directory is the project
        return "Project directory does not exist"

# 2. Check if necessary files exist

def check_necessary_files():
    necessary_files = ['file1.txt', 'file2.txt', 'README.md']  # Update this list with your necessary files
    missing_files = [file for file in necessary_files if not os.path.isfile(file)]
    return missing_files

# 3. Check if files are non-empty

def check_non_empty_files():
    empty_files = []
    for file in os.listdir('.'):  # Assuming current directory is the project
        if os.path.isfile(file) and os.path.getsize(file) == 0:
            empty_files.append(file)
    return empty_files

# 4. Check if Python scripts are present

def check_python_scripts():
    scripts = [file for file in os.listdir('.') if file.endswith('.py')]
    return scripts

# 5. Check if project is under version control

def check_version_control():
    if not os.path.exists('.git'):
        return "Project is not under version control"

# 6. Validate encoding for text files

def validate_encoding():
    text_files = [file for file in os.listdir('.') if file.endswith('.txt')]
    for file in text_files:
        try:
            content = open(file).read_text(encoding='utf-8')  # Updated encoding
        except UnicodeDecodeError:
            return f"Encoding error in file: {file}"

# 7. Check for '.gitignore' file

def check_gitignore():
    if not os.path.isfile('.gitignore'):
        return "'.gitignore' file is missing"

# 8. Check for any custom validation logic

def check_custom_logic():
    # Implement your custom logic here
    return

# 9. Check for requirements file

def check_requirements():
    if not os.path.isfile('requirements.txt'):
        return "'requirements.txt' file is missing"

# 10. Check compatibility with Python version

def check_python_version():
    import sys
    if sys.version_info < (3, 6):
        return "Python version is not compatible"

# 11. Check for dependencies

def check_dependencies():
    # Implement dependency checks here
    return

# 12. Check for documentation

def check_documentation():
    if not os.path.isfile('README.md'):
        return "'README.md' file is missing"

# 13. Check for test files

def check_test_files():
    test_files = [file for file in os.listdir('.') if file.startswith('test_')]
    return test_files

# 14. Check for licensing information

def check_license():
    if not os.path.isfile('LICENSE'):
        return "'LICENSE' file is missing"

# Combine validations

def run_validations():
    validations = [
        check_project_directory(),
        check_necessary_files(),
        check_non_empty_files(),
        check_python_scripts(),
        check_version_control(),
        validate_encoding(),
        check_gitignore(),
        check_requirements(),
        check_python_version(),
        check_documentation(),
        check_test_files(),
        check_license()
    ]
    return validations

if __name__ == '__main__':
    results = run_validations()
    for result in results:
        if result:
            print(result)
