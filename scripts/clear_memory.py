#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Deletion Utility for Entelgia
=====================================

This utility allows you to clear memory from the Entelgia system.

Options:
- Clear short-term memory (JSON files)
- Clear long-term memory (SQLite database rows + agent state)
- Clear sessions
- Clear all memories and sessions

Usage:
    python scripts/clear_memory.py

The script will prompt you to choose which type of memory to delete.
"""

import os
import sys
import sqlite3
from typing import List, Tuple


def get_data_directory() -> str:
    """Get the data directory path."""
    return "entelgia_data"


def list_stm_files(data_dir: str) -> List[str]:
    """List all short-term memory JSON files."""
    if not os.path.exists(data_dir):
        return []

    files = []
    for file in os.listdir(data_dir):
        if file.startswith("stm_") and file.endswith(".json"):
            files.append(os.path.join(data_dir, file))
    return files


def delete_short_term_memory(data_dir: str) -> int:
    """
    Delete all short-term memory files.

    Returns:
        Number of files deleted
    """
    stm_files = list_stm_files(data_dir)

    if not stm_files:
        print("No short-term memory files found.")
        return 0

    print(f"\nFound {len(stm_files)} short-term memory file(s):")
    for file in stm_files:
        print(f"  - {os.path.basename(file)}")

    count = 0
    for file in stm_files:
        try:
            os.remove(file)
            count += 1
            print(f"Deleted: {os.path.basename(file)}")
        except Exception as e:
            print(f"Error deleting {os.path.basename(file)}: {e}")

    return count


def delete_long_term_memory(data_dir: str) -> bool:
    """
    Clear all long-term memory entries and agent state from the SQLite database.

    Rows are removed via SQL DELETE so the database file and the ``settings``
    table (which stores the HMAC key fingerprint) are preserved.  This avoids
    a full key-migration re-sign on the next bot start-up and works even when
    SQLite WAL files are present.

    Returns:
        True if successful, False otherwise
    """
    db_path = os.path.join(data_dir, "entelgia_memory.sqlite")

    if not os.path.exists(db_path):
        print("No long-term memory database found.")
        return False

    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            cursor = conn.cursor()

            # Report how many memory rows will be removed
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            )
            if cursor.fetchone() is None:
                print("Database exists but 'memories' table not found.")
                return False

            cursor.execute("SELECT COUNT(*) FROM memories")
            mem_count = cursor.fetchone()[0]
            print(f"\nFound {mem_count} long-term memory entries in the database.")

            # Report agent_state rows
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_state'"
            )
            has_agent_state = cursor.fetchone() is not None
            agent_count = 0
            if has_agent_state:
                cursor.execute("SELECT COUNT(*) FROM agent_state")
                agent_count = cursor.fetchone()[0]

            # Delete all memory rows and agent state; keep the settings table
            # (HMAC key fingerprint) so the bot does not re-sign on next start
            conn.execute("DELETE FROM memories")
            if has_agent_state:
                conn.execute("DELETE FROM agent_state")
            conn.commit()

        print(f"Cleared {mem_count} memory row(s) from the database.")
        if has_agent_state and agent_count:
            print(f"Cleared {agent_count} agent-state row(s) from the database.")
        return True

    except Exception as e:
        print(f"Error clearing database: {e}")
        return False


def delete_sessions(data_dir: str) -> int:
    """
    Delete all session JSON files from the sessions directory.

    Returns:
        Number of session files deleted
    """
    sessions_dir = os.path.join(data_dir, "sessions")

    if not os.path.exists(sessions_dir):
        print("No sessions directory found.")
        return 0

    session_files = [
        os.path.join(sessions_dir, f)
        for f in os.listdir(sessions_dir)
        if f.startswith("session_") and f.endswith(".json")
    ]

    if not session_files:
        print("No session files found.")
        return 0

    print(f"\nFound {len(session_files)} session file(s).")

    count = 0
    for file in session_files:
        try:
            os.remove(file)
            count += 1
        except Exception as e:
            print(f"Error deleting {os.path.basename(file)}: {e}")

    print(f"Deleted {count} session file(s).")
    return count


def delete_all_memories(data_dir: str) -> Tuple[int, bool, int]:
    """
    Delete all memories (short-term, long-term) and sessions.

    Returns:
        Tuple of (stm_count, ltm_deleted, session_count)
    """
    stm_count = delete_short_term_memory(data_dir)
    ltm_deleted = delete_long_term_memory(data_dir)
    session_count = delete_sessions(data_dir)
    return stm_count, ltm_deleted, session_count


def confirm_deletion(memory_type: str) -> bool:
    """
    Ask user to confirm deletion.

    Args:
        memory_type: Type of memory to delete ("short-term", "long-term", or "all")

    Returns:
        True if user confirms, False otherwise
    """
    print(f"\n WARNING: You are about to delete {memory_type} memory!")
    print("This action cannot be undone.")

    response = input("\nType 'yes' to confirm deletion: ").strip().lower()
    return response == "yes"


def display_menu():
    """Display the main menu."""
    print("\n" + "=" * 60)
    print("Entelgia Memory Deletion Utility")
    print("=" * 60)
    print("\nWhat would you like to delete?")
    print("\n1. Short-term memory (JSON files)")
    print("2. Long-term memory (SQLite rows + agent state)")
    print("3. Sessions")
    print("4. All memories and sessions")
    print("5. Exit")
    print("\n" + "=" * 60)


def main():
    """Main function."""
    data_dir = get_data_directory()

    # Check if data directory exists
    if not os.path.exists(data_dir):
        print(f"\nData directory '{data_dir}' does not exist.")
        print("No memories to delete.")
        return

    while True:
        display_menu()
        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "1":
            # Delete short-term memory
            if confirm_deletion("short-term"):
                print("\nDeleting short-term memory...")
                count = delete_short_term_memory(data_dir)
                print(f"\nDeleted {count} short-term memory file(s).")
            else:
                print("\nDeletion cancelled.")

        elif choice == "2":
            # Delete long-term memory
            if confirm_deletion("long-term"):
                print("\nDeleting long-term memory...")
                success = delete_long_term_memory(data_dir)
                if success:
                    print("\nLong-term memory cleared successfully.")
                else:
                    print("\nFailed to clear long-term memory.")
            else:
                print("\nDeletion cancelled.")

        elif choice == "3":
            # Delete sessions
            if confirm_deletion("sessions"):
                print("\nDeleting sessions...")
                count = delete_sessions(data_dir)
                print(f"\nDeleted {count} session file(s).")
            else:
                print("\nDeletion cancelled.")

        elif choice == "4":
            # Delete all memories and sessions
            if confirm_deletion("all"):
                print("\nDeleting all memories and sessions...")
                stm_count, ltm_deleted, session_count = delete_all_memories(data_dir)
                print(f"\nDeleted {stm_count} short-term memory file(s).")
                if ltm_deleted:
                    print("Long-term memory cleared successfully.")
                print(f"Deleted {session_count} session file(s).")
                print("\nAll memories and sessions have been deleted.")
            else:
                print("\nDeletion cancelled.")

        elif choice == "5":
            print("\nExiting...")
            break

        else:
            print("\nInvalid choice. Please enter 1, 2, 3, 4, or 5.")

        # Ask if user wants to perform another operation
        if choice in ["1", "2", "3", "4"]:
            continue_response = (
                input("\nPerform another operation? (y/n): ").strip().lower()
            )
            if continue_response != "y":
                print("\nExiting...")
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)
