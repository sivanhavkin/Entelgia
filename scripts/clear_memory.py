#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Deletion Utility for Entelgia
=====================================

This utility allows you to clear memory from the Entelgia system.

Options:
- Clear short-term memory (JSON files)
- Clear long-term memory (SQLite database)
- Clear all memories

Usage:
    python scripts/clear_memory.py

The script will prompt you to choose which type of memory to delete.
"""

import os
import sys
import sqlite3
from pathlib import Path
from typing import List


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
    Delete the long-term memory database.

    Returns:
        True if successful, False otherwise
    """
    db_path = os.path.join(data_dir, "entelgia_memory.sqlite")

    if not os.path.exists(db_path):
        print("No long-term memory database found.")
        return False

    # Check how many entries exist
    try:
        # Use context manager for automatic connection cleanup
        # Note: This is read-only, so no explicit commit needed
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Check if memories table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            )
            if cursor.fetchone() is None:
                print("Database exists but 'memories' table not found.")
            else:
                # Count entries
                cursor.execute("SELECT COUNT(*) FROM memories")
                count = cursor.fetchone()[0]
                print(f"\nFound {count} long-term memory entries in the database.")
    except Exception as e:
        print(f"Could not read database: {e}")
        return False

    try:
        os.remove(db_path)
        print(f"Deleted: {os.path.basename(db_path)}")
        return True
    except Exception as e:
        print(f"Error deleting database: {e}")
        return False


def delete_all_memories(data_dir: str) -> tuple:
    """
    Delete all memories (both short-term and long-term).

    Returns:
        Tuple of (stm_count, ltm_deleted)
    """
    stm_count = delete_short_term_memory(data_dir)
    ltm_deleted = delete_long_term_memory(data_dir)
    return stm_count, ltm_deleted


def confirm_deletion(memory_type: str) -> bool:
    """
    Ask user to confirm deletion.

    Args:
        memory_type: Type of memory to delete ("short-term", "long-term", or "all")

    Returns:
        True if user confirms, False otherwise
    """
    print(f"\n⚠️  WARNING: You are about to delete {memory_type} memory!")
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
    print("2. Long-term memory (SQLite database)")
    print("3. All memories (both short-term and long-term)")
    print("4. Exit")
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
        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == "1":
            # Delete short-term memory
            if confirm_deletion("short-term"):
                print("\nDeleting short-term memory...")
                count = delete_short_term_memory(data_dir)
                print(f"\n✓ Deleted {count} short-term memory file(s).")
            else:
                print("\nDeletion cancelled.")

        elif choice == "2":
            # Delete long-term memory
            if confirm_deletion("long-term"):
                print("\nDeleting long-term memory...")
                success = delete_long_term_memory(data_dir)
                if success:
                    print("\n✓ Long-term memory deleted successfully.")
                else:
                    print("\n✗ Failed to delete long-term memory.")
            else:
                print("\nDeletion cancelled.")

        elif choice == "3":
            # Delete all memories
            if confirm_deletion("all"):
                print("\nDeleting all memories...")
                stm_count, ltm_deleted = delete_all_memories(data_dir)
                print(f"\n✓ Deleted {stm_count} short-term memory file(s).")
                if ltm_deleted:
                    print("✓ Long-term memory deleted successfully.")
                print("\n✓ All memories have been deleted.")
            else:
                print("\nDeletion cancelled.")

        elif choice == "4":
            print("\nExiting...")
            break

        else:
            print("\n✗ Invalid choice. Please enter 1, 2, 3, or 4.")

        # Ask if user wants to perform another operation
        if choice in ["1", "2", "3"]:
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
        print(f"\n✗ An error occurred: {e}")
        sys.exit(1)
