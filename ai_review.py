#!/usr/bin/env python3
import subprocess
import sys
import os
import argparse
import re
import shutil
import datetime
import json

def run_command(command, check=True, capture_output=True, text=True, cwd=None):
    """Runs a shell command and returns the completed process object."""
    try:
        result = subprocess.run(
            command,
            check=check,
            shell=True,
            capture_output=capture_output,
            text=text,
            cwd=cwd
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running command: {command}")
            print(f"Return code: {e.returncode}")
            if capture_output:
                print(f"Stdout: {e.stdout}")
                print(f"Stderr: {e.stderr}")
            raise
        return e

def run_streaming_command(command, cwd=None):
    """Runs a command, streaming output to screen (overwriting last line) and capturing it."""
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            text=True,
            cwd=cwd
        )

        captured_lines = []
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                captured_lines.append(line)
                stripped = line.strip()
                if stripped:
                    # Get terminal width to avoid wrapping
                    columns = shutil.get_terminal_size().columns
                    # Truncate to fit on one line (leave 1 char margin)
                    truncated = stripped
                    if len(truncated) > columns - 1:
                        truncated = truncated[:columns - 1]
                        
                    # If "Error" in line, print permanently (newline), else overwrite
                    if "error" in stripped.lower():
                        sys.stdout.write(f"\r\033[K{stripped}\n")
                    else:
                        # \r moves to start, \033[K clears line.
                        sys.stdout.write(f"\r\033[K{truncated}")
                    sys.stdout.flush()
                
        # Clear the dynamic line when done
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

        return subprocess.CompletedProcess(
            args=command,
            returncode=process.poll(),
            stdout="".join(captured_lines),
            stderr="" 
        )
    except Exception as e:
        print(f"\nError running streaming command: {e}")
        # Ensure we kill process if something goes wrong
        try:
            process.kill()
        except:
            pass
        raise

def check_git_repo(cwd):
    """Checks if the specified directory is a git repository."""
    try:
        run_command("git rev-parse --is-inside-work-tree", cwd=cwd)
    except subprocess.CalledProcessError:
        print(f"Error: Directory '{cwd}' is not a git repository.")
        sys.exit(1)

def check_clean_state(cwd):
    """Checks if the git repository is in a clean state."""
    result = run_command("git status --porcelain", cwd=cwd)
    if result.stdout.strip():
        print("Error: Git repository is not clean. Please commit or stash changes.")
        sys.exit(1)

def get_git_ref(sha, cwd):
    """Returns the git ref format: short_sha ("subject")."""
    try:
        res = run_command(f"git show -s --format='%h (\"%s\")' {sha}", cwd=cwd, capture_output=True)
        return res.stdout.strip()
    except:
        return sha

def verify_range(commit_range, cwd):
    """Verifies that the commit range is valid."""
    try:
        # Check if the range is valid syntax
        run_command(f"git rev-parse {commit_range}", cwd=cwd)
    except subprocess.CalledProcessError:
        print(f"Error: Invalid commit range '{commit_range}'.")
        sys.exit(1)

def resolve_commits(arg, cwd):
    """
    Returns a list of commits based on the argument.
    - None: Returns the current HEAD commit.
    - Integer (as string): Returns the last N commits.
    - String: Treated as a git revision range (e.g., HEAD~3..HEAD).
    """
    if arg is None:
        result = run_command("git rev-parse HEAD", cwd=cwd)
        return [result.stdout.strip()]
    
    try:
        n = int(arg)
        if n <= 0:
             print("Error: Number of commits must be positive.")
             sys.exit(1)
        result = run_command(f"git rev-list --reverse -n {n} HEAD", cwd=cwd)
        return result.stdout.strip().splitlines()
    except ValueError:
        # Assume it's a range or specific ref
        verify_range(arg, cwd)
        result = run_command(f"git rev-list --reverse {arg}", cwd=cwd)
        commits = result.stdout.strip().splitlines()

        # If it's a range "A..B", we want to include A as well.
        if arg and ".." in arg and "..." not in arg:
            start_ref = arg.split("..")[0]
            if start_ref:
                try:
                    res = run_command(f"git rev-parse {start_ref}", cwd=cwd, check=False)
                    if res.returncode == 0:
                        start_sha = res.stdout.strip()
                        if start_sha not in commits:
                            commits.insert(0, start_sha)
                except Exception:
                    pass

        return commits

