import pandas as pd
import uuid
import re
import unicodedata
from datetime import datetime

def normalize_text(text):
    """Normalize text by removing special characters and standardizing format"""
    if not isinstance(text, str):
        return ""
    
    # Convert to lowercase and normalize unicode
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    
    # Remove special characters
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def generate_unique_player_ids(csv_path, output_path=None):
    """
    Generate unique player IDs based on Name and First_Team only.
    
    Args:
        csv_path: Path to the input CSV file
        output_path: Path for the output CSV file. If None, will add timestamp to original filename.
    """
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Create a backup before making changes
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = csv_path.replace('.csv', f'_new_{timestamp}.csv')
    
    # Create a mapping dictionary to track player identities
    player_map = {}
    new_player_ids = []
    
    print("Generating unique player IDs...")
    for _, row in df.iterrows():
        name = normalize_text(row['Name'])
        team = normalize_text(row['First_Team']) if pd.notna(row['First_Team']) else ""
        
        # Create a composite key for uniqueness using only name and first team
        identity_key = f"{name}_{team}"
        
        # Use existing mapping or create new UUID
        if identity_key in player_map:
            new_id = player_map[identity_key]
        else:
            new_id = str(uuid.uuid4())
            player_map[identity_key] = new_id
            
        new_player_ids.append(new_id)
    
    # Remove the old player_id column and add the new one
    if 'player_id' in df.columns:
        df = df.drop('player_id', axis=1)
    
    df['player_id'] = new_player_ids
    
    print(f"Saving updated data to {output_path}...")
    df.to_csv(output_path, index=False)
    print(f"Successfully generated unique player IDs for {len(df)} records")
    print(f"Number of unique players identified: {len(player_map)}")
    
    return output_path

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate unique player IDs based on Name and First_Team")
    parser.add_argument("input_csv", help="Path to the input CSV file")
    parser.add_argument("--output", "-o", help="Path for the output CSV file (optional)")
    
    args = parser.parse_args()
    
    output_file = generate_unique_player_ids(args.input_csv, args.output)
    print(f"Process completed. Updated file saved to: {output_file}") 