"""
Linting and code standard enforcement CLI command handlers.
Linting 和代码标准执行 CLI 命令处理器。

Provides functions to check for compliance with bilingual docstring standards
and other project-specific code quality rules.
提供检查是否符合双语 docstring 标准以及其他特定于项目的代码质量规则的函数。
"""
import os
import re
import sys
import logging
from pathlib import Path

logger = logging.getLogger("manage.lint")

def find_python_files(root_dir: Path) -> list[Path]:
    """
    Recursively finds all Python files in the given directory.
    在给定目录中递归查找所有 Python 文件。
    
    Args:
        root_dir (Path): The root directory to start searching from. / 开始搜索的根目录。
        
    Returns:
        list[Path]: A list of paths to discovered Python files. / 发现的 Python 文件路径列表。
    """
    python_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip common non-source directories
        if any(part.startswith('.') or part == '__pycache__' for part in Path(dirpath).parts):
            continue
            
        for filename in filenames:
            if filename.endswith('.py'):
                python_files.append(Path(dirpath) / filename)
    return python_files

def check_module_docstring(content: str) -> tuple[bool, str]:
    """
    Verifies if a module has a bilingual (English/Chinese) docstring at the top.
    验证模块顶部是否有双语（中英）docstring。
    
    Args:
        content (str): The string content of the Python file. / Python 文件的字符串内容。
        
    Returns:
        tuple[bool, str]: Success status and an error message if failed. / 成功状态以及失败时的错误信息。
    """
    lines = content.split('\n')
    # Filter out shebang and empty lines at start
    start_index = 0
    while start_index < len(lines) and (lines[start_index].startswith('#!') or not lines[start_index].strip()):
        start_index += 1
        
    if start_index >= len(lines) or not lines[start_index].strip().startswith('"""'):
        return False, "Missing module docstring"
    
    # Check for Chinese characters in first 10-15 lines of content
    test_block = '\n'.join(lines[start_index:start_index+15])
    has_chinese = re.search(r'[\u4e00-\u9fff]', test_block)
    return has_chinese is not None, "Missing Chinese translation in module docstring"

def check_function_docstrings(content: str) -> list[str]:
    """
    Analyzes all function definitions in a file for bilingual docstrings.
    分析文件中所有函数定义的双语 docstring。
    
    Args:
        content (str): The string content of the Python file. / Python 文件的字符串内容。
        
    Returns:
        list[str]: A list of strings describing identified issues. / 描述已识别问题的字符串列表。
    """
    lines = content.split('\n')
    issues = []

    # Track indentation level to detect nested functions
    # Track the current function's indentation level
    current_func_indent = None

    # Regex to find top-level or method definitions
    func_pattern = r'^\s*def\s+(\w+)'
    for i, line in enumerate(lines):
        # Reset indent tracking when we see a line with less indentation (exiting a function)
        if line.strip() and not line.strip().startswith('#'):
            line_indent = len(line) - len(line.lstrip())
            if current_func_indent is not None and line_indent < current_func_indent:
                current_func_indent = None

        match = re.match(func_pattern, line)
        if match:
            func_name = match.group(1)
            # Skip private/internal methods or dunder methods usually
            if func_name.startswith('__') and func_name.endswith('__') and func_name != '__init__':
                continue

            # Get the indentation of this function definition
            func_indent = len(line) - len(line.lstrip())

            # Skip nested functions (functions defined inside another function)
            # They have higher indentation than the enclosing function
            if current_func_indent is not None and func_indent > current_func_indent:
                continue

            # Update current function indentation level
            current_func_indent = func_indent

            # Find where the signature ends (looking for '):')
            sig_end_line = i
            for j in range(i, min(i+15, len(lines))):
                if '):' in lines[j] or '->' in lines[j] and ':' in lines[j]:
                    sig_end_line = j
                    break
            
            # Check lines after the signature for docstring
            found_docstring = False
            has_chinese = False
            for j in range(sig_end_line+1, min(sig_end_line+10, len(lines))):
                stripped = lines[j].strip()
                if not stripped: continue
                if '"""' in stripped:
                    found_docstring = True
                    # Check for Chinese in the docstring block
                    for k in range(j, min(j+20, len(lines))):
                        if re.search(r'[\u4e00-\u9fff]', lines[k]):
                            has_chinese = True
                            break
                        # End of docstring detection
                        if '"""' in lines[k] and k != j:
                            break
                    break
                # If we encounter actual code body before a docstring
                if stripped and not stripped.startswith('#') and '"""' not in stripped:
                    break
            
            if not found_docstring:
                issues.append(f"Function/Method '{func_name}': Missing docstring")
            elif not has_chinese:
                issues.append(f"Function/Method '{func_name}': Missing Chinese translation in docstring")
    
    return issues

