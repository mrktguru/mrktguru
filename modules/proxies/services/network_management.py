from models.proxy_network import ProxyNetwork
from database import db
from modules.proxies.exceptions import (
    NetworkValidationError,
    NetworkNotFoundError,
    NetworkInUseError
)

class NetworkManagementService:
    @staticmethod
    def list_networks():
        return ProxyNetwork.query.order_by(ProxyNetwork.id.desc()).all()

    @staticmethod
    def get_network(network_id: int) -> ProxyNetwork:
        network = ProxyNetwork.query.get(network_id)
        if not network:
            raise NetworkNotFoundError(f"Network {network_id} not found")
        return network

    @staticmethod
    def create_network(data: dict) -> ProxyNetwork:
        """
        Create proxy network.
        Data: name, base_url, start_port, end_port
        """
        name = data.get('name')
        base_url = data.get('base_url')
        try:
            start_port = int(data.get('start_port'))
            end_port = int(data.get('end_port'))
        except (ValueError, TypeError):
             raise NetworkValidationError("Ports must be integers")
             
        if not name or not base_url:
            raise NetworkValidationError("Name and Base URL are required")
            
        if start_port > end_port:
             raise NetworkValidationError("Start port cannot be greater than end port")
             
        MAX_RANGE = 50000
        if (end_port - start_port) > MAX_RANGE:
             raise NetworkValidationError(f"Port range too large (max {MAX_RANGE} ports)")
             
        network = ProxyNetwork(
            name=name,
            base_url=base_url,
            start_port=start_port,
            end_port=end_port
        )
        
        db.session.add(network)
        db.session.commit()
        return network

    @staticmethod
    def delete_network(network_id: int):
        """Delete network if not in use"""
        network = NetworkManagementService.get_network(network_id)
        
        # Check usage (assuming relationship 'accounts' exists on ProxyNetwork)
        if hasattr(network, 'accounts') and network.accounts and len(network.accounts) > 0:
             raise NetworkInUseError(f"Cannot delete network: assigned to {len(network.accounts)} accounts")
             
        db.session.delete(network)
        db.session.commit()
        return True
