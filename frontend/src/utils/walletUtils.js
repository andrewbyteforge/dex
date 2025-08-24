/**
 * Wallet Utilities - Helper functions and formatters for wallet operations.
 * 
 * Provides comprehensive utility functions for address formatting, validation,
 * error handling, and wallet-related calculations with production logging.
 *
 * File: frontend/src/utils/walletUtils.js
 */

import { PublicKey } from '@solana/web3.js';

/**
 * Structured logging for wallet utilities
 */
const logWalletUtils = (level, message, data = {}) => {
  const logEntry = {
    timestamp: new Date().toISOString(),
    level,
    component: 'walletUtils',
    trace_id: data.trace_id || `utils_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    message,
    ...data
  };

  switch (level) {
    case 'error':
      console.error(`[WalletUtils] ${message}`, logEntry);
      break;
    case 'warn':
      console.warn(`[WalletUtils] ${message}`, logEntry);
      break;
    case 'info':
      console.info(`[WalletUtils] ${message}`, logEntry);
      break;
    case 'debug':
      console.debug(`[WalletUtils] ${message}`, logEntry);
      break;
    default:
      console.log(`[WalletUtils] ${message}`, logEntry);
  }

  return logEntry.trace_id;
};

/**
 * Chain configurations for validation and formatting
 */
export const SUPPORTED_CHAINS = {
  ethereum: {
    name: 'Ethereum',
    shortName: 'ETH',
    chainId: 1,
    type: 'evm',
    nativeCurrency: 'ETH',
    addressLength: 42,
    addressPrefix: '0x',
    blockExplorer: 'https://etherscan.io',
    color: '#627EEA',
    icon: '⟠'
  },
  bsc: {
    name: 'BNB Smart Chain',
    shortName: 'BSC',
    chainId: 56,
    type: 'evm',
    nativeCurrency: 'BNB',
    addressLength: 42,
    addressPrefix: '0x',
    blockExplorer: 'https://bscscan.com',
    color: '#F3BA2F',
    icon: '🟡'
  },
  polygon: {
    name: 'Polygon',
    shortName: 'MATIC',
    chainId: 137,
    type: 'evm',
    nativeCurrency: 'MATIC',
    addressLength: 42,
    addressPrefix: '0x',
    blockExplorer: 'https://polygonscan.com',
    color: '#8247E5',
    icon: '🟣'
  },
  base: {
    name: 'Base',
    shortName: 'BASE',
    chainId: 8453,
    type: 'evm',
    nativeCurrency: 'ETH',
    addressLength: 42,
    addressPrefix: '0x',
    blockExplorer: 'https://basescan.org',
    color: '#0052FF',
    icon: '🔵'
  },
  arbitrum: {
    name: 'Arbitrum One',
    shortName: 'ARB',
    chainId: 42161,
    type: 'evm',
    nativeCurrency: 'ETH',
    addressLength: 42,
    addressPrefix: '0x',
    blockExplorer: 'https://arbiscan.io',
    color: '#28A0F0',
    icon: '🌐'
  },
  solana: {
    name: 'Solana',
    shortName: 'SOL',
    chainId: 'solana',
    type: 'solana',
    nativeCurrency: 'SOL',
    addressLength: 44,
    addressPrefix: null,
    blockExplorer: 'https://explorer.solana.com',
    color: '#9945FF',
    icon: '☀️'
  }
};

/**
 * Wallet types and their configurations
 */
export const WALLET_TYPES = {
  metamask: {
    name: 'MetaMask',
    type: 'evm',
    icon: '🦊',
    downloadUrl: 'https://metamask.io/download/',
    chains: ['ethereum', 'bsc', 'polygon', 'base', 'arbitrum'],
    features: ['signTransaction', 'switchChain', 'addChain', 'watchAsset']
  },
  walletconnect: {
    name: 'WalletConnect',
    type: 'evm',
    icon: '🔗',
    downloadUrl: 'https://walletconnect.com/',
    chains: ['ethereum', 'bsc', 'polygon', 'base', 'arbitrum'],
    features: ['signTransaction', 'switchChain']
  },
  phantom: {
    name: 'Phantom',
    type: 'solana',
    icon: '👻',
    downloadUrl: 'https://phantom.app/',
    chains: ['solana'],
    features: ['signTransaction', 'signMessage', 'signAndSendTransaction']
  },
  solflare: {
    name: 'Solflare',
    type: 'solana',
    icon: '☀️',
    downloadUrl: 'https://solflare.com/',
    chains: ['solana'],
    features: ['signTransaction', 'signMessage']
  }
};

/**
 * Common error codes and their user-friendly messages
 */
export const WALLET_ERROR_CODES = {
  4001: {
    message: 'User rejected the request',
    category: 'user_rejected',
    userMessage: 'Transaction was cancelled. Please try again if you want to proceed.',
    recoveryAction: 'retry'
  },
  4100: {
    message: 'Unauthorized method',
    category: 'unauthorized',
    userMessage: 'This action is not authorized. Please check your wallet permissions.',
    recoveryAction: 'reconnect'
  },
  4200: {
    message: 'Unsupported method',
    category: 'unsupported',
    userMessage: 'This wallet does not support this action.',
    recoveryAction: 'try_different_wallet'
  },
  4900: {
    message: 'Disconnected from all chains',
    category: 'disconnected',
    userMessage: 'Wallet is disconnected. Please reconnect to continue.',
    recoveryAction: 'reconnect'
  },
  4901: {
    message: 'Chain not added to wallet',
    category: 'chain_not_added',
    userMessage: 'This network is not added to your wallet. Please add it first.',
    recoveryAction: 'add_chain'
  },
  '-32603': {
    message: 'Internal JSON-RPC error',
    category: 'rpc_error',
    userMessage: 'Network error occurred. Please try again or switch networks.',
    recoveryAction: 'retry_or_switch_network'
  }
};

/**
 * Address Formatting and Validation
 */

/**
 * Format an address for display with customizable truncation
 */
export const formatAddress = (address, options = {}) => {
  const {
    startChars = 6,
    endChars = 4,
    separator = '...',
    includePrefix = true,
    uppercase = false
  } = options;

  try {
    if (!address || typeof address !== 'string') {
      logWalletUtils('warn', 'Invalid address provided for formatting', {
        address: typeof address,
        options
      });
      return '';
    }

    // Handle empty or too short addresses
    if (address.length <= startChars + endChars) {
      return uppercase ? address.toUpperCase() : address;
    }

    // Format address
    let formattedAddress;
    
    if (includePrefix && address.startsWith('0x')) {
      // EVM address with 0x prefix
      formattedAddress = `${address.substring(0, startChars + 2)}${separator}${address.substring(address.length - endChars)}`;
    } else {
      // Solana address or EVM without prefix preference
      formattedAddress = `${address.substring(0, startChars)}${separator}${address.substring(address.length - endChars)}`;
    }

    return uppercase ? formattedAddress.toUpperCase() : formattedAddress;

  } catch (error) {
    logWalletUtils('error', 'Address formatting failed', {
      address: address?.substring(0, 10) + '...',
      error: error.message,
      options
    });
    return address || '';
  }
};

/**
 * Validate an address for a specific chain
 */
export const validateAddress = (address, chain) => {
  const trace_id = logWalletUtils('debug', 'Validating address format', {
    chain,
    address_length: address?.length
  });

  try {
    if (!address || typeof address !== 'string') {
      return {
        isValid: false,
        error: 'Address must be a non-empty string',
        trace_id
      };
    }

    const chainConfig = SUPPORTED_CHAINS[chain];
    if (!chainConfig) {
      return {
        isValid: false,
        error: `Unsupported chain: ${chain}`,
        trace_id
      };
    }

    if (chainConfig.type === 'evm') {
      return validateEVMAddress(address, chainConfig, trace_id);
    } else if (chainConfig.type === 'solana') {
      return validateSolanaAddress(address, trace_id);
    } else {
      return {
        isValid: false,
        error: `Unknown chain type: ${chainConfig.type}`,
        trace_id
      };
    }

  } catch (error) {
    logWalletUtils('error', 'Address validation failed', {
      error: error.message,
      chain,
      trace_id
    });

    return {
      isValid: false,
      error: `Validation error: ${error.message}`,
      trace_id
    };
  }
};

/**
 * Validate EVM address format
 */
const validateEVMAddress = (address, chainConfig, trace_id) => {
  // Check if address starts with 0x
  if (!address.startsWith(chainConfig.addressPrefix)) {
    return {
      isValid: false,
      error: `EVM address must start with ${chainConfig.addressPrefix}`,
      trace_id
    };
  }

  // Check length
  if (address.length !== chainConfig.addressLength) {
    return {
      isValid: false,
      error: `EVM address must be exactly ${chainConfig.addressLength} characters`,
      trace_id
    };
  }

  // Check if contains only valid hex characters
  const hexPart = address.substring(2);
  if (!/^[0-9a-fA-F]+$/.test(hexPart)) {
    return {
      isValid: false,
      error: 'EVM address contains invalid characters',
      trace_id
    };
  }

  return {
    isValid: true,
    trace_id
  };
};

/**
 * Validate Solana address format
 */
const validateSolanaAddress = (address, trace_id) => {
  try {
    // Use Solana's PublicKey constructor for validation
    new PublicKey(address);
    
    return {
      isValid: true,
      trace_id
    };
  } catch (error) {
    return {
      isValid: false,
      error: `Invalid Solana address: ${error.message}`,
      trace_id
    };
  }
};

/**
 * Check if an address is a zero address (all zeros)
 */
export const isZeroAddress = (address, chain) => {
  try {
    const chainConfig = SUPPORTED_CHAINS[chain];
    if (!chainConfig) return false;

    if (chainConfig.type === 'evm') {
      return address === '0x0000000000000000000000000000000000000000';
    } else if (chainConfig.type === 'solana') {
      // Solana zero address (all 1s in base58 = 32 zero bytes)
      return address === '11111111111111111111111111111111';
    }

    return false;
  } catch (error) {
    logWalletUtils('error', 'Zero address check failed', {
      error: error.message,
      chain
    });
    return false;
  }
};

/**
 * Balance Formatting and Calculations
 */

/**
 * Format token balance for display
 */
export const formatBalance = (balance, options = {}) => {
  const {
    decimals = 18,
    maxDecimals = 4,
    minDecimals = 2,
    useGrouping = true,
    symbol = '',
    showSymbol = true,
    roundingMode = 'floor'
  } = options;

  try {
    if (balance === null || balance === undefined || balance === '') {
      return showSymbol ? `0${symbol ? ' ' + symbol : ''}` : '0';
    }

    // Convert to number if it's a string
    let numBalance;
    if (typeof balance === 'string') {
      numBalance = parseFloat(balance);
    } else if (typeof balance === 'bigint') {
      numBalance = Number(balance) / Math.pow(10, decimals);
    } else {
      numBalance = balance;
    }

    if (isNaN(numBalance)) {
      logWalletUtils('warn', 'Invalid balance value for formatting', {
        balance,
        type: typeof balance
      });
      return showSymbol ? `0${symbol ? ' ' + symbol : ''}` : '0';
    }

    // Apply rounding
    let displayDecimals = maxDecimals;
    
    // For very small amounts, show more decimals
    if (numBalance > 0 && numBalance < Math.pow(10, -maxDecimals)) {
      displayDecimals = Math.max(maxDecimals, 8);
    }

    // For large amounts, show fewer decimals
    if (numBalance >= 1000) {
      displayDecimals = Math.min(displayDecimals, 2);
    }

    const multiplier = Math.pow(10, displayDecimals);
    let roundedBalance;

    switch (roundingMode) {
      case 'ceil':
        roundedBalance = Math.ceil(numBalance * multiplier) / multiplier;
        break;
      case 'round':
        roundedBalance = Math.round(numBalance * multiplier) / multiplier;
        break;
      case 'floor':
      default:
        roundedBalance = Math.floor(numBalance * multiplier) / multiplier;
        break;
    }

    // Format with appropriate decimal places
    const formatted = roundedBalance.toLocaleString('en-US', {
      minimumFractionDigits: numBalance >= 1 ? minDecimals : 0,
      maximumFractionDigits: displayDecimals,
      useGrouping
    });

    return showSymbol && symbol ? `${formatted} ${symbol}` : formatted;

  } catch (error) {
    logWalletUtils('error', 'Balance formatting failed', {
      balance,
      error: error.message,
      options
    });
    return showSymbol ? `0${symbol ? ' ' + symbol : ''}` : '0';
  }
};

/**
 * Format USD value for display
 */
export const formatUSDValue = (value, options = {}) => {
  const {
    showCents = true,
    abbreviated = false,
    prefix = '$'
  } = options;

  try {
    if (value === null || value === undefined || value === '') {
      return `${prefix}0.00`;
    }

    const numValue = typeof value === 'string' ? parseFloat(value) : value;
    
    if (isNaN(numValue)) {
      return `${prefix}0.00`;
    }

    if (abbreviated && numValue >= 1000000) {
      const millions = numValue / 1000000;
      return `${prefix}${millions.toFixed(1)}M`;
    } else if (abbreviated && numValue >= 1000) {
      const thousands = numValue / 1000;
      return `${prefix}${thousands.toFixed(1)}K`;
    }

    const decimals = showCents ? 2 : 0;
    const formatted = numValue.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });

    return `${prefix}${formatted}`;

  } catch (error) {
    logWalletUtils('error', 'USD value formatting failed', {
      value,
      error: error.message,
      options
    });
    return `${prefix}0.00`;
  }
};

/**
 * Calculate percentage change between two values
 */
export const calculatePercentageChange = (oldValue, newValue) => {
  try {
    const old = typeof oldValue === 'string' ? parseFloat(oldValue) : oldValue;
    const current = typeof newValue === 'string' ? parseFloat(newValue) : newValue;

    if (isNaN(old) || isNaN(current) || old === 0) {
      return null;
    }

    return ((current - old) / old) * 100;

  } catch (error) {
    logWalletUtils('error', 'Percentage change calculation failed', {
      oldValue,
      newValue,
      error: error.message
    });
    return null;
  }
};

/**
 * Error Handling and User Messages
 */

/**
 * Parse wallet error and return user-friendly information
 */
export const parseWalletError = (error) => {
  const trace_id = logWalletUtils('debug', 'Parsing wallet error', {
    error_message: error?.message,
    error_code: error?.code
  });

  try {
    let errorInfo = {
      code: error?.code || 'unknown',
      message: error?.message || 'Unknown error occurred',
      category: 'unknown',
      userMessage: 'An unexpected error occurred. Please try again.',
      recoveryAction: 'retry',
      trace_id
    };

    // Check for known error codes
    const knownError = WALLET_ERROR_CODES[error?.code?.toString()];
    if (knownError) {
      errorInfo = {
        ...errorInfo,
        ...knownError,
        trace_id
      };
    } else {
      // Parse by error message patterns
      const message = error?.message?.toLowerCase() || '';

      if (message.includes('user denied') || message.includes('user rejected')) {
        errorInfo = {
          ...errorInfo,
          category: 'user_rejected',
          userMessage: 'Transaction was cancelled. Please try again if you want to proceed.',
          recoveryAction: 'retry'
        };
      } else if (message.includes('not installed') || message.includes('no provider')) {
        errorInfo = {
          ...errorInfo,
          category: 'wallet_not_installed',
          userMessage: 'Wallet extension not found. Please install the wallet and refresh the page.',
          recoveryAction: 'install_wallet'
        };
      } else if (message.includes('network') || message.includes('rpc')) {
        errorInfo = {
          ...errorInfo,
          category: 'network_error',
          userMessage: 'Network connection failed. Please check your internet connection and try again.',
          recoveryAction: 'check_network'
        };
      } else if (message.includes('insufficient') || message.includes('balance')) {
        errorInfo = {
          ...errorInfo,
          category: 'insufficient_balance',
          userMessage: 'Insufficient balance for this transaction. Please add funds to your wallet.',
          recoveryAction: 'add_funds'
        };
      } else if (message.includes('gas') || message.includes('fee')) {
        errorInfo = {
          ...errorInfo,
          category: 'gas_error',
          userMessage: 'Transaction fee error. Please try again with higher gas settings.',
          recoveryAction: 'adjust_gas'
        };
      }
    }

    logWalletUtils('debug', 'Wallet error parsed', {
      original_message: error?.message,
      category: errorInfo.category,
      recovery_action: errorInfo.recoveryAction,
      trace_id
    });

    return errorInfo;

  } catch (parseError) {
    logWalletUtils('error', 'Error parsing failed', {
      original_error: error?.message,
      parse_error: parseError.message,
      trace_id
    });

    return {
      code: 'parse_error',
      message: error?.message || 'Unknown error',
      category: 'unknown',
      userMessage: 'An unexpected error occurred. Please try again.',
      recoveryAction: 'retry',
      trace_id
    };
  }
};

/**
 * Get recovery suggestions for wallet errors
 */
export const getRecoveryActions = (errorCategory) => {
  const recoveryMap = {
    user_rejected: [
      'Try the transaction again',
      'Make sure you approve the transaction in your wallet'
    ],
    wallet_not_installed: [
      'Install the wallet extension',
      'Refresh the page after installation',
      'Try a different wallet'
    ],
    network_error: [
      'Check your internet connection',
      'Try switching to a different network',
      'Wait a moment and try again'
    ],
    insufficient_balance: [
      'Add funds to your wallet',
      'Try a smaller transaction amount',
      'Check if you have enough for transaction fees'
    ],
    gas_error: [
      'Increase the gas limit',
      'Wait for network congestion to decrease',
      'Try again with higher gas price'
    ],
    chain_not_added: [
      'Add the network to your wallet',
      'Switch to a supported network',
      'Contact support if the network should be supported'
    ]
  };

  return recoveryMap[errorCategory] || [
    'Try the action again',
    'Refresh the page and reconnect your wallet',
    'Contact support if the issue persists'
  ];
};

/**
 * Utility Functions
 */

/**
 * Generate a unique transaction identifier
 */
export const generateTransactionId = () => {
  return `tx_${Date.now()}_${Math.random().toString(36).substr(2, 12)}`;
};

/**
 * Copy text to clipboard with error handling
 */
export const copyToClipboard = async (text, description = 'text') => {
  const trace_id = logWalletUtils('debug', 'Copying to clipboard', {
    description,
    text_length: text?.length
  });

  try {
    if (!navigator.clipboard) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (!successful) {
        throw new Error('Fallback copy command failed');
      }
    } else {
      await navigator.clipboard.writeText(text);
    }

    logWalletUtils('debug', 'Text copied to clipboard successfully', {
      description,
      trace_id
    });

    return { success: true };

  } catch (error) {
    logWalletUtils('error', 'Clipboard copy failed', {
      description,
      error: error.message,
      trace_id
    });

    return { 
      success: false, 
      error: error.message 
    };
  }
};

/**
 * Get explorer URL for an address or transaction
 */
export const getExplorerUrl = (chain, addressOrTx, type = 'address') => {
  try {
    const chainConfig = SUPPORTED_CHAINS[chain];
    if (!chainConfig) {
      logWalletUtils('warn', 'Unknown chain for explorer URL', { chain });
      return null;
    }

    const baseUrl = chainConfig.blockExplorer;
    
    switch (type) {
      case 'address':
        return `${baseUrl}/address/${addressOrTx}`;
      case 'tx':
      case 'transaction':
        return chainConfig.type === 'solana' 
          ? `${baseUrl}/tx/${addressOrTx}`
          : `${baseUrl}/tx/${addressOrTx}`;
      case 'token':
        return chainConfig.type === 'solana'
          ? `${baseUrl}/account/${addressOrTx}`
          : `${baseUrl}/token/${addressOrTx}`;
      default:
        return `${baseUrl}/address/${addressOrTx}`;
    }

  } catch (error) {
    logWalletUtils('error', 'Explorer URL generation failed', {
      chain,
      type,
      error: error.message
    });
    return null;
  }
};

/**
 * Check if wallet is mobile browser extension
 */
export const isMobileWallet = () => {
  const userAgent = navigator.userAgent || navigator.vendor || window.opera;
  const isMobile = /android|ipad|iphone|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
  
  return isMobile && (
    window.ethereum?.isTrust ||
    window.ethereum?.isMetaMask ||
    window.solana?.isPhantom ||
    window.ethereum?.isCoinbaseWallet
  );
};

/**
 * Get recommended wallet for current environment
 */
export const getRecommendedWallet = (chain) => {
  const chainConfig = SUPPORTED_CHAINS[chain];
  if (!chainConfig) return null;

  const isMobile = isMobileWallet();

  if (chainConfig.type === 'evm') {
    if (isMobile) {
      return window.ethereum?.isTrust ? 'trust' : 'metamask';
    }
    return window.ethereum ? 'metamask' : 'walletconnect';
  } else if (chainConfig.type === 'solana') {
    return window.solana?.isPhantom ? 'phantom' : 'phantom';
  }

  return null;
};

/**
 * Debounce function for reducing API calls
 */
export const debounce = (func, wait, immediate = false) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      timeout = null;
      if (!immediate) func(...args);
    };
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func(...args);
  };
};

/**
 * Retry function with exponential backoff
 */
export const retryWithBackoff = async (
  fn, 
  maxRetries = 3, 
  initialDelay = 1000,
  backoffFactor = 2
) => {
  const trace_id = logWalletUtils('debug', 'Starting retry with backoff', {
    max_retries: maxRetries,
    initial_delay: initialDelay
  });

  let lastError;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const result = await fn();
      
      if (attempt > 0) {
        logWalletUtils('info', 'Function succeeded after retry', {
          attempt,
          trace_id
        });
      }
      
      return result;
    } catch (error) {
      lastError = error;
      
      if (attempt === maxRetries) {
        logWalletUtils('error', 'Function failed after all retries', {
          attempts: attempt + 1,
          error: error.message,
          trace_id
        });
        break;
      }
      
      const delay = initialDelay * Math.pow(backoffFactor, attempt);
      
      logWalletUtils('warn', 'Function failed, retrying', {
        attempt,
        next_delay: delay,
        error: error.message,
        trace_id
      });
      
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError;
};

// Export all utility functions
export default {
  formatAddress,
  validateAddress,
  isZeroAddress,
  formatBalance,
  formatUSDValue,
  calculatePercentageChange,
  parseWalletError,
  getRecoveryActions,
  generateTransactionId,
  copyToClipboard,
  getExplorerUrl,
  isMobileWallet,
  getRecommendedWallet,
  debounce,
  retryWithBackoff,
  SUPPORTED_CHAINS,
  WALLET_TYPES,
  WALLET_ERROR_CODES
};