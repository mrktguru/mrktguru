from database import db
from models.proxy_network import ProxyNetwork
from models.account import Account
import logging

logger = logging.getLogger(__name__)

def assign_dynamic_port(account, network_id, commit=True):
    """
    Finds the first available port in the network range and assigns it to the account.
    """
    # Use local import to avoid circular dependency
    from app import app
    
    with app.app_context(): # Ensure we have app context if called from outside
        network = ProxyNetwork.query.get(network_id)
        if not network:
            raise ValueError(f"Proxy network with ID {network_id} not found")

        # 1. Fetch ports currently assigned (sorted)
        # Avoid generating full range set to prevent OOM/Timeout on large ranges
        used_ports_query = db.session.query(Account.assigned_port).filter(
            Account.proxy_network_id == network_id,
            Account.assigned_port != None
        ).order_by(Account.assigned_port).all()
        
        used_ports = [row[0] for row in used_ports_query]

        # 2. Find first available port (Gap Finding Algorithm)
        target_port = None
        current_check = network.start_port
        
        # Optimize: if no used ports, just take start
        if not used_ports:
            target_port = network.start_port
        else:
            # Check for gaps between used ports
            for port in used_ports:
                if port == current_check:
                    current_check += 1
                elif port > current_check:
                    # Found a gap!
                    target_port = current_check
                    break
                # If port < current_check, it duplicates or is out of order (shouldn't happen with order_by), continue
            
            # If no gap found in middle, check if we can append after last used
            if target_port is None:
                if current_check <= network.end_port:
                    target_port = current_check

        if target_port is None or target_port > network.end_port:
             raise Exception(f"No free ports available in network '{network.name}' ({network.start_port}-{network.end_port})!")

        # 3. Assign
        account.proxy_network_id = network.id
        account.assigned_port = target_port
        
        if commit:
            db.session.commit()
            logger.info(f"[{account.id}] Assigned dynamic port {target_port} from network '{network.name}'")
            
        return target_port

def release_dynamic_port(account, commit=True):
    """
    Releases the port assigned to an account.
    """
    if account.assigned_port:
        port = account.assigned_port
        account.assigned_port = None
        
        if commit:
            db.session.commit()
            logger.info(f"[{account.id}] Released dynamic port {port}")
        return True
    return False
