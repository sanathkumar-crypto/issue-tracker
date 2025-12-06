#!/usr/bin/env python3
"""
One-time script to update hospital zones by fuzzy matching hospital names
from the mapping CSV to existing hospitals in the system.
"""

import csv
from difflib import SequenceMatcher
from pathlib import Path

# File paths
MAPPING_CSV = Path('bquxjob_21dcb5c6_19af1fc4855.csv')
HOSPITALS_CSV = Path('data/hospitals.csv')
SIMILARITY_THRESHOLD = 0.7


def normalize_string(s):
    """Normalize string for comparison: lowercase and strip whitespace"""
    if not s:
        return ''
    return s.lower().strip()


def similarity_score(str1, str2):
    """Calculate similarity score between two strings using SequenceMatcher"""
    return SequenceMatcher(None, normalize_string(str1), normalize_string(str2)).ratio()


def read_csv(filepath):
    """Read CSV file and return list of dictionaries"""
    if not filepath.exists():
        print(f"Error: File {filepath} not found")
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(filepath, data, headers):
    """Write list of dictionaries to CSV file"""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        if data:
            # Filter out fields not in headers to avoid ValueError
            filtered_data = [{k: v for k, v in row.items() if k in headers} for row in data]
            writer.writerows(filtered_data)


def find_best_match(hospital_name, mapping_data):
    """Find the best matching hospital from mapping data"""
    best_match = None
    best_score = 0.0
    
    for mapping_row in mapping_data:
        radar_name = mapping_row.get('radar_name', '')
        if not radar_name:
            continue
        
        score = similarity_score(hospital_name, radar_name)
        if score > best_score and score >= SIMILARITY_THRESHOLD:
            best_score = score
            best_match = {
                'name': radar_name,
                'zone': mapping_row.get('cp_zone', ''),
                'score': score
            }
    
    return best_match


def main():
    """Main function to update hospital zones"""
    print("=" * 60)
    print("Hospital Zone Update Script")
    print("=" * 60)
    
    # Read mapping CSV
    print(f"\nReading mapping CSV: {MAPPING_CSV}")
    mapping_data = read_csv(MAPPING_CSV)
    if not mapping_data:
        print("Error: Could not read mapping CSV or it is empty")
        return 1
    
    print(f"Found {len(mapping_data)} entries in mapping CSV")
    
    # Read hospitals CSV
    print(f"\nReading hospitals CSV: {HOSPITALS_CSV}")
    hospitals = read_csv(HOSPITALS_CSV)
    if not hospitals:
        print("Error: Could not read hospitals CSV or it is empty")
        return 1
    
    print(f"Found {len(hospitals)} hospitals in hospitals CSV")
    
    # Perform fuzzy matching and update zones
    print(f"\nPerforming fuzzy matching (threshold: {SIMILARITY_THRESHOLD})...")
    matched_count = 0
    unmatched_hospitals = []
    updated_hospitals = []
    
    for hospital in hospitals:
        hospital_name = hospital.get('name', '')
        if not hospital_name:
            updated_hospitals.append(hospital)
            continue
        
        # Find best match
        match = find_best_match(hospital_name, mapping_data)
        
        if match:
            # Update zone
            hospital['zone'] = match['zone']
            matched_count += 1
            print(f"  Matched: '{hospital_name}' -> '{match['name']}' (score: {match['score']:.3f}, zone: {match['zone']})")
        else:
            unmatched_hospitals.append(hospital_name)
        
        updated_hospitals.append(hospital)
    
    # Save updated hospitals
    print(f"\nSaving updated hospitals to {HOSPITALS_CSV}...")
    write_csv(HOSPITALS_CSV, updated_hospitals, ['name', 'zone'])
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total hospitals: {len(hospitals)}")
    print(f"Matched and updated: {matched_count}")
    print(f"Unmatched (zone left empty): {len(unmatched_hospitals)}")
    
    if unmatched_hospitals:
        print(f"\nUnmatched hospitals ({len(unmatched_hospitals)}):")
        for name in unmatched_hospitals[:20]:  # Show first 20
            print(f"  - {name}")
        if len(unmatched_hospitals) > 20:
            print(f"  ... and {len(unmatched_hospitals) - 20} more")
    
    print("\n" + "=" * 60)
    print("Update completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    exit(main())

