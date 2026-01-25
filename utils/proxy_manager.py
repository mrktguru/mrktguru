from app import db, app
from models.proxy_network import ProxyNetwork
from models.account import Account
import logging

logger = logging.getLogger(__name__)

def assign_dynamic_port(account, network_id):
    """
    Finds the first available port in the network range and assigns it to the account.
    """
    with app.app_context(): # Ensure we have app context if called from outside
        network = ProxyNetwork.query.get(network_id)
        if not network:
            raise ValueError(f"Proxy network with ID {network_id} not found")

        # 1. Generate full set of potential ports
        all_ports = set(range(network.start_port, network.end_port + 1))

        # 2. Find ports currently assigned to ACTIVE accounts (or just any account occupying it)
        # We assume ANY account holding a port makes it unavailable.
        used_ports_query = db.session.query(Account.assigned_port).filter(
            Account.proxy_network_id == network_id,
            Account.assigned_port != None
        ).all()
        
        used_ports = {row[0] for row in used_ports_query}

        # 3. Calculate free ports
        free_ports = list(all_ports - used_ports)
        free_ports.sort() # low to high

        if not free_ports:
            raise Exception(f"No free ports available in network '{network.name}' ({network.start_port}-{network.end_port})!")

        # 4. Assign the first one
        target_port = free_ports[0]
        
        # Update account instance (caller must commit if they want, or we commit here)
        # Assuming account is attached to session.
        account.proxy_network_id = network.id
        account.assigned_port = target_port
        
        db.session.commit()
        
        logger.info(f"[{account.id}] Assigned dynamic port {target_port} from network '{network.name}'")
        return target_port

def release_dynamic_port(account):
    """
    Releases the port assigned to an account.
    """
    if account.assigned_port:
        port = account.assigned_port
        account.assigned_port = None
        # account.proxy_network_id = None # Optional: Keep network association or clear it? 
        # Plan says: "acc.proxy_network_id оставляем или тоже None, по желанию". Keeping it might be useful for re-enabling.
        
        db.session.commit()
        logger.info(f"[{account.id}] Released dynamic port {port}")
        return True
    return False
