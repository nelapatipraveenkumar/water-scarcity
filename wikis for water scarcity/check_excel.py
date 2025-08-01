import pandas as pd

try:
    # Read the Excel file
    df = pd.read_excel(r'C:\Users\Hp\OneDrive\Desktop\Copy of jan_2023_data_for_website_co_ordinates_1(1).xlsx')
    
    # Print column names
    print('\nColumns in Excel file:')
    for col in df.columns:
        print(f'- {col}')
    
    # Print first few rows
    print('\nFirst 3 rows of data:')
    print(df.head(3))
    
except Exception as e:
    print(f'Error reading Excel file: {str(e)}')