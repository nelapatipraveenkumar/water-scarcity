from app import app, db
from water_level_data import WaterLevelData

def check_data():
    with app.app_context():
        try:
            count = WaterLevelData.query.count()
            print(f'Total water level entries: {count}')
            
            if count > 0:
                # Sample some entries
                sample = WaterLevelData.query.limit(3).all()
                print('\nSample entries:')
                for entry in sample:
                    print(f'Latitude: {entry.latitude}, Longitude: {entry.longitude}, Water Level: {entry.water_level}')
            else:
                print('No entries found in database')
                
        except Exception as e:
            print(f'Error checking data: {str(e)}')

if __name__ == '__main__':
    check_data()