def load_settings():
    """Loads settings from .kengp.json."""
    settings_path = ".kengp.json"
    default_settings = {
        "llm_agent": "gemini",
        "llm_model": "gemini-3-pro-preview",
        "llm_project": None
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r') as f:
                return {**default_settings, **json.load(f)}
        except Exception as e:
            print(f"Warning: Could not read {settings_path}: {e}. Using defaults.")
    return default_settings

def check_environment(agent_command):
    """Checks if review-prompts are available."""
    cwd = os.getcwd()
    review_prompts_dir = os.path.join(cwd, "review-prompts")

    if not os.path.isdir(review_prompts_dir):
        print(f"Error: Directory '{review_prompts_dir}' not found in current path.")
        sys.exit(1)

    core_prompt = os.path.join(review_prompts_dir, "review-core.md")
    if not os.path.isfile(core_prompt):
        print(f"Error: Core prompt file '{core_prompt}' not found.")
        sys.exit(1)

def main():
    description = """Run ai_review on git commits.

This tool analyzes git commits using an AI model to detect regressions.
It can process a single commit (HEAD), a number of recent commits, or a range of commits.
"""
    epilog = """Examples:
  ./ai_review.py            # Analyze HEAD
  ./ai_review.py 3          # Analyze last 3 commits
  ./ai_review.py HEAD~2..HEAD # Analyze last 2 commits using range
"""
    settings = load_settings()
    
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("revision", nargs="?", help="Git commit range, number of commits, or empty for HEAD.")
    parser.add_argument("-m", "--model", default=settings["llm_model"], help=f"LLM model to use (default: {settings['llm_model']}).")
    parser.add_argument("--agent", default=settings["llm_agent"], help=f"LLM agent to use (default: {settings['llm_agent']}).")
    parser.add_argument("-p", "--project", default=settings["llm_project"], help=f"LLM project to use (default: {settings['llm_project']}).")
    args = parser.parse_args()

    check_environment(args.agent)

    # Current working directory is the base
    base_dir = os.getcwd()
    
    # Source tree is now ./linux
    source_tree = os.path.join(base_dir, "linux")
    
    # Use semcode built from local source if present, otherwise look in $PATH,
    # otherwise fail.
    semcode_index_src_path = os.path.join(base_dir, "semcode/target/release/semcode-index")
    if os.path.isfile(semcode_index_src_path):
        semcode_index_path = semcode_index_src_path
    elif (p := shutil.which("semcode-index")):
        semcode_index_path = p
    else:
        print(f"Error: semcode-index tool not found at {semcode_index_path} or in $PATH")
        sys.exit(1)

    print(f"Running semcode-index on {source_tree}...")
    run_command(f"{semcode_index_path} --source {source_tree}", capture_output=False)

    # Verify source tree exists
    if not os.path.isdir(source_tree):
        print(f"Error: Source tree '{source_tree}' does not exist.")
        sys.exit(1)
    
    check_git_repo(source_tree)
    check_clean_state(source_tree)
    
    # Capture original git state to restore later
    original_commit = run_command("git rev-parse HEAD", cwd=source_tree).stdout.strip()
    original_branch_res = run_command("git symbolic-ref --short -q HEAD", check=False, cwd=source_tree)
    original_branch = original_branch_res.stdout.strip() if original_branch_res.returncode == 0 else None

    commits = resolve_commits(args.revision, source_tree)
    
    if not commits:
        print("No commits found in the specified range.")
        sys.exit(0)

    print(f"Found {len(commits)} commits to process.")
    
    # Gather task info
    model_name = args.model
    
    # Get review-prompts SHA
    try:
        prompts_dir = os.path.join(base_dir, "review-prompts")
        prompts_sha = get_git_ref("HEAD", prompts_dir)
    except:
        prompts_sha = "unknown"

    report_content = []
    report_content.append(f"# Task")
    report_content.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append(f"Model: {model_name}")
    report_content.append(f"Prompts SHA: {prompts_sha}")
    report_content.append(f"Commits to review:")
    
    # Pre-calculate refs for the report to avoid doing it inside the processing loop again if we wanted optimization, 
    # but we need them for the report header now.
    commit_refs = []
    for sha in commits:
        commit_refs.append(get_git_ref(sha, source_tree))
    
    for ref in commit_refs:
        report_content.append(f"- {ref}")

    report_content.append(f"\n")

    total_regressions = 0
    commit_results = []

    try:
        for i, sha in enumerate(commits):
            commit_ref = commit_refs[i]
            print(f"Processing commit: {commit_ref}")
            
            # Checkout commit
            run_command(f"git checkout {sha}", cwd=source_tree)
            
            # Delete review-inline.txt if it exists in base_dir
            review_inline_path = os.path.join(base_dir, "review-inline.txt")
            if os.path.exists(review_inline_path):
                os.remove(review_inline_path)
            
            # Run ai_review
            prompt = f"Using @./review-prompts/review-core.md prompt as a guidance run a deep dive regression analysis of the top commit in the ./linux directory. If you cannot read the prompt, bail out."
            
            agent_cmd = f"{args.agent} --approval-mode auto_edit -e '' -m {model_name}"
            if args.project:
                agent_cmd += f" --project {args.project}"
            agent_cmd += f" -p '{prompt}'"

            # Run agent from base_dir (current folder)
            print(f"  Running analysis using {args.agent}...")
            proc = run_streaming_command(agent_cmd, cwd=base_dir)
            
            commit_section = f"# Commit {commit_ref}\n"
            current_regressions = "N/A"
            
            if proc.returncode == 0:
                print(f"  Success.")
                output = proc.stdout
                
                # Check for regressions count in output
                match = re.search(r"FINAL REGRESSIONS FOUND: (\d+)", output)
                if match:
                    count = int(match.group(1))
                    current_regressions = count
                    total_regressions += count
                    print(f"  Regressions found: {count}")
                else:
                    # Try to find it in stderr if not in stdout (though usually stdout)
                    match_err = re.search(r"FINAL REGRESSIONS FOUND: (\d+)", proc.stderr)
                    if match_err:
                        count = int(match_err.group(1))
                        current_regressions = count
                        total_regressions += count
                        print(f"  Regressions found: {count}")
                    else:
                        print("  Could not parse regression count.")

                # Check for review-inline.txt
                if os.path.exists(review_inline_path):
                    with open(review_inline_path, 'r') as f:
                        commit_section += f.read()
                    # Clean up the inline file
                    os.remove(review_inline_path)
                else:
                    commit_section += "No detailed regression report generated.\n"
            else:
                print(f"  Failed.")
                commit_section += f"Error running review tool.\nStderr:\n{proc.stderr}\n"

            commit_results.append((commit_ref, current_regressions))
            report_content.append(commit_section)
    
    except KeyboardInterrupt:
        print("\nProcess interrupted.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        print("\nRestoring original git state...")
        if original_branch:
            print(f"Checking out branch: {original_branch}")
            run_command(f"git checkout {original_branch}", check=False, cwd=source_tree)
        else:
            original_ref = get_git_ref(original_commit, source_tree)
            print(f"Checking out commit: {original_ref}")
            run_command(f"git checkout {original_commit}", check=False, cwd=source_tree)

        # Generate final report
        summary_table = "# Summary\n\n"
        
        # Calculate max width for alignment and prepare data
        max_len = len("Commit")
        safe_results = []
        for ref, count in commit_results:
            # Escape pipes for markdown safety
            safe_ref = ref.replace("|", "\\|")
            max_len = max(max_len, len(safe_ref))
            safe_results.append((safe_ref, count))
        
        # Header
        summary_table += f"| {'Commit'.ljust(max_len)} | Regressions |\n"
        summary_table += f"| :{'-' * (max_len - 1)} | :---------- |\n"
        
        for safe_ref, count in safe_results:
            summary_table += f"| {safe_ref.ljust(max_len)} | {str(count).ljust(11)} |\n"
        
        report_content.append(summary_table)
        
        start_sha_short = run_command(f"git rev-parse --short {commits[0]}", cwd=source_tree, capture_output=True).stdout.strip()
        end_sha_short = run_command(f"git rev-parse --short {commits[-1]}", cwd=source_tree, capture_output=True).stdout.strip()
        current_time_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"{current_time_str}_{start_sha_short}..{end_sha_short}.report.txt"
        
        try:
            with open(report_filename, 'w') as f:
                f.write("\n".join(report_content))
            print(f"\nReport saved to {report_filename}")
        except Exception as e:
            print(f"Error saving report: {e}")

        # Cleanup review-inline.txt in base_dir
        review_inline_path = os.path.join(base_dir, "review-inline.txt")
        if os.path.exists(review_inline_path):
            try:
                os.remove(review_inline_path)
            except:
                pass
        
        # Cleanup review-inline.txt in source_tree
        review_inline_source_path = os.path.join(source_tree, "review-inline.txt")
        if os.path.exists(review_inline_source_path):
            try:
                os.remove(review_inline_source_path)
            except:
                pass

if __name__ == "__main__":
    main()
