import re
 
TEST_COMMAND = "Modify the existing model parameters and save this model in STP format"
 
mappings = [
    (r"\b(modify|update).*parameters\b", "update_parameters.py")
]
 
def find_script(text):
    norm = text.lower()
    for pattern, script in mappings:
        if re.search(pattern, norm):
            return script
    return None
 
result = find_script(TEST_COMMAND)
if result == "update_parameters.py":
    print("SUCCESS: Command matched correctly.")
else:
    print(f"FAILURE: Command did not match. Result: {result}")