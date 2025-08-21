# Quick Start Guide

Get up and running with DEX Sniper Pro in 5 minutes! This guide covers the essential steps to start trading.

## 🎯 Prerequisites

- ✅ Python 3.11+ installed
- ✅ Git installed
- ✅ Web browser (Chrome/Firefox recommended)
- ✅ Crypto wallet (MetaMask, Trust Wallet, etc.)
- ✅ Some ETH/BNB/MATIC for gas fees

## ⚡ 5-Minute Setup

### Step 1: Download & Install (2 minutes)
```bash
# Clone and enter directory
git clone https://github.com/your-repo/dex-sniper-pro.git
cd dex-sniper-pro

# Quick install (Windows)
.\scripts\install.bat

# Quick install (macOS/Linux)
chmod +x scripts/install.sh && ./scripts/install.sh
```

### Step 2: Basic Configuration (1 minute)
```bash
# Copy example config
cp config/env.example .env

# Edit basic settings (use any text editor)
nano .env
```

**Minimal Configuration**:
```env
ENVIRONMENT=development
DEBUG=true
API_PORT=8000
SECRET_KEY=your_random_secret_key_here
```

### Step 3: Start Application (1 minute)
```bash
# Start backend (Terminal 1)
cd backend && python -m uvicorn app.main:app --reload --port 8000

# Start frontend (Terminal 2)
cd frontend && npm start
```

### Step 4: Access Interface (30 seconds)
1. **Open Browser**: Go to http://localhost:3000
2. **Connect Wallet**: Click "Connect Wallet" and select your provider
3. **Verify Connection**: Check that your wallet balance appears

### Step 5: Health Check (30 seconds)
- Visit http://localhost:8000/api/v1/health
- Should show: `{"status": "healthy", "uptime": "..."}`

## 🎮 Your First Trade

### Quick Demo Trade
1. **Go to Trading Interface**: Click "Trading" in the navigation
2. **Select Chain**: Choose "BSC" (fastest for testing)
3. **Choose Pair**: WBNB → BUSD (stable, high liquidity)
4. **Set Amount**: Start with 0.01 BNB
5. **Get Quote**: Click "Get Quote"
6. **Review Trade**: Check price impact and fees
7. **Execute**: Click "Execute Trade" (connects to your wallet)

### Safety First! 🛡️
- **Start Small**: Use tiny amounts for first trades
- **Check Slippage**: Keep under 5% for established tokens
- **Verify Contracts**: Ensure token addresses are correct
- **Test Mode**: Use testnets first if available

## 🎛️ Essential Settings

### Risk Management (Recommended)
```javascript
// In the UI Risk Settings:
Max Position Size: 0.1 ETH/BNB  // Start conservative
Max Slippage: 3%                // Prevent bad fills
Gas Price: Auto                 // Let system optimize
Daily Loss Limit: 0.5 ETH/BNB   // Protect capital
```

### Chain Priority
```javascript
// Recommended order for beginners:
1. BSC        // Lowest fees
2. Polygon    // Fast and cheap
3. Base       // Growing ecosystem
4. Ethereum   // Highest liquidity (high fees)
```

## 🚀 Key Features Overview

### 1. Manual Trading
- **Real-time Quotes**: Aggregated from multiple DEXs
- **Price Impact**: See how your trade affects price
- **Gas Optimization**: Automatic gas price suggestions
- **Multi-chain**: Trade across 4+ blockchains

### 2. Risk Controls
- **Position Limits**: Automatic position size limits
- **Slippage Protection**: Reject trades with high slippage
- **Contract Verification**: Basic token safety checks
- **Emergency Stop**: Instant trading halt

### 3. Portfolio Tracking
- **Live Balances**: Real-time wallet balance updates
- **PnL Tracking**: Profit/loss on all positions
- **Transaction History**: Complete trade log
- **Performance Analytics**: Returns and risk metrics

### 4. AI Features (Advanced)
- **Auto-tuning**: Optimize settings based on performance
- **Risk Explanation**: AI explains trade risks
- **Anomaly Detection**: Alerts for unusual market behavior
- **Decision Journal**: AI insights on trading decisions

## 🎯 Common First Tasks

### Set Up Alerts
1. Go to Settings → Alerts
2. Add your email/Telegram
3. Configure alert preferences
4. Test with a sample alert

