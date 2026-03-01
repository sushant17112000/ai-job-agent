"""
GitHub Uploader — commits the Excel report via git CLI (used inside GitHub Actions).
"""

import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def commit_excel_via_git(file_path: str, commit_message: str) -> None:
    """
    Stage and commit a file using git CLI.

    This function is designed to run inside GitHub Actions where the workspace
    is already a cloned repository. It will:
      1. git add <file>
      2. Check if there are staged changes
      3. git commit if changes exist

    The workflow YAML handles 'git push' separately.

    Args:
        file_path: path to the file to commit (relative or absolute).
        commit_message: commit message string.
    """
    if os.environ.get("GITHUB_ACTIONS") != "true":
        logger.info("Not running in GitHub Actions — skipping git commit.")
        return

    def run(cmd: list[str]) -> subprocess.CompletedProcess:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            logger.debug("git stdout: %s", result.stdout.strip())
        if result.stderr:
            logger.debug("git stderr: %s", result.stderr.strip())
        return result

    # Stage the file
    add_result = run(["git", "add", file_path])
    if add_result.returncode != 0:
        logger.error("git add failed: %s", add_result.stderr)
        return

    # Check if there is anything to commit
    diff_result = run(["git", "diff", "--staged", "--quiet"])
    if diff_result.returncode == 0:
        logger.info("Nothing to commit — report may be unchanged.")
        return

    # Commit
    commit_result = run(["git", "commit", "-m", commit_message])
    if commit_result.returncode != 0:
        logger.error("git commit failed: %s", commit_result.stderr)
    else:
        logger.info("Committed: %s", commit_message)
