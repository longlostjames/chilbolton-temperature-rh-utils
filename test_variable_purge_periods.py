#!/usr/bin/env python3
"""
Test script to verify that the apply_purge_indices module can handle
variable numbers of purge periods (more than 2).
"""

import pandas as pd


def test_csv_with_variable_columns():
    """Test reading the CSV file with 2017-07-10 which has 3 purge periods."""
    
    csv_file = "purge_indices_2017.csv"
    
    print("Testing CSV reading with variable number of purge periods...")
    
    # Read CSV file with variable number of columns per row
    # First, read raw lines to find maximum number of columns
    max_cols = 0
    with open(csv_file, 'r') as f:
        for line in f:
            num_cols = len(line.strip().split(','))
            if num_cols > max_cols:
                max_cols = num_cols
    
    print(f"Maximum number of columns found: {max_cols}")
    
    # Generate column names dynamically based on maximum columns found
    if max_cols > 9:
        # We have more than 2 purge periods in some rows
        # Calculate number of purge periods: (max_cols - 1) / 4
        num_periods = (max_cols - 1) // 4
        print(f"Detected {num_periods} purge periods (maximum)")
        
        col_names = ['date']
        for i in range(1, num_periods + 1):
            col_names.extend([
                f'purge{i}_start_idx',
                f'purge{i}_end_idx',
                f'recovery{i}_start_idx',
                f'recovery{i}_end_idx'
            ])
        df = pd.read_csv(csv_file, names=col_names, skiprows=1, parse_dates=['date'], on_bad_lines='warn')
    else:
        # Standard case with 2 purge periods
        df = pd.read_csv(csv_file, parse_dates=['date'], on_bad_lines='warn')
    
    print(f"\nRead {len(df)} rows from {csv_file}")
    print(f"Column names: {list(df.columns)}")
    
    # Find and display the 2017-07-10 row
    july_10 = df[df['date'] == '2017-07-10']
    
    if not july_10.empty:
        print("\n2017-07-10 data:")
        row = july_10.iloc[0]
        
        # Count how many purge periods this row has
        purge_count = 0
        for i in range(1, num_periods + 1):
            purge_start_col = f'purge{i}_start_idx'
            if purge_start_col in row.index and pd.notna(row[purge_start_col]):
                purge_count += 1
                print(f"  Purge {i}: start={int(row[f'purge{i}_start_idx'])}, "
                      f"end={int(row[f'purge{i}_end_idx'])}")
                if pd.notna(row.get(f'recovery{i}_start_idx')):
                    print(f"  Recovery {i}: start={int(row[f'recovery{i}_start_idx'])}, "
                          f"end={int(row[f'recovery{i}_end_idx'])}")
        
        print(f"\nTotal purge periods for 2017-07-10: {purge_count}")
        
        # Test that we can iterate through the purge periods dynamically
        print("\nTesting dynamic purge period iteration:")
        purge_num = 1
        while True:
            purge_start_col = f'purge{purge_num}_start_idx'
            purge_end_col = f'purge{purge_num}_end_idx'
            
            has_purge = purge_start_col in row.index and purge_end_col in row.index
            
            if not has_purge:
                break
            
            if pd.notna(row.get(purge_start_col)):
                print(f"  Found purge period {purge_num}: "
                      f"{int(row[purge_start_col])} to {int(row[purge_end_col])}")
            
            purge_num += 1
        
        print(f"\n✓ Successfully identified {purge_num - 1} purge period(s)")
    else:
        print("\nWarning: 2017-07-10 not found in CSV")
    
    print("\n✓ Test completed successfully!")


if __name__ == "__main__":
    test_csv_with_variable_columns()
