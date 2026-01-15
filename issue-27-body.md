## Description
Create secure storage for OAuth tokens using OS keychain or encrypted SQLite.

## Acceptance Criteria
- [ ] Use `keyring` library for OS keychain access
- [ ] Fallback to encrypted SQLite with `cryptography`
- [ ] Generate encryption key on first run
- [ ] Store key securely in keychain
- [ ] Implement token encryption/decryption
- [ ] Add token expiry checking

## Implementation
```python
# core/token_storage.py
import keyring
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

class TokenStorage:
    """Secure token storage using OS keychain + encrypted SQLite"""
    
    SERVICE_NAME = "oslash-local"
    KEY_NAME = "encryption-key"
    
    def __init__(self, db_session):
        self.db = db_session
        self._fernet = None
    
    async def initialize(self):
        """Initialize encryption key"""
        # Try to get key from keychain
        key = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
        
        if not key:
            # Generate new key and store in keychain
            key = Fernet.generate_key().decode()
            keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, key)
        
        self._fernet = Fernet(key.encode())
    
    def _encrypt(self, plaintext: str) -> str:
        """Encrypt sensitive data"""
        return self._fernet.encrypt(plaintext.encode()).decode()
    
    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt sensitive data"""
        return self._fernet.decrypt(ciphertext.encode()).decode()
    
    async def store(
        self,
        provider: str,
        access_token: str,
        refresh_token: str | None,
        expires_in: int
    ):
        """Store encrypted tokens"""
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Encrypt tokens
        encrypted_access = self._encrypt(access_token)
        encrypted_refresh = self._encrypt(refresh_token) if refresh_token else None
        
        # Upsert to database
        account = await self.db.get(ConnectedAccount, provider)
        if account:
            account.token_encrypted = encrypted_access
            account.refresh_token_encrypted = encrypted_refresh
            account.expires_at = expires_at
        else:
            account = ConnectedAccount(
                id=provider,
                source=provider,
                token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                expires_at=expires_at,
                connected_at=datetime.now()
            )
            self.db.add(account)
        
        await self.db.commit()
    
    async def get(self, provider: str) -> ConnectedAccount | None:
        """Get account with decrypted tokens"""
        account = await self.db.get(ConnectedAccount, provider)
        if not account:
            return None
        
        # Decrypt tokens for use
        account.access_token = self._decrypt(account.token_encrypted)
        if account.refresh_token_encrypted:
            account.refresh_token = self._decrypt(account.refresh_token_encrypted)
        
        return account
    
    async def delete(self, provider: str):
        """Remove account and tokens"""
        account = await self.db.get(ConnectedAccount, provider)
        if account:
            await self.db.delete(account)
            await self.db.commit()
    
    async def list_connected(self) -> list[str]:
        """List all connected providers"""
        result = await self.db.execute(
            select(ConnectedAccount.source)
        )
        return [row[0] for row in result.fetchall()]
```

## Keychain Fallback for Linux
```python
# For systems without keychain support
class FileBasedKeyStorage:
    """Fallback key storage using encrypted file"""
    
    def __init__(self, key_file: Path):
        self.key_file = key_file
    
    def get_or_create_key(self, password: str) -> bytes:
        """Get or create encryption key"""
        if self.key_file.exists():
            # Derive key from password and stored salt
            with open(self.key_file, "rb") as f:
                salt = f.read()
            return self._derive_key(password, salt)
        else:
            # Generate new salt and store it
            salt = os.urandom(16)
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_file, "wb") as f:
                f.write(salt)
            self.key_file.chmod(0o600)  # Restrict permissions
            return self._derive_key(password, salt)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
```

## Security Considerations
- Tokens are never stored in plaintext
- Encryption key is stored in OS keychain (most secure)
- Fallback uses PBKDF2 with high iteration count
- File permissions restricted to owner only
- Tokens automatically refreshed before expiry

## Dependencies
- keyring>=24.3.0
- cryptography>=42.0.0

## Estimate
4 hours

