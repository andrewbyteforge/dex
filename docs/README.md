# Installation Guide

## 📋 System Requirements

### Minimum Requirements
- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Python**: 3.11 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space minimum, 10GB recommended
- **Network**: Stable internet connection for blockchain RPC access

### Recommended Specifications
- **CPU**: 4+ cores for optimal performance
- **RAM**: 16GB for large-scale operations
- **Storage**: SSD with 50GB+ free space
- **Network**: High-speed connection (100+ Mbps) for fast execution

## 🛠️ Installation Methods

### Method 1: Quick Install (Recommended)

#### Windows
```powershell
# 1. Install Python 3.11+ from python.org
# 2. Download DEX Sniper Pro
git clone https://github.com/your-repo/dex-sniper-pro.git
cd dex-sniper-pro

# 3. Run the installation script
.\scripts\install.bat
```

#### macOS/Linux
```bash
# 1. Ensure Python 3.11+ is installed
python3 --version

# 2. Download DEX Sniper Pro
git clone https://github.com/your-repo/dex-sniper-pro.git
cd dex-sniper-pro

# 3. Run the installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

### Method 2: Manual Installation

#### Step 1: Clone Repository
```bash
git clone https://github.com/your-repo/dex-sniper-pro.git
cd dex-sniper-pro
```

#### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

#### Step 3: Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies (requires Node.js)
cd frontend
npm install
cd ..
```

#### Step 4: Initialize Database
```bash
# Set up database
python -m backend.app.storage.database
```

#### Step 5: Configure Environment
```bash
# Copy example configuration
cp config/env.example .env

# Edit configuration (see Configuration Guide)
# Windows: notepad .env
# macOS/Linux: nano .env
```

## ⚙️ Configuration

### Environment Variables
Create a `.env` file in the project root:

```env
# Basic Configuration
ENVIRONMENT=development
DEBUG=true
SERVICE_MODE=free

# Database
DATABASE_URL=sqlite:///./data/app.db

# API Configuration
API_HOST=127.0.0.1
API_PORT=8000

# Blockchain RPC Endpoints (use your own for better performance)
ETHEREUM_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BSC_RPC_URL=https://bsc-dataseed.binance.org/
POLYGON_RPC_URL=https://polygon-rpc.com/
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# External APIs
COINGECKO_API_KEY=your_coingecko_api_key
DEXSCREENER_API_KEY=your_dexscreener_api_key

# Security
SECRET_KEY=your_very_secure_random_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# AI Features (optional)
AI_FEATURES_ENABLED=true
AUTO_TUNING_MODE=advisory

# Alerting (optional)
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### RPC Configuration
For optimal performance, obtain dedicated RPC endpoints:

#### Ethereum
- **Alchemy**: https://www.alchemy.com/
- **Infura**: https://infura.io/
- **QuickNode**: https://www.quicknode.com/

#### BSC
- **BSC Official**: https://docs.binance.org/smart-chain/developer/rpc.html
- **NodeReal**: https://nodereal.io/

#### Polygon
- **Polygon Official**: https://docs.polygon.technology/
- **Alchemy**: https://www.alchemy.com/

#### Solana
- **Solana Official**: https://docs.solana.com/cluster/rpc-endpoints
- **QuickNode**: https://www.quicknode.com/

## 🚀 Starting the Application

### Development Mode
```bash
# Terminal 1: Start Backend
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Start Frontend
cd frontend
npm start
```

### Production Mode
```bash
# Start the application
python scripts/start.py --environment production

# Or use the deployment script
python scripts/deploy.py --current-version 0.0.0 --target-version 1.0.0
```

## ✅ Verification

### Health Check
1. **Backend Health**: Visit http://localhost:8000/api/v1/health
2. **Frontend Access**: Visit http://localhost:3000
3. **API Documentation**: Visit http://localhost:8000/docs

### Quick Test
```bash
# Run system diagnostics
python -c "
import asyncio
from backend.app.core.self_test import run_quick_health_check

async def test():
    result = await run_quick_health_check()
    print(f'Health Check: {result.passed_count}/{len(result.tests)} tests passed')

asyncio.run(test())
"
```

## 🛡️ Security Setup

### 1. Secure File Permissions
```bash
# Set secure permissions
chmod 600 .env
chmod 600 data/app.db
```

### 2. Generate Secure Keys
```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Wallet Security
- **Never store private keys in configuration files**
- **Use hardware wallets for large amounts**
- **Enable all available security features**

## 🔄 Updates

### Automatic Updates
```bash
# Check for updates
python scripts/update.py --check

# Install updates
python scripts/update.py --install
```

### Manual Updates
```bash
# Backup current installation
python scripts/backup.py --create

# Pull latest changes
git pull origin main

# Update dependencies
pip install -r backend/requirements.txt --upgrade
cd frontend && npm update && cd ..

# Run migrations
python scripts/migrate.py
```

## 🐛 Troubleshooting

### Common Issues

#### Installation Fails
```bash
# Clear cache and retry
pip cache purge
rm -rf venv
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r backend/requirements.txt
```

#### Database Errors
```bash
# Reset database
rm data/app.db*
python -m backend.app.storage.database
```

#### Permission Errors (Linux/macOS)
```bash
# Fix permissions
chmod +x scripts/*.sh
sudo chown -R $USER:$USER .
```

#### Port Already in Use
```bash
# Find and kill process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS:
lsof -ti:8000 | xargs kill
```

### Performance Issues

#### Slow RPC Responses
- Switch to premium RPC providers
- Add multiple RPC endpoints for redundancy
- Check network connectivity

#### High Memory Usage
- Reduce concurrent operations
- Check for memory leaks in logs
- Restart the application periodically

### Getting Help

1. **Check Logs**: Review `data/logs/app-YYYY-MM-DD.jsonl`
2. **Run Diagnostics**: Use `python -m backend.app.core.self_test`
3. **Review Documentation**: Check the [Troubleshooting Guide](admin/troubleshooting.md)
4. **Community Support**: Visit our community forums

## 📚 Next Steps

After successful installation:

1. **Configuration**: Review the [Configuration Guide](configuration.md)
2. **First Trade**: Follow the [First Trade Tutorial](tutorials/first-trade.md)
3. **Security**: Read the [Security Overview](security/README.md)
4. **Features**: Explore [User Guides](user-guides/)

---

## 🔧 Development Installation

For developers contributing to DEX Sniper Pro:

### Additional Dependencies
```bash
# Install development dependencies
pip install -r backend/requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest backend/tests/
```

### IDE Setup
- **VS Code**: Use the provided `.vscode/settings.json`
- **PyCharm**: Configure Python interpreter to use the venv
- **Recommended Extensions**: Python, Pylance, Black Formatter

---

*For detailed configuration options, see the [Configuration Guide](configuration.md)*