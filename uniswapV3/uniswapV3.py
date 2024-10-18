import json
import os
import math
import time
from web3 import Web3
from decimal import Decimal
from utils.utils import load_abi, price_to_tick, calculate_ticks


from logs.logger import Logger
logger = Logger()


MAX_UINT128 = (1 << 128) - 1  # Solidity uint128 max value


class UniswapV3:
    def __init__(self, network: str, web3: Web3, wallet_address: str):
        """
        Initializes the UniswapV3 class with a Web3 instance and the wallet address.
        :param network: The blockchain network (e.g., Polygon).
        :param web3: Web3 connection instance.
        :param wallet_address: Wallet address for interacting with contracts.
        """
        self.web3 = web3
        self.network = network
        self.wallet_address = wallet_address

        # Load and initialize Uniswap V3 contracts
        self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS = self.web3.to_checksum_address(
            '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'
        )
        self.UNISWAP_V3_FACTORY_ADDRESS = self.web3.to_checksum_address(
            '0x1F98431c8aD98523631AE4a59f267346ea31F984'
        )

        # Load contract ABIs
        self.nft_manager_abi = load_abi('config/NonfungiblePositionManager.json')
        self.factory_abi = load_abi('config/UniswapV3Factory.json')
        self.pool_abi = load_abi('config/UniswapV3Pool.json')
        self.erc20_abi = load_abi('config/ERC20.json')

        # Create contract instances
        self.nft_manager_contract = self.web3.eth.contract(
            address=self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS, abi=self.nft_manager_abi
        )
        self.factory_contract = self.web3.eth.contract(
            address=self.UNISWAP_V3_FACTORY_ADDRESS, abi=self.factory_abi
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
                'topics': [transfer_event_signature, None, wallet_address_topic]
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

    def get_position_details(self, position_id):
        """
        Retrieves details of a specific position based on its token ID.
        :param position_id: The token ID representing the liquidity position.
        :return: Liquidity position details.
        """
        try:
            return self.nft_manager_contract.functions.positions(position_id).call()
        except Exception as e:
            logger.error(f"Error retrieving details for position {position_id}: {e}")
            return None

    def get_positions(self):
        """
        Retrieves all liquidity positions associated with the wallet by checking position IDs.

        :return: A dictionary mapping token IDs to their position details.
        """
        positions = {}
        for token_id in self.get_positions_ids():
            position_details = self.get_position_details(token_id)
            if position_details:
                positions[token_id] = position_details

        if not positions:
            logger.info(f"No positions found for wallet: {self.wallet_address}")

        return positions

    def get_active_positions(self):
        """
        Retrieves all active liquidity positions associated with the wallet.

        :return: A dictionary of active positions where liquidity > 0.
        """
        positions = self.get_positions()
        active_positions = {_id: position for _id, position in positions.items() if position[7] > 0}

        if not active_positions:
            logger.info(f"No active positions for wallet: {self.wallet_address}")

        return active_positions

    def get_positions_in_range(self):
        """
        Returns a dictionary of active liquidity positions where the current price is within the position's tick range.

        :return: A dictionary mapping token IDs to positions where the price is within range.
        """
        active_positions = self.get_active_positions()
        positions_in_range = {
            _id: position for _id, position in active_positions.items() if self.is_price_in_range(position)
        }

        return positions_in_range

    def is_price_in_range(self, position):
        """
        Checks if the current pool price (tick) is within the position's tick range.

        :param position: Position details from Uniswap V3.
        :return: True if the current price (tick) is within the range, else False.
        """
        token0, token1, fee, tick_lower, tick_upper = position[2:7]

        try:
            # Get the pool address for the specific tokens and fee
            pool_address = self.factory_contract.functions.getPool(token0, token1, fee).call()

            # Instantiate the pool contract and retrieve the current tick
            pool_contract = self.web3.eth.contract(address=pool_address, abi=self.pool_abi)
            current_tick = pool_contract.functions.slot0().call()[1]

            # Check if the current tick is within the position's tick range
            return tick_lower <= current_tick <= tick_upper

        except (self.web3.exceptions.ContractLogicError, self.web3.exceptions.TransactionNotFound) as e:
            logger.error(f"Error checking price range for position: {e}")
            return False

    def collect_fees(self, position_id):
        """
        Collects fees from a Uniswap V3 liquidity position.

        :param position_id: The ID of the liquidity position to collect fees from.
        :return: Transaction receipt of the collect action.
        """

        try:
            # Prepare the transaction to collect fees
            transaction = self.nft_manager_contract.functions.collect({
                'tokenId': position_id,
                'recipient': self.wallet_address,
                'amount0Max': MAX_UINT128,
                'amount1Max': MAX_UINT128
            }).build_transaction({
                'from': self.wallet_address,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'gas': 2000000,
                'gasPrice': self.web3.eth.gas_price
            })

            # Sign the transaction
            signed_tx = self.web3.eth.account.sign_transaction(transaction, os.environ["WALLET_PRIVATE_KEY"])

            # Send the transaction and wait for the receipt
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            logger.info(f"Fees collected for position ID {position_id}. Transaction hash: {tx_hash.hex()}")
            return tx_receipt

        except self.web3.exceptions.ContractLogicError as e:
            logger.error(f"Error collecting fees for position ID {position_id} (ContractLogicError): {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error collecting fees for token ID {position_id}: {e}")
            return None

    def close_position(self, position_id):
        """
        Closes a Uniswap V3 liquidity position by decreasing liquidity and burning the NFT.

        :param position_id: The ID of the liquidity position to close.
        :return: Transaction receipt of the closing action.
        """
        try:
            # Step 1: Decrease liquidity
            position = self.get_position_details(position_id)
            if position is None:
                raise ValueError(f"Position {position_id} not found.")

            liquidity = position[7]  # Liquidity of the position
            if liquidity > 0:
                self._decrease_liquidity(position_id, liquidity)
            else:
                logger.info(f"No liquidity to remove for position ID {position_id}. Proceeding to burn the NFT.")

            # Step 2: Collect outstanding fees
            self.collect_fees(position_id)

            # Step 3: Burn the NFT (close the position)
            return self._burn_position(position_id)

        except Exception as e:
            logger.error(f"Error closing position {position_id}: {e}")
            return None

    def _decrease_liquidity(self, position_id, liquidity):
        """
        Decreases liquidity of a Uniswap V3 position.

        :param position_id: The ID of the liquidity position.
        :param liquidity: The amount of liquidity to remove.
        """
        try:
            transaction = self.nft_manager_contract.functions.decreaseLiquidity({
                'tokenId': position_id,
                'liquidity': liquidity,
                'amount0Min': 0,
                'amount1Min': 0,
                'deadline': self.web3.eth.get_block('latest')['timestamp'] + 600  # 10 minutes deadline
            }).build_transaction({
                'from': self.wallet_address,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'gas': 2000000,
                'gasPrice': self.web3.eth.gas_price
            })

            # Sign and send the transaction
            signed_tx = self.web3.eth.account.sign_transaction(transaction, os.environ["WALLET_PRIVATE_KEY"])
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)

            logger.info(f"Liquidity removed for position ID {position_id}. Transaction hash: {tx_hash.hex()}")
            return tx_receipt

        except Exception as e:
            logger.error(f"Error decreasing liquidity for position ID {position_id}: {e}")
            return None

    def _burn_position(self, position_id):
        """
        Burns the NFT of a Uniswap V3 position, effectively closing the position.

        :param position_id: The ID of the liquidity position.
        :return: Transaction receipt of the burn action.
        """
        try:
            burn_tx = self.nft_manager_contract.functions.burn(position_id).build_transaction({
                'from': self.wallet_address,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'gas': 2000000,
                'gasPrice': self.web3.eth.gas_price
            })

            # Sign and send the burn transaction
            signed_burn_tx = self.web3.eth.account.sign_transaction(burn_tx, os.environ["WALLET_PRIVATE_KEY"])
            burn_tx_hash = self.web3.eth.send_raw_transaction(signed_burn_tx.raw_transaction)
            burn_tx_receipt = self.web3.eth.wait_for_transaction_receipt(burn_tx_hash)

            logger.info(f"Position {position_id} closed and NFT burned. Transaction hash: {burn_tx_hash.hex()}")
            return burn_tx_receipt

        except Exception as e:
            logger.error(f"Error burning position {position_id}: {e}")
            return None

    def approve_token(self, token_address, amount):
        """
        Approves a token for spending by the NonfungiblePositionManager contract.

        :param token_address: The address of the token to approve.
        :param amount: The amount of the token to approve for spending.
        """
        try:
            token_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)

            # Check current allowance
            allowance = token_contract.functions.allowance(self.wallet_address,
                                                           self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS).call()
            logger.info(f"Current allowance for {token_address}: {allowance}")

            # Only approve if the current allowance is less than the required amount
            if allowance >= amount:
                logger.info(f"Token {token_address} already approved with sufficient allowance: {allowance}")
                return

            # Build and send the approve transaction
            tx = token_contract.functions.approve(self.NONFUNGIBLE_POSITION_MANAGER_ADDRESS, amount).build_transaction({
                'from': self.wallet_address,
                'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
                'gas': 200000,  # Consider estimating gas for better efficiency
                'gasPrice': self.web3.eth.gas_price
            })

            # Sign and send the transaction
            signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=os.environ["WALLET_PRIVATE_KEY"])
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for the transaction receipt
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(
                f"Approval transaction successful. Token {token_address} approved for {amount}. Tx hash: {tx_hash.hex()}")

            return tx_receipt

        except Exception as e:
            logger.error(f"Error approving token {token_address}: {e}")
            return None

    def get_token_decimals(self, token_address):
        """
        Obtiene los decimales de un token ERC20.

        :param token_address: Dirección del token ERC20.
        :return: Número de decimales del token.
        """
        # ABI estándar de ERC20 para obtener los decimales
        token_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)

        try:
            decimals = token_contract.functions.decimals().call()
            return decimals
        except Exception as e:
            logger.error(f"Error obteniendo los decimales del token en {token_address}: {e}")
            return None

    def get_token_balance(self, wallet_address, token_address, decimals):
        """
        Retrieves the balance of a specific ERC-20 token for a wallet address, adjusted for the token's decimals.

        :param wallet_address: Address of the wallet holding the token.
        :param token_address: Address of the ERC-20 token contract.
        :param decimals: The number of decimals the token uses.
        :return: The balance of the token, adjusted for decimals.
        """
        # Conectar al contrato ERC-20 del token
        token_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)

        # Obtener el saldo de la billetera (en la unidad más pequeña del token, por ejemplo, Wei)
        balance = token_contract.functions.balanceOf(wallet_address).call()

        # Ajustar el saldo por los decimales del token y devolverlo
        return balance / (10 ** decimals)

    def get_pool_price(self, pool_address):
        """
        Retrieves the current adjusted price from a Uniswap V3 pool,
        along with the token addresses.

        :param pool_address: The address of the Uniswap V3 pool.
        :return: A tuple containing the adjusted price, token0 address, and token1 address.
        """
        # Conectarse al contrato del pool
        pool_contract = self.web3.eth.contract(address=pool_address, abi=self.pool_abi)

        # Obtener sqrtPriceX96 y el tick actual
        slot0 = pool_contract.functions.slot0().call()
        sqrt_price_x96 = slot0[0]

        # Obtener las direcciones de token0 y token1
        token0_address = pool_contract.functions.token0().call()
        token1_address = pool_contract.functions.token1().call()

        # Obtener los decimales de token0 y token1
        token0_contract = self.web3.eth.contract(address=token0_address, abi=self.erc20_abi)
        token1_contract = self.web3.eth.contract(address=token1_address, abi=self.erc20_abi)

        decimals_token0 = token0_contract.functions.decimals().call()
        decimals_token1 = token1_contract.functions.decimals().call()

        # Calcular el precio actual (ajustado por decimales)
        price_current = (sqrt_price_x96 / (2 ** 96)) ** 2
        adjusted_price = price_current * (10 ** (decimals_token0 - decimals_token1))

        return adjusted_price, token0_address, token1_address

    def verify_balance(self, amount_token0, amount_token1, token0_address, token1_address):
        """
        Verifica si el wallet tiene suficiente balance de ambos tokens para añadir liquidez.

        :param amount_token0: Cantidad de token0 requerida.
        :param amount_token1: Cantidad de token1 requerida.
        :param token0_address: Dirección del token0.
        :param token1_address: Dirección del token1.
        :return: True si hay saldo suficiente, False en caso contrario.
        """
        # Obtener los decimales de los tokens
        decimals_token0 = self.get_token_decimals(token0_address)
        decimals_token1 = self.get_token_decimals(token1_address)

        # Obtener balances de la wallet
        balance_token0 = self.get_token_balance(self.wallet_address, token0_address, decimals_token0)
        balance_token1 = self.get_token_balance(self.wallet_address, token1_address, decimals_token1)

        logger.info(f"Saldo Token0 ({token0_address}): {balance_token0}")
        logger.info(f"Saldo Token1 ({token1_address}): {balance_token1}")

        # Verificar si el saldo es suficiente
        if balance_token0 < amount_token0:
            logger.error(
                f"Saldo insuficiente de token0 ({token0_address}). Requiere {amount_token0}, tiene {balance_token0}")
            return False
        if balance_token1 < amount_token1:
            logger.error(
                f"Saldo insuficiente de token1 ({token1_address}). Requiere {amount_token1}, tiene {balance_token1}")
            return False

        return True

    def add_liquidity(self, amount_usdt, fee=3000, price_range=(0.90, 1.10)):
        """
        Adds liquidity to a Uniswap V3 pool between USDT and WETH.

        :param amount_usdt: Amount of USDT to be added as liquidity.
        :return: Transaction receipt of the liquidity addition.
        :param fee: Fee tier for the pool (e.g., 3000 for 0.3%).
        :param price_range: Tuple with lower and upper price factors
        """

        # todo: defaults to WETH/USDT LP ; customize token pairs

        # Configuración inicial
        usdt_token_address = self.web3.to_checksum_address('0xc2132D05D31c914a87C6611C10748AEb04B58e8F')  # USDT
        weth_token_address = self.web3.to_checksum_address('0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619')  # WETH

        logger.info(f"USDT Address: {usdt_token_address}")
        logger.info(f"WETH Address: {weth_token_address}")

        # Obtener el pool
        pool_address = self.factory_contract.functions.getPool(weth_token_address, usdt_token_address, 3000).call()
        logger.info(f"Pool Address: {pool_address}")

        # Obtener el precio actual del pool y verificar el orden de los tokens
        price_current, token0_address, token1_address = self.get_pool_price(pool_address)

        # Los tokens ya están en el orden correcto como devuelve el contrato
        if token0_address.lower() == usdt_token_address.lower():
            token0 = usdt_token_address
            token1 = weth_token_address
            amount_token0 = amount_usdt  # USDT
            amount_token1 = amount_usdt / price_current  # WETH equivalente
            decimals_token0 = 6  # Decimales de USDT
            decimals_token1 = 18  # Decimales de WETH
        else:
            token0 = weth_token_address
            token1 = usdt_token_address
            amount_token0 = amount_usdt / price_current  # WETH equivalente
            amount_token1 = amount_usdt  # USDT
            decimals_token0 = 18  # Decimales de WETH
            decimals_token1 = 6  # Decimales de USDT

        # Verificar saldo
        if not self.verify_balance(amount_token1, amount_token0, usdt_token_address, weth_token_address):
            return

        #######################################################################
        # Ajustar por decimales antes de enviar la transacción
        amount_token0_wei = int(amount_token0 * (10 ** decimals_token0))  # Token0 en Wei
        amount_token1_wei = int(amount_token1 * (10 ** decimals_token1))  # Token1 en Wei

        slippage_tolerance = 0.70  # Permitir un 25% de slippage
        amount0Min = int(amount_token0_wei * slippage_tolerance)
        amount1Min = int(amount_token1_wei * slippage_tolerance)

        # Calcular ticks
        tick_lower, tick_upper = calculate_ticks(price_current, price_range, decimals_token0, decimals_token1, fee)

        logger.info(f"Adding {amount_token0} of token0 and {amount_token1} of token1 to the pool")

        # Verificar que los ticks sean válidos
        if tick_lower >= tick_upper:
            raise ValueError("tickLower debe ser menor que tickUpper")

        # Aprobar tokens antes de añadir liquidez
        self.approve_token(token0, amount_token0_wei)
        self.approve_token(token1, amount_token1_wei)

        logger.info(f"amount0: {amount_token0_wei}, amount0Min: {amount0Min}")
        logger.info(f"amount1: {amount_token1_wei}, amount1Min: {amount1Min}")

        params = {
            'token0': token0,
            'token1': token1,
            'fee': fee,
            'tickLower': tick_lower,
            'tickUpper': tick_upper,
            'amount0Desired': amount_token0_wei,
            'amount1Desired': amount_token1_wei,
            'amount0Min': amount0Min,
            'amount1Min': amount1Min,
            'recipient': self.wallet_address,
            'deadline': self.web3.eth.get_block('latest')['timestamp'] + 3600  # 1 hora de plazo
        }

        # Construir la transacción
        tx = self.nft_manager_contract.functions.mint(params).build_transaction({
            'from': self.wallet_address,
            'nonce': self.web3.eth.get_transaction_count(self.wallet_address),
            'gas': 3000000,
            'gasPrice': int(self.web3.eth.gas_price) * 2
        })

        # Firmar y enviar la transacción
        signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=os.environ["WALLET_PRIVATE_KEY"])
        tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Transacción enviada, hash: {tx_hash.hex()}")

        # Esperar la confirmación
        tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"Transacción confirmada en el bloque: {tx_receipt.blockNumber}")

        return tx_receipt
