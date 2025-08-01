from app import app
from import_excel import import_excel_data
import os
from dotenv import load_dotenv

def run_import():
    load_dotenv()
    excel_path = os.getenv('EXCEL_FILE_PATH')
    
    if not excel_path:
        print('Error: EXCEL_FILE_PATH not found in .env file')
        return
    
    if not os.path.exists(excel_path):
        print(f'Error: Excel file not found at path: {excel_path}')
        return
    
    with app.app_context():
        print(f'Importing data from: {excel_path}')
        result = import_excel_data(excel_path)
        
        if result['success']:
            print(f'Successfully imported {result["imported_count"]} records')
            if result['error_rows']:
                print('\nErrors in rows:')
                for error in result['error_rows']:
                    print(f'Row {error["row"]}: {error["error"]}')
        else:
            print(f'Import failed: {result["error"]}')

if __name__ == '__main__':
    run_import()