def check_class_docstrings(content: str) -> list[str]:
    """
    Analyzes all class definitions in a file for bilingual docstrings.
    分析文件中所有类定义的双语 docstring。
    
    Args:
        content (str): The string content of the Python file. / Python 文件的字符串内容。
        
    Returns:
        list[str]: A list of strings describing identified issues. / 描述已识别问题的字符串列表。
    """
    lines = content.split('\n')
    issues = []
    
    class_pattern = r'^\s*class\s+(\w+)'
    for i, line in enumerate(lines):
        match = re.match(class_pattern, line)
        if match:
            class_name = match.group(1)
            
            # Find where the signature ends (looking for ':')
            sig_end_line = i
            for j in range(i, min(i+10, len(lines))):
                if ':' in lines[j]:
                    sig_end_line = j
                    break

            found_docstring = False
            has_chinese = False
            for j in range(sig_end_line+1, min(sig_end_line+10, len(lines))):
                stripped = lines[j].strip()
                if not stripped: continue
                if '"""' in stripped:
                    found_docstring = True
                    for k in range(j, min(j+20, len(lines))):
                        if re.search(r'[\u4e00-\u9fff]', lines[k]):
                            has_chinese = True
                            break
                        if '"""' in lines[k] and k != j:
                            break
                    break
                if stripped and not stripped.startswith('#') and '"""' not in stripped:
                    break
            
            if not found_docstring:
                issues.append(f"Class '{class_name}': Missing docstring")
            elif not has_chinese:
                issues.append(f"Class '{class_name}': Missing Chinese translation in docstring")
    
    return issues

def lint_comments(args):
    """
    CLI handler to check all Python files in the source tree for commenting standards.
    CLI 处理器，用于检查源树中所有 Python 文件是否符合注释标准。
    """
    root_dir = Path("src")
    if not root_dir.exists():
        logger.error("Error: 'src' directory not found in current path.")
        sys.exit(1)
    
    python_files = find_python_files(root_dir)
    logger.info(f"Scanning {len(python_files)} Python files for commenting compliance...")
    
    total_issues = 0
    files_with_issues = []
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        issues = []
        has_chinese, msg = check_module_docstring(content)
        if not has_chinese:
            issues.append(f"Module: {msg}")
        
        issues.extend(check_function_docstrings(content))
        issues.extend(check_class_docstrings(content))
        
        if issues:
            total_issues += len(issues)
            files_with_issues.append((file_path, issues))
            print(f"\n{file_path}:")
            for issue in issues:
                print(f"  - {issue}")
    
    print("\n" + "="*85)
    print(f"SUMMARY: {len(files_with_issues)} file(s) with issues, {total_issues} total issue(s).")
    print("="*85 + "\n")
    
    # Save a persistent report for automated CI or records
    report_path = Path("comment_issues_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("OmniDigest Commenting Standard Issues Report\n")
        f.write("="*60 + "\n\n")
        f.write(f"Total files checked: {len(python_files)}\n")
        f.write(f"Files with issues: {len(files_with_issues)}\n")
        f.write(f"Total issues: {total_issues}\n\n")
        
        for file_path, issues in files_with_issues:
            f.write(f"{file_path}:\n")
            for issue in issues:
                f.write(f"  - {issue}\n")
            f.write("\n")
    
    logger.info(f"Detailed report saved to {report_path}")
    
    if total_issues > 0:
        sys.exit(1)
    else:
        logger.info("✅ All files are compliant with the commenting standard!")
