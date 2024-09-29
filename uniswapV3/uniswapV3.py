import json
from web3 import Web3

from logs.logger import Logger

logger = Logger()


class UniswapV3:
    def __init__(self, web3: Web3, wallet_address: str):
        """
        Initializes the UniswapV3 class with a Web3 instance and the wallet address.

        :param web3: Web3 connection instance (passed from the Wallet class).
        :param wallet_address: Public address of the connected wallet.
        """
        self.web3 = web3
        self.wallet_address = wallet_address

        # Address of the NonfungiblePositionManager contract in Uniswap V3
        self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS = self.web3.to_checksum_address(
            '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'
        )

        # Load the ABI for the NonfungiblePositionManager contract
        with open('config/NonfungiblePositionManager.json', 'r') as abi_file:
            self.nft_manager_abi = json.load(abi_file)

        # Create an instance of the NonfungiblePositionManager contract
        self.nft_manager_contract = self.web3.eth.contract(
            address=self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS, abi=self.nft_manager_abi
        )

    def get_positions_ids(self):
        """
        Retrieves the IDs of liquidity positions associated with the wallet.
        :return: List of active position IDs.
        """
        try:
            # Event signature for the NFT Transfer event
            transfer_event_signature = self.web3.keccak(text="Transfer(address,address,uint256)").to_0x_hex()

            # Get the current block number
            latest_block = self.web3.eth.block_number

            # Format the wallet address for filtering topics
            wallet_address_topic = '0x' + self.wallet_address[2:].zfill(64)

            # Filter Transfer events where the 'to' address is the wallet
            transfer_filter = {
                'fromBlock': 0,
                'toBlock': latest_block,
                'address': self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS,
                'topics': [transfer_event_signature, None, wallet_address_topic]  # Filter by the recipient address (wallet)
            }

            logs = self.web3.eth.get_logs(transfer_filter)

            position_ids = []
            for log in logs:
                # Decode the event log data
                decoded_log = self.nft_manager_contract.events.Transfer().process_log(log)
                token_id = decoded_log['args']['tokenId']
                position_ids.append(token_id)

            return position_ids

        except Exception as e:
            logger.error(f"Error retrieving position IDs: {e}")
            return []

    def get_position_details(self, token_id):
        """
        Retrieves details of a specific position based on its token ID.
        :param token_id: The token ID representing the liquidity position.
        :return: Liquidity position details.
        """
        try:
            position = self.nft_manager_contract.functions.positions(token_id).call()
            return position
        except Exception as e:
            logger.error(f"Error retrieving details for position {token_id}: {e}")
            return None

    def get_pools(self):
        """
        Retrieves all pools associated with the wallet by checking position IDs.
        Prints details of each position.
        """
        pools, position_ids = [], self.get_positions_ids()
        if position_ids:
            for token_id in position_ids:
                # Get and display the details of each position
                position_details = self.get_position_details(token_id)
                if position_details:
                    pools.append(position_details)
        else:
            logger.info(f"No positions found for wallet: {self.wallet_address}")
        return pools

    def get_active_pools(self):
        """
        Retrieves all active pools associated with the wallet by checking position IDs.
        Prints details of each active position.
        """
        active_pools, positions = [], self.get_pools()
        if positions:
            active_pools = [position for position in positions if position[0] > 0]
            if not active_pools:
                logger.info(f"No active positions for wallet: {self.wallet_address}")
        return active_pools
