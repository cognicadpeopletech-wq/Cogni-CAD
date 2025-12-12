
import re

number_re = r"(-?\d+(?:\.\d+)?)"
def normalize(text: str) -> str:
    if not text:
        return ""
    return text.replace("×", "x").replace("\u00D7", "x").replace("\u00A0", " ").lower().strip()

def extract_value_for_keyword(text: str, keywords: list) -> float:
    s = normalize(text)
    for kw in keywords:
        m = re.search(rf"{kw}\s*[:=]?\s*{number_re}", s)
        if m:
            print(f"Match 1 (forward) for {kw}: {m.group(0)} -> {m.group(1)}")
            try:
                return float(m.group(1))
            except:
                pass
    for kw in keywords:
        m = re.search(rf"{number_re}\s*(?:mm)?\s*{kw}", s)
        if m:
            print(f"Match 2 (backward) for {kw}: {m.group(0)} -> {m.group(1)}")
            try:
                return float(m.group(1))
            except:
                pass
    return None

test_str = "Make a 1000x500x40 mm plate, 4 holes on the diagonals, offset 75 mm from every corner hole dia 20 mm"
print(f"Test String: {test_str}")
val = extract_value_for_keyword(test_str, ["offset", "inset", "inward"])
print(f"Extracted Value: {val}")
