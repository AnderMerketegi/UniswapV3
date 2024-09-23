from web3 import Web3
import os
from dotenv import load_dotenv
from utils.utils import load_config

from logs.logger import Logger

logger = Logger()


class Wallet:

    def __init__(self):

        load_dotenv()

        self.name = "metamask"
        self.provider = "polygon"

        address = os.getenv("WALLET_ADDRESS")
        private_key = os.getenv("PRIVATE_KEY")

        if not private_key or not address:
            raise ValueError("Environment variables WALLET_ADDRESS and PRIVATE_KEY must be defined in .env file")

        self.address = address

        # Use Polygon network as default
        self.web3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

        # Verify connection
        if not self.web3.is_connected():
            raise ConnectionError(f"Unable to connect to: {self.provider}")

        logger.info(f"Connected to: {self.provider}")

    def set_provider(self, provider: str) -> None:
        """Set wallet provider and connect"""

        config = load_config()
        try:
            network_url = config['networks'][provider]
        except KeyError as e:
            raise ValueError(f"Unable to find provider in config file: {provider}") from e

        try:
            web3_instance = Web3(Web3.HTTPProvider(network_url))
            if not web3_instance.is_connected():
                raise ConnectionError(f"Unable to connect to: {provider}")

            self.provider = provider
            self.web3 = web3_instance
            logger.info(f"Connected to: {self.provider}")

        except ConnectionError as e:
            logger.error(f"Unable to connect to provider {provider}: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in provider configuration: {e}")
            raise

    def get_balance(self):
        """Get wallet balance"""

        try:
            # Get balance (in wei) and convert to ether or matic
            balance_wei = self.web3.eth.get_balance(self.address)
            balance_eth = self.web3.from_wei(balance_wei, 'ether')
            return balance_eth
        except (Exception,) as e:
            logger.error(f"Unable to get balance: {e}")
            return None
