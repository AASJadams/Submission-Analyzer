import pandas as pd
from difflib import SequenceMatcher

# Load the GL class code table
gl_df = pd.read_csv("gl_class_codes_final.csv")
gl_df["General Liability Code"] = gl_df["General Liability Code"].astype(str).str.strip().str.lstrip("0")

# Keyword override map
keyword_map = {
    "gym": "41718",
    "fitness": "41718",
    "personal training": "41718",
    "health club": "41718",
    "lawn care": "97050",
    "landscaping": "97050",
    "restaurant": "11111",
    "trucking": "99793",
    "freight": "99793",
    "construction": "91580",
}

def get_description_by_code(code):
    code_str = str(code).lstrip("0")
    match = gl_df[gl_df["General Liability Code"].astype(str).str.lstrip("0") == code_str]
    if not match.empty:
        return match.iloc[0]["General Liability Description"]
    return "Unknown"

def get_best_gl_code(business_description: str, top_n=1):
    business_description = business_description.lower()
    def similarity(row):
        desc = str(row['General Liability Description']).lower()
        return SequenceMatcher(None, business_description, desc).ratio()
    gl_df["similarity"] = gl_df.apply(similarity, axis=1)
    matches = gl_df.sort_values("similarity", ascending=False).head(top_n)
    return matches

def smart_gl_lookup(description: str):
    description = description.lower()
    for keyword, code in keyword_map.items():
        if keyword in description:
            return {
                "GL Class Code": code,
                "Description": get_description_by_code(code),
                "Source": f"Matched via keyword: '{keyword}'"
            }
    match = get_best_gl_code(description, top_n=1)
    if not match.empty:
        return {
            "GL Class Code": match.iloc[0]["General Liability Code"],
            "Description": match.iloc[0]["General Liability Description"],
            "Source": "Best fuzzy match"
        }
    return {
        "GL Class Code": "Not found",
        "Description": "No matching class found",
        "Source": "No match"
    }
