from database import db

class ProxyNetwork(db.Model):
    __tablename__ = 'proxy_networks'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))  # e.g. "DataImpulse California"
    
    # Base connection string WITHOUT port: socks5://user:pass@gw.dataimpulse.com
    base_url = db.Column(db.String(255), nullable=False)
    
    # Port Range Settings
    start_port = db.Column(db.Integer, nullable=False) # e.g. 10000
    end_port = db.Column(db.Integer, nullable=False)   # e.g. 10050
    
    # Relationship with Accounts
    accounts = db.relationship('Account', backref='proxy_network', lazy=True)

    @property
    def total_ports(self):
        return self.end_port - self.start_port + 1

    def __repr__(self):
        return f'<ProxyNetwork {self.name} ({self.start_port}-{self.end_port})>'
