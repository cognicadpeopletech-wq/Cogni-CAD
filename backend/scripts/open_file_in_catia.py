import sys
import argparse
import os
import time
from win32com.client import Dispatch

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Absolute path to the file to open")
    args = parser.parse_args()

    file_path = os.path.abspath(args.path)
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        sys.exit(1)

    try:
        # Connect to CATIA
        catia = Dispatch('CATIA.Application')
        catia.Visible = True
        
        # Open the document
        doc = catia.Documents.Open(file_path)
        print(f"Success: Opened {file_path}")
        
    except Exception as e:
        print(f"Error: Failed to open file in CATIA. {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