### Create Your First Preset
1. Go to Trading → Presets
2. Click "Create New Preset"
3. Name: "Conservative Trading"
4. Set safe parameters:
   - Max Position: 0.05 ETH
   - Slippage: 2%
   - Gas: Normal
5. Save and activate

### Review Security Settings
1. Go to Settings → Security
2. **Enable 2FA** if available
3. **Review Permissions**: Check what the app can access
4. **Backup Settings**: Export your configuration

## 📊 Monitoring Your Performance

### Daily Checklist
- [ ] Check portfolio balance
- [ ] Review recent trades
- [ ] Monitor risk metrics
- [ ] Check system health
- [ ] Review alerts/notifications

### Weekly Review
- [ ] Analyze performance vs benchmarks
- [ ] Adjust risk parameters if needed
- [ ] Review and update presets
- [ ] Check for system updates
- [ ] Backup important data

## 🆘 Quick Troubleshooting

### Wallet Won't Connect
1. **Refresh page** and try again
2. **Check wallet**: Ensure it's unlocked
3. **Clear cache**: Browser cache/cookies
4. **Try different wallet**: MetaMask vs WalletConnect

### Quotes Not Loading
1. **Check internet**: Ensure stable connection
2. **RPC Issues**: Try different chain
3. **Restart backend**: Stop and restart API server
4. **Check logs**: Look at browser console (F12)

### Trade Failing
1. **Insufficient Balance**: Check you have enough tokens + gas
2. **High Slippage**: Market moved, increase tolerance or retry
3. **Gas Too Low**: Increase gas price setting
4. **Network Congestion**: Wait and retry

### Performance Issues
1. **Close unused tabs**: Free up browser memory
2. **Restart application**: Stop backend/frontend, restart
3. **Check CPU**: High CPU usage can slow things down
4. **Update browser**: Ensure latest version

## 🔄 What's Next?

### Immediate Next Steps (Today)
1. **Complete Your Profile**: Add contact info for alerts
2. **Read Risk Guide**: Understanding [Risk Management](user-guides/risk-management.md)
3. **Make Small Trades**: Practice with tiny amounts
4. **Join Community**: Connect with other users

### This Week
1. **Strategy Development**: Learn about [Trading Strategies](user-guides/strategies.md)
2. **Advanced Features**: Explore [Advanced Orders](user-guides/advanced-orders.md)
3. **Performance Analysis**: Set up [Analytics](advanced/analytics.md)
4. **Automation**: Consider [Autotrade](advanced/autotrade.md) for repetitive tasks

### Advanced Goals (Next Month)
1. **AI Integration**: Enable [AI Features](ai/) for optimization
2. **Multi-chain**: Expand to other blockchains
3. **Backtesting**: Use [Simulation](advanced/simulation.md) to test strategies
4. **API Usage**: Integrate with external tools

## 📚 Essential Reading

**Must Read First**:
- [Risk Management Guide](user-guides/risk-management.md) - **Critical for safety**
- [Security Overview](security/README.md) - Protect your funds
- [Trading Interface Guide](user-guides/trading-interface.md) - Master the UI

**Read This Week**:
- [Configuration Guide](configuration.md) - Optimize your setup
- [Multi-chain Trading](advanced/multi-chain.md) - Expand opportunities
- [Troubleshooting](admin/troubleshooting.md) - Solve common issues

## 💡 Pro Tips for Beginners

### Start Conservative
- Use **testnet** first if available
- Trade only **well-known tokens** initially
- Keep **position sizes small** (< 1% of portfolio)
- Focus on **learning** over profits

### Risk Management
- **Never risk more than you can afford to lose**
- Set **daily/weekly loss limits**
- Use **stop losses** for larger positions
- **Diversify** across different strategies/tokens

### Performance Tracking
- **Log everything**: Keep detailed records
- **Review regularly**: Weekly performance analysis
- **Learn from mistakes**: Study failed trades
- **Iterate and improve**: Gradually optimize

### Community & Learning
- **Ask questions**: Use community forums
- **Share experiences**: Help other beginners
- **Stay updated**: Follow project updates
- **Learn continuously**: DEX trading evolves quickly

---

## 🎉 Congratulations!

You're now ready to start trading with DEX Sniper Pro! Remember:

- **Start small and learn**
- **Prioritize safety over profits**
- **Use the community for support**
- **Keep learning and improving**

For detailed guides on specific features, check out our [User Guides](user-guides/) section.

---

*Need help? Check the [FAQ](reference/faq.md) or [Troubleshooting Guide](admin/troubleshooting.md)*