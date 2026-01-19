from app import create_app
from models.account import Account, DeviceProfile
from models.tdata_metadata import TDataMetadata

app = create_app()

with app.app_context():
    account_id = 24  # Assuming this is the account based on logs
    account = Account.query.get(account_id)
    
    if account:
        print(f"Account: {account.id} - {account.phone or account.username}")
        
        # Check TDataMetadata
        tdata = TDataMetadata.query.filter_by(account_id=account.id).first()
        print(f"TDataMetadata query result: {tdata}")
        
        if account.tdata_metadata:
            print(f"Relationship account.tdata_metadata: {account.tdata_metadata}")
            print(f"Device Model: {account.tdata_metadata.device_model}")
        else:
            print("Relationship account.tdata_metadata is None")
            
        # Check DeviceProfile
        device = DeviceProfile.query.filter_by(account_id=account.id).first()
        print(f"DeviceProfile query result: {device}")
        
        if account.device_profile:
             print(f"Relationship account.device_profile: {account.device_profile}")
        else:
             print("Relationship account.device_profile is None")
             
    else:
        print(f"Account {account_id} not found")
