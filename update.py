# -*- coding: utf-8 -*-
"""
Created on Tue Jun 11 15:30:33 2024

@author: vbja
"""
import os
import subprocess


def updateShiny():
    # Execute the git pull command and capture the output
    result = subprocess.run(['git', 'pull'], capture_output=True, text=True)
    output = result.stdout

    # Print any errors
    if result.stderr:
        print(f"Errors during git pull:")
        print(result.stderr)
        print()

    if output == "Already up to date.\n":
        print(output)
        return
    else:
        print("Updating new changes:")
        print(output)

    # List of subfolders
    folders = []
    for i, line in enumerate(output.rstrip("\n").split("Updating ")[1].split("changed, ")[0].split("\n")[:-1]):
        if line.startswith(" "):
            if len(line.split("/")) > 1:
                folders.append(f"./{line.split('/')[0].strip()}")

    print(f"Changes in {', '.join(folders)}")

    # Bash script to execute
    bash_script = './redeploy.sh'

    for folder in folders:
        try:
            # Change the current working directory to the subfolder
            os.chdir(folder)
            print(f"Current working directory: {os.getcwd()}")

            # Execute the bash script
            subprocess.run(bash_script, check=True, shell=True)
            print(f"Finished redeploying {folder}")
        except Exception as e:
            print(f"An error occurred in {folder}: {e}")
        os.chdir("..")

if __name__ == "__main__":
    updateShiny()
