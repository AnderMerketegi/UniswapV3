import toml
from web3 import Web3


def get_balance(network_name):
    network = blockchain_config['networks'][network_name]
    rpc_url = network['rpc_url']

    # Connect
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if web3.is_connected():
        print(f"Connected to {network_name}")
        # Get balance (in wei) and convert to ether or matic
        balance_wei = web3.eth.get_balance(wallet_address)
        balance_eth = web3.from_wei(balance_wei, 'ether')
        return balance_eth
    else:
        raise ConnectionError(f"Unable to connect to {network_name} blockchain")


# Load config files
wallet_config = toml.load("../config/config.toml")
blockchain_config = toml.load("../blockchain/blockchain.toml")

# Get wallet info
wallet_address = wallet_config["wallet"]["metamask"]['address']
private_key = wallet_config["wallet"]["metamask"]['private_key']

if __name__ == "__main__":

    try:
        matic_balance = get_balance('polygon')
        print(f"Balance in Polygon: {matic_balance} MATIC")
    except Exception as e:
        print(f"Error: {str(e)}")
