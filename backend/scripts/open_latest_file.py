import os
import glob
from win32com.client import Dispatch, gencache

def main():
    try:
        # 1. Determine CATParts directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(script_dir)
        catparts_dir = os.path.join(backend_dir, "CATParts")
        
        if not os.path.exists(catparts_dir):
            print(f"Error: CATParts directory not found at {catparts_dir}")
            return

        # 2. Find latest .CATPart file
        files = glob.glob(os.path.join(catparts_dir, "*.CATPart"))
        if not files:
            print("Error: No .CATPart files found in CATParts directory.")
            return
            
        latest_file = max(files, key=os.path.getctime)
        print(f"Found latest file: {latest_file}")
        
        # 3. Connect to CATIA
        try:
            catia = Dispatch('CATIA.Application')
        except Exception:
            try:
                catia = gencache.EnsureDispatch('CATIA.Application')
            except Exception:
                print("Error: Could not connect to CATIA. Is it running?")
                return

        catia.Visible = True
        
        # 4. Open the file
        # Check if already open to avoid errors or reload?
        # documents = catia.Documents
        # For now, just try to open.
        
        doc = catia.Documents.Open(latest_file)
        print(f"Successfully opened: {latest_file}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
