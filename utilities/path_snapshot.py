import os

def path_snapshot(base_dir, output_file="path_snapshot.txt"): #pylint: disable#redefined-outer-name
    """
    Generates a tree structure for the given directory and writes it to a file.

    Args:
        base_dir (str): The base directory to snapshot.
        output_file (str): The file to save the tree (default: "path_snapshot.txt").
    """
    def generate_tree(base_dir, prefix=""):
        """
        Recursively generates a tree structure for a given directory, excluding 'venv' contents.

        Args:
            base_dir (str): The base directory to start the tree.
            prefix (str): The prefix for indentation (used during recursion).

        Returns:
            list: A list of strings representing the directory tree.
        """
        tree = []
        entries = sorted(os.listdir(base_dir))  # Sort entries for consistent output

        for index, entry in enumerate(entries):
            path = os.path.join(base_dir, entry)
            is_last = (index == len(entries) - 1)

            # Add branch characters based on whether this is the last entry
            if is_last:
                connector = "└── "
            else:
                connector = "├── "

            # Add the current entry
            tree.append(f"{prefix}{connector}{entry}")

            # If the entry is a directory, recurse into it unless it's 'venv'
            if os.path.isdir(path) and entry != "venv":
                extension = "    " if is_last else "│   "
                tree.extend(generate_tree(path, prefix + extension))

        return tree

    # Ensure the base directory name is included at the top
    tree = [os.path.basename(base_dir) + "/"] + generate_tree(base_dir)

    # Write the tree to the output file using utf-8 encoding
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(tree))

    print(f"Directory tree saved to {output_file}")

# Example usage
if __name__ == "__main__":
    # Get the project root directory (two levels up from this script)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_file = os.path.join(base_dir, "path_snapshot.txt")
    path_snapshot(base_dir, output_file)
