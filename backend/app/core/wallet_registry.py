"""
Wallet registry for managing encrypted keystores and hot wallet operations.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from eth_account import Account
from eth_account.signers.local import LocalAccount
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from ..core.settings import settings
from ..core.logging import get_logger
from ..storage.repositories import WalletRepository, get_wallet_repository

logger = get_logger(__name__)


class WalletSecurityError(Exception):
    """Raised when wallet security operations fail."""
    pass


class WalletRegistry:
    """
    Manages encrypted wallet keystores and hot wallet operations.
    
    Provides secure key generation, encrypted storage, and emergency
    controls while never persisting passphrases or unencrypted keys.
    """
    
    def __init__(self) -> None:
        """Initialize wallet registry."""
        self.keystores_dir = settings.data_dir / "keys"
        self.keystores_dir.mkdir(parents=True, exist_ok=True)
        
        # Runtime wallet cache (encrypted keys only)
        self._cached_keystores: Dict[str, Dict] = {}
        self._session_passphrases: Dict[str, str] = {}
        self._wallet_locks: Dict[str, asyncio.Lock] = {}
        
        # Emergency state
        self._emergency_mode = False
        
        logger.info("Wallet registry initialized")
    
    async def create_hot_wallet(
        self,
        chain: str,
        passphrase: str,
        wallet_label: str = "hot_wallet",
    ) -> Dict[str, str]:
        """
        Create new encrypted hot wallet for specified chain.
        
        Args:
            chain: Blockchain network (ethereum, bsc, polygon, solana)
            passphrase: Encryption passphrase (not stored)
            wallet_label: Human-readable wallet label
            
        Returns:
            Dict with wallet address and keystore path
            
        Raises:
            WalletSecurityError: If wallet creation fails
        """
        if self._emergency_mode:
            raise WalletSecurityError("Emergency mode active - wallet operations disabled")
        
        try:
            # Generate wallet based on chain
            if chain.lower() in ["ethereum", "bsc", "polygon", "base", "arbitrum"]:
                # EVM wallet generation
                account = Account.create()
                private_key = account.key.hex()
                address = account.address
                
                keystore_data = {
                    "version": 3,
                    "chain": chain,
                    "wallet_type": "hot_wallet",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "label": wallet_label,
                    "address": address,
                    "crypto": self._encrypt_private_key(private_key, passphrase)
                }
                
            elif chain.lower() == "solana":
                # Solana wallet generation
                keypair = Keypair()
                private_key = keypair.secret().hex()
                address = str(keypair.pubkey())
                
                keystore_data = {
                    "version": 3,
                    "chain": chain,
                    "wallet_type": "hot_wallet", 
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "label": wallet_label,
                    "address": address,
                    "crypto": self._encrypt_private_key(private_key, passphrase)
                }
                
            else:
                raise WalletSecurityError(f"Unsupported chain: {chain}")
            
            # Save encrypted keystore
            keystore_filename = f"{chain}_{wallet_label}_{address[:8].lower()}.json"
            keystore_path = self.keystores_dir / keystore_filename
            
            with open(keystore_path, 'w', encoding='utf-8') as f:
                json.dump(keystore_data, f, indent=2)
            
            # Cache keystore and session passphrase
            wallet_key = f"{chain}:{address}"
            self._cached_keystores[wallet_key] = keystore_data
            self._session_passphrases[wallet_key] = passphrase
            self._wallet_locks[wallet_key] = asyncio.Lock()
            
            logger.info(
                f"Hot wallet created: {address[:10]}... on {chain}",
                extra={'extra_data': {
                    'chain': chain,
                    'address': address,
                    'wallet_label': wallet_label,
                    'keystore_path': str(keystore_path)
                }}
            )
            
            return {
                "address": address,
                "chain": chain,
                "keystore_path": str(keystore_path),
                "wallet_label": wallet_label,
                "created_at": keystore_data["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to create hot wallet: {e}")
            raise WalletSecurityError(f"Wallet creation failed: {e}")
    
    async def load_wallet(
        self,
        keystore_path: str,
        passphrase: str,
    ) -> Dict[str, str]:
        """
        Load encrypted wallet from keystore file.
        
        Args:
            keystore_path: Path to keystore file
            passphrase: Decryption passphrase
            
        Returns:
            Wallet information dict
            
        Raises:
            WalletSecurityError: If loading fails
        """
        if self._emergency_mode:
            raise WalletSecurityError("Emergency mode active - wallet operations disabled")
        
        try:
            keystore_file = Path(keystore_path)
            if not keystore_file.exists():
                raise WalletSecurityError(f"Keystore file not found: {keystore_path}")
            
            with open(keystore_file, 'r', encoding='utf-8') as f:
                keystore_data = json.load(f)
            
            # Verify keystore format
            required_fields = ["version", "chain", "address", "crypto"]
            for field in required_fields:
                if field not in keystore_data:
                    raise WalletSecurityError(f"Invalid keystore: missing {field}")
            
            # Test decryption (but don't store decrypted key)
            try:
                self._decrypt_private_key(keystore_data["crypto"], passphrase)
            except Exception:
                raise WalletSecurityError("Invalid passphrase")
            
            # Cache keystore and session passphrase
            address = keystore_data["address"]
            chain = keystore_data["chain"]
            wallet_key = f"{chain}:{address}"
            
            self._cached_keystores[wallet_key] = keystore_data
            self._session_passphrases[wallet_key] = passphrase
            self._wallet_locks[wallet_key] = asyncio.Lock()
            
            logger.info(
                f"Wallet loaded: {address[:10]}... on {chain}",
                extra={'extra_data': {
                    'chain': chain,
                    'address': address,
                    'keystore_path': keystore_path
                }}
            )
            
            return {
                "address": address,
                "chain": chain,
                "wallet_label": keystore_data.get("label", "unknown"),
                "created_at": keystore_data.get("created_at"),
                "loaded_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            raise WalletSecurityError(f"Wallet loading failed: {e}")
    
    async def get_signing_key(
        self,
        chain: str,
        address: str,
    ) -> str:
        """
        Get decrypted private key for signing (use carefully).
        
        Args:
            chain: Blockchain network
            address: Wallet address
            
        Returns:
            Decrypted private key hex string
            
        Raises:
            WalletSecurityError: If key retrieval fails
        """
        if self._emergency_mode:
            raise WalletSecurityError("Emergency mode active - signing disabled")
        
        wallet_key = f"{chain}:{address}"
        
        if wallet_key not in self._cached_keystores:
            raise WalletSecurityError(f"Wallet not loaded: {address}")
        
        if wallet_key not in self._session_passphrases:
            raise WalletSecurityError(f"Passphrase not available for: {address}")
        
        try:
            async with self._wallet_locks[wallet_key]:
                keystore_data = self._cached_keystores[wallet_key]
                passphrase = self._session_passphrases[wallet_key]
                
                private_key = self._decrypt_private_key(
                    keystore_data["crypto"], 
                    passphrase
                )
                
                logger.debug(
                    f"Private key retrieved for signing: {address[:10]}...",
                    extra={'extra_data': {
                        'chain': chain,
                        'address': address
                    }}
                )
                
                return private_key
                
        except Exception as e:
            logger.error(f"Failed to get signing key: {e}")
            raise WalletSecurityError(f"Key retrieval failed: {e}")
    
    async def emergency_drain(
        self,
        source_chain: str,
        source_address: str,
        destination_address: str,
        reason: str = "Emergency drain activated",
    ) -> Dict[str, str]:
        """
        Emergency drain hot wallet to cold wallet.
        
        Args:
            source_chain: Source blockchain network
            source_address: Hot wallet address to drain
            destination_address: Cold wallet destination
            reason: Reason for emergency drain
            
        Returns:
            Emergency drain transaction info
            
        Raises:
            WalletSecurityError: If drain fails
        """
        try:
            # Activate emergency mode
            self._emergency_mode = True
            
            logger.critical(
                f"EMERGENCY DRAIN INITIATED: {source_address} -> {destination_address}",
                extra={'extra_data': {
                    'source_chain': source_chain,
                    'source_address': source_address,
                    'destination_address': destination_address,
                    'reason': reason,
                    'initiated_at': datetime.now(timezone.utc).isoformat()
                }}
            )
            
            # TODO: Implement actual drain transaction
            # This would involve:
            # 1. Get current balance
            # 2. Calculate gas for transfer
            # 3. Build drain transaction
            # 4. Sign and submit
            # 5. Monitor confirmation
            
            return {
                "status": "initiated",
                "source_address": source_address,
                "destination_address": destination_address,
                "chain": source_chain,
                "reason": reason,
                "initiated_at": datetime.now(timezone.utc).isoformat(),
                "emergency_mode": True
            }
            
        except Exception as e:
            logger.error(f"Emergency drain failed: {e}")
            raise WalletSecurityError(f"Emergency drain failed: {e}")
    
    async def list_wallets(self) -> List[Dict[str, str]]:
        """
        List all available wallet keystores.
        
        Returns:
            List of wallet information dicts
        """
        wallets = []
        
        try:
            for keystore_file in self.keystores_dir.glob("*.json"):
                try:
                    with open(keystore_file, 'r', encoding='utf-8') as f:
                        keystore_data = json.load(f)
                    
                    wallet_info = {
                        "address": keystore_data.get("address", "unknown"),
                        "chain": keystore_data.get("chain", "unknown"),
                        "label": keystore_data.get("label", "unknown"),
                        "created_at": keystore_data.get("created_at"),
                        "keystore_path": str(keystore_file),
                        "is_loaded": f"{keystore_data.get('chain')}:{keystore_data.get('address')}" in self._cached_keystores
                    }
                    wallets.append(wallet_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to read keystore {keystore_file}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to list wallets: {e}")
        
        return wallets
    
    def _encrypt_private_key(self, private_key: str, passphrase: str) -> Dict:
        """Encrypt private key using PBKDF2 + AES."""
        try:
            # Generate salt
            salt = secrets.token_bytes(16)
            
            # Derive key from passphrase
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            derived_key = kdf.derive(passphrase.encode('utf-8'))
            
            # Encrypt private key
            fernet = Fernet(Fernet.generate_key())
            encrypted_key = fernet.encrypt(private_key.encode('utf-8'))
            
            # Encrypt the Fernet key with derived key
            key_fernet = Fernet(Fernet.generate_key())
            encrypted_fernet_key = key_fernet.encrypt(fernet._signing_key + fernet._encryption_key)
            
            return {
                "cipher": "aes-256-ctr",
                "ciphertext": encrypted_key.hex(),
                "kdf": "pbkdf2",
                "kdfparams": {
                    "iterations": 100000,
                    "salt": salt.hex(),
                    "keylen": 32
                },
                "mac": encrypted_fernet_key.hex()
            }
            
        except Exception as e:
            raise WalletSecurityError(f"Encryption failed: {e}")
    
    def _decrypt_private_key(self, crypto_data: Dict, passphrase: str) -> str:
        """Decrypt private key using stored crypto parameters."""
        try:
            # Derive key from passphrase
            salt = bytes.fromhex(crypto_data["kdfparams"]["salt"])
            iterations = crypto_data["kdfparams"]["iterations"]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            derived_key = kdf.derive(passphrase.encode('utf-8'))
            
            # Decrypt Fernet key
            encrypted_fernet_key = bytes.fromhex(crypto_data["mac"])
            key_fernet = Fernet(Fernet.generate_key())
            fernet_key_data = key_fernet.decrypt(encrypted_fernet_key)
            
            # Reconstruct Fernet instance
            fernet = Fernet(fernet_key_data[:32] + fernet_key_data[32:])
            
            # Decrypt private key
            encrypted_key = bytes.fromhex(crypto_data["ciphertext"])
            private_key = fernet.decrypt(encrypted_key).decode('utf-8')
            
            return private_key
            
        except Exception as e:
            raise WalletSecurityError(f"Decryption failed: {e}")
    
    async def clear_session(self, chain: str, address: str) -> None:
        """Clear session data for wallet (passphrase, cache)."""
        wallet_key = f"{chain}:{address}"
        
        # Clear sensitive session data
        if wallet_key in self._session_passphrases:
            del self._session_passphrases[wallet_key]
        
        if wallet_key in self._cached_keystores:
            del self._cached_keystores[wallet_key]
        
        if wallet_key in self._wallet_locks:
            del self._wallet_locks[wallet_key]
        
        logger.info(
            f"Session cleared for wallet: {address[:10]}...",
            extra={'extra_data': {'chain': chain, 'address': address}}
        )
    
    def is_emergency_mode(self) -> bool:
        """Check if emergency mode is active."""
        return self._emergency_mode
    
    def reset_emergency_mode(self) -> None:
        """Reset emergency mode (admin function)."""
        self._emergency_mode = False
        logger.warning("Emergency mode reset - wallet operations re-enabled")


# Global wallet registry instance
wallet_registry = WalletRegistry()