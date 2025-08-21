import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Card, Row, Col, Button, ButtonGroup, Dropdown, Form, Badge, Spinner } from 'react-bootstrap';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, CandlestickChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ReferenceLine, ReferenceArea, Brush, ComposedChart
} from 'recharts';
import {
  TrendingUp, TrendingDown, BarChart3, Activity, Settings,
  ZoomIn, ZoomOut, RotateCcw, Download, Maximize2, Eye, EyeOff
} from 'lucide-react';

// Import mobile detection for responsive behavior
import useMobileDetection from '../hooks/useMobileDetection.js';
import useTouch from '../hooks/useTouch.js';

/**
 * Advanced Charts Component - Mobile-responsive trading charts with technical indicators
 * 
 * Features:
 * - Multiple chart types (line, area, candlestick, volume)
 * - Technical indicators (MA, EMA, RSI, MACD, Bollinger Bands)
 * - Mobile-optimized touch interactions
 * - Real-time data updates
 * - Zoom and pan functionality
 * - Customizable timeframes and indicators
 */
const Charts = ({ 
  symbol = 'ETH/USDT',
  initialTimeframe = '1h',
  height = 400,
  enableRealTime = true,
  showVolume = true,
  className = ''
}) => {
  // Mobile detection for responsive behavior
  const { isMobile, isTablet, screenSize } = useMobileDetection();
  
  // Chart state management
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Chart configuration
  const [chartConfig, setChartConfig] = useState({
    type: 'line', // line, area, candlestick
    timeframe: initialTimeframe,
    indicators: {
      ma: { enabled: true, period: 20, color: '#ff7300' },
      ema: { enabled: false, period: 12, color: '#8884d8' },
      rsi: { enabled: false, period: 14 },
      macd: { enabled: false },
      bollinger: { enabled: false, period: 20, stdDev: 2 }
    },
    overlay: {
      volume: showVolume,
      grid: true,
      crosshair: true
    }
  });
  
  // Zoom and pan state
  const [zoomState, setZoomState] = useState({
    startIndex: 0,
    endIndex: 100,
    isZoomed: false
  });
  
  // Touch interaction state
  const chartRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(null);

  // Touch gestures for mobile
  const { onTouchStart, onTouchMove, onTouchEnd } = useTouch(chartRef.current, {
    enablePinch: true,
    enableDrag: true,
    onPinch: handlePinchZoom,
    onDrag: handleChartDrag,
    onDoubleTap: handleDoubleTap
  });

  // Timeframe options
  const timeframes = [
    { value: '1m', label: '1m', mobile: '1m' },
    { value: '5m', label: '5m', mobile: '5m' },
    { value: '15m', label: '15m', mobile: '15m' },
    { value: '1h', label: '1h', mobile: '1h' },
    { value: '4h', label: '4h', mobile: '4h' },
    { value: '1d', label: '1D', mobile: '1D' },
    { value: '1w', label: '1W', mobile: '1W' }
  ];

  // Chart type options
  const chartTypes = [
    { value: 'line', label: 'Line', icon: Activity, mobile: true },
    { value: 'area', label: 'Area', icon: BarChart3, mobile: true },
    { value: 'candlestick', label: 'Candles', icon: BarChart3, mobile: false } // Hidden on mobile
  ];

  // Technical indicators options
  const indicatorOptions = [
    { key: 'ma', label: 'Moving Average', shortLabel: 'MA' },
    { key: 'ema', label: 'Exponential MA', shortLabel: 'EMA' },
    { key: 'rsi', label: 'RSI', shortLabel: 'RSI' },
    { key: 'macd', label: 'MACD', shortLabel: 'MACD' },
    { key: 'bollinger', label: 'Bollinger Bands', shortLabel: 'BB' }
  ];

  /**
   * Generate sample trading data for demonstration
   */
  const generateSampleData = useCallback((timeframe, count = 100) => {
    const data = [];
    const now = Date.now();
    const timeframMinutes = {
      '1m': 1, '5m': 5, '15m': 15, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080
    };
    const interval = timeframMinutes[timeframe] * 60 * 1000;
    
    let price = 2000; // Starting price
    let volume = 1000000;
    
    for (let i = count; i >= 0; i--) {
      const timestamp = now - (i * interval);
      
      // Simulate price movement with some volatility
      const change = (Math.random() - 0.5) * 100;
      price = Math.max(price + change, 100); // Minimum price of 100
      
      // Simulate volume
      volume = Math.max(volume * (0.8 + Math.random() * 0.4), 100000);
      
      // OHLC data for candlestick charts
      const open = price;
      const close = price + (Math.random() - 0.5) * 50;
      const high = Math.max(open, close) + Math.random() * 30;
      const low = Math.min(open, close) - Math.random() * 30;
      
      data.push({
        timestamp,
        time: new Date(timestamp).toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit',
          ...(timeframe === '1d' || timeframe === '1w' ? { 
            month: 'short', 
            day: 'numeric' 
          } : {})
        }),
        price: Math.round(price * 100) / 100,
        open: Math.round(open * 100) / 100,
        high: Math.round(high * 100) / 100,
        low: Math.round(low * 100) / 100,
        close: Math.round(close * 100) / 100,
        volume: Math.round(volume)
      });
    }
    
    return data;
  }, []);

  /**
   * Calculate technical indicators
   */
  const calculateIndicators = useCallback((data, indicators) => {
    return data.map((item, index) => {
      const result = { ...item };
      
      // Moving Average
      if (indicators.ma.enabled && index >= indicators.ma.period - 1) {
        const slice = data.slice(index - indicators.ma.period + 1, index + 1);
        result.ma = slice.reduce((sum, d) => sum + d.price, 0) / slice.length;
      }
      
      // Exponential Moving Average
      if (indicators.ema.enabled) {
        const multiplier = 2 / (indicators.ema.period + 1);
        if (index === 0) {
          result.ema = item.price;
        } else {
          const prevEma = data[index - 1].ema || item.price;
          result.ema = (item.price * multiplier) + (prevEma * (1 - multiplier));
        }
      }
      
      // RSI calculation (simplified)
      if (indicators.rsi.enabled && index >= indicators.rsi.period) {
        const period = indicators.rsi.period;
        const slice = data.slice(index - period, index + 1);
        
        let gains = 0, losses = 0;
        for (let i = 1; i < slice.length; i++) {
          const change = slice[i].price - slice[i - 1].price;
          if (change > 0) gains += change;
          else losses -= change;
        }
        
        const avgGain = gains / period;
        const avgLoss = losses / period;
        const rs = avgGain / (avgLoss || 1);
        result.rsi = 100 - (100 / (1 + rs));
      }
      
      // Bollinger Bands
      if (indicators.bollinger.enabled && index >= indicators.bollinger.period - 1) {
        const period = indicators.bollinger.period;
        const slice = data.slice(index - period + 1, index + 1);
        const ma = slice.reduce((sum, d) => sum + d.price, 0) / slice.length;
        
        const variance = slice.reduce((sum, d) => sum + Math.pow(d.price - ma, 2), 0) / slice.length;
        const stdDev = Math.sqrt(variance);
        
        result.bb_upper = ma + (stdDev * indicators.bollinger.stdDev);
        result.bb_lower = ma - (stdDev * indicators.bollinger.stdDev);
        result.bb_middle = ma;
      }
      
      return result;
    });
  }, []);

  /**
   * Load chart data
   */
  const loadChartData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // In a real application, this would fetch from your API
      await new Promise(resolve => setTimeout(resolve, 500)); // Simulate API delay
      
      const rawData = generateSampleData(chartConfig.timeframe);
      const dataWithIndicators = calculateIndicators(rawData, chartConfig.indicators);
      
      setChartData(dataWithIndicators);
      
      // Reset zoom when data changes
      setZoomState({
        startIndex: Math.max(0, dataWithIndicators.length - 100),
        endIndex: dataWithIndicators.length - 1,
        isZoomed: false
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [chartConfig.timeframe, generateSampleData, calculateIndicators, chartConfig.indicators]);

  /**
   * Handle pinch zoom gesture
   */
  function handlePinchZoom({ scale, center }) {
    const zoomFactor = scale > 1 ? 0.9 : 1.1;
    const currentRange = zoomState.endIndex - zoomState.startIndex;
    const newRange = Math.max(10, Math.min(currentRange * zoomFactor, chartData.length));
    
    const centerPoint = zoomState.startIndex + (currentRange / 2);
    const newStart = Math.max(0, centerPoint - (newRange / 2));
    const newEnd = Math.min(chartData.length - 1, newStart + newRange);
    
    setZoomState({
      startIndex: Math.round(newStart),
      endIndex: Math.round(newEnd),
      isZoomed: newRange < chartData.length
    });
  }

  /**
   * Handle chart drag gesture
   */
  function handleChartDrag({ deltaX }) {
    if (!zoomState.isZoomed) return;
    
    const sensitivity = isMobile ? 2 : 1;
    const moveAmount = Math.round(deltaX / sensitivity);
    const currentRange = zoomState.endIndex - zoomState.startIndex;
    
    let newStart = zoomState.startIndex - moveAmount;
    let newEnd = zoomState.endIndex - moveAmount;
    
    // Constrain to data bounds
    if (newStart < 0) {
      newStart = 0;
      newEnd = currentRange;
    } else if (newEnd >= chartData.length) {
      newEnd = chartData.length - 1;
      newStart = newEnd - currentRange;
    }
    
    setZoomState({
      startIndex: newStart,
      endIndex: newEnd,
      isZoomed: true
    });
  }

  /**
   * Handle double tap to reset zoom
   */
  function handleDoubleTap() {
    setZoomState({
      startIndex: Math.max(0, chartData.length - 100),
      endIndex: chartData.length - 1,
      isZoomed: false
    });
  }

  /**
   * Update chart configuration
   */
  const updateChartConfig = useCallback((updates) => {
    setChartConfig(prev => ({
      ...prev,
      ...updates
    }));
  }, []);

  /**
   * Toggle indicator
   */
  const toggleIndicator = useCallback((indicatorKey) => {
    setChartConfig(prev => ({
      ...prev,
      indicators: {
        ...prev.indicators,
        [indicatorKey]: {
          ...prev.indicators[indicatorKey],
          enabled: !prev.indicators[indicatorKey].enabled
        }
      }
    }));
  }, []);

  /**
   * Custom tooltip for charts
   */
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;
    
    const data = payload[0].payload;
    
    return (
      <div className="bg-white border rounded shadow-sm p-2" style={{ fontSize: isMobile ? '12px' : '14px' }}>
        <p className="mb-1 fw-bold">{label}</p>
        <p className="mb-1 text-primary">
          Price: ${data.price?.toFixed(2)}
        </p>
        {data.volume && (
          <p className="mb-1 text-muted">
            Volume: {(data.volume / 1000000).toFixed(2)}M
          </p>
        )}
        {data.ma && (
          <p className="mb-1" style={{ color: chartConfig.indicators.ma.color }}>
            MA({chartConfig.indicators.ma.period}): ${data.ma.toFixed(2)}
          </p>
        )}
        {data.rsi && (
          <p className="mb-0">
            RSI: {data.rsi.toFixed(1)}
          </p>
        )}
      </div>
    );
  };

  /**
   * Render chart based on type
   */
  const renderChart = () => {
    const visibleData = chartData.slice(zoomState.startIndex, zoomState.endIndex + 1);
    const chartHeight = isMobile ? 300 : height;
    
    const commonProps = {
      data: visibleData,
      margin: { 
        top: 5, 
        right: isMobile ? 5 : 30, 
        left: isMobile ? 5 : 20, 
        bottom: 5 
      }
    };

    switch (chartConfig.type) {
      case 'area':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="time" 
              fontSize={isMobile ? 10 : 12}
              interval={isMobile ? 'preserveStartEnd' : 0}
            />
            <YAxis 
              fontSize={isMobile ? 10 : 12}
              domain={['dataMin - 10', 'dataMax + 10']}
              width={isMobile ? 40 : 60}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#8884d8"
              fill="url(#colorPrice)"
              strokeWidth={2}
            />
            
            {/* Technical Indicators */}
            {chartConfig.indicators.ma.enabled && (
              <Line
                type="monotone"
                dataKey="ma"
                stroke={chartConfig.indicators.ma.color}
                strokeWidth={1}
                dot={false}
              />
            )}
            
            {chartConfig.indicators.bollinger.enabled && (
              <>
                <Line type="monotone" dataKey="bb_upper" stroke="#ff9999" strokeWidth={1} dot={false} />
                <Line type="monotone" dataKey="bb_lower" stroke="#ff9999" strokeWidth={1} dot={false} />
              </>
            )}
            
            <defs>
              <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="#8884d8" stopOpacity={0.1}/>
              </linearGradient>
            </defs>
          </AreaChart>
        );

      case 'line':
      default:
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey="time" 
              fontSize={isMobile ? 10 : 12}
              interval={isMobile ? 'preserveStartEnd' : 0}
            />
            <YAxis 
              fontSize={isMobile ? 10 : 12}
              domain={['dataMin - 10', 'dataMax + 10']}
              width={isMobile ? 40 : 60}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#8884d8"
              strokeWidth={2}
              dot={false}
            />
            
            {/* Technical Indicators */}
            {chartConfig.indicators.ma.enabled && (
              <Line
                type="monotone"
                dataKey="ma"
                stroke={chartConfig.indicators.ma.color}
                strokeWidth={1}
                dot={false}
              />
            )}
            
            {chartConfig.indicators.ema.enabled && (
              <Line
                type="monotone"
                dataKey="ema"
                stroke={chartConfig.indicators.ema.color}
                strokeWidth={1}
                dot={false}
              />
            )}
          </LineChart>
        );
    }
  };

  /**
   * Render volume chart
   */
  const renderVolumeChart = () => {
    if (!chartConfig.overlay.volume) return null;
    
    const visibleData = chartData.slice(zoomState.startIndex, zoomState.endIndex + 1);
    
    return (
      <ResponsiveContainer width="100%" height={isMobile ? 80 : 100}>
        <BarChart
          data={visibleData}
          margin={{ top: 5, right: isMobile ? 5 : 30, left: isMobile ? 5 : 20, bottom: 5 }}
        >
          <XAxis dataKey="time" hide />
          <YAxis 
            fontSize={isMobile ? 10 : 12}
            width={isMobile ? 40 : 60}
            tickFormatter={(value) => `${(value / 1000000).toFixed(1)}M`}
          />
          <Tooltip 
            formatter={(value) => [`${(value / 1000000).toFixed(2)}M`, 'Volume']}
            labelStyle={{ display: 'none' }}
          />
          <Bar dataKey="volume" fill="#e0e0e0" />
        </BarChart>
      </ResponsiveContainer>
    );
  };

  /**
   * Render RSI indicator
   */
  const renderRSIChart = () => {
    if (!chartConfig.indicators.rsi.enabled) return null;
    
    const visibleData = chartData.slice(zoomState.startIndex, zoomState.endIndex + 1)
      .filter(d => d.rsi !== undefined);
    
    return (
      <ResponsiveContainer width="100%" height={isMobile ? 80 : 100}>
        <LineChart
          data={visibleData}
          margin={{ top: 5, right: isMobile ? 5 : 30, left: isMobile ? 5 : 20, bottom: 5 }}
        >
          <XAxis dataKey="time" hide />
          <YAxis 
            domain={[0, 100]}
            fontSize={isMobile ? 10 : 12}
            width={isMobile ? 40 : 60}
          />
          <Tooltip formatter={(value) => [value.toFixed(1), 'RSI']} />
          <Line type="monotone" dataKey="rsi" stroke="#ff7300" strokeWidth={1} dot={false} />
          <ReferenceLine y={70} stroke="#ff4444" strokeDasharray="3 3" />
          <ReferenceLine y={30} stroke="#44ff44" strokeDasharray="3 3" />
        </LineChart>
      </ResponsiveContainer>
    );
  };

  // Load initial data
  useEffect(() => {
    loadChartData();
  }, [loadChartData]);

  // Real-time updates
  useEffect(() => {
    if (!enableRealTime) return;
    
    const interval = setInterval(() => {
      // In a real app, this would fetch latest data
      // For demo, we'll just add a new data point
      setChartData(prev => {
        if (prev.length === 0) return prev;
        
        const lastItem = prev[prev.length - 1];
        const newPrice = lastItem.price + (Math.random() - 0.5) * 10;
        const newItem = {
          ...lastItem,
          timestamp: Date.now(),
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          price: Math.round(newPrice * 100) / 100
        };
        
        return [...prev.slice(-199), newItem]; // Keep last 200 items
      });
    }, 5000); // Update every 5 seconds
    
    return () => clearInterval(interval);
  }, [enableRealTime]);

  if (loading) {
    return (
      <Card className={className}>
        <Card.Body className="text-center py-5">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading chart...</span>
          </Spinner>
          <div className="mt-2">Loading {symbol} chart...</div>
        </Card.Body>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <Card.Body className="text-center py-5">
          <div className="text-danger mb-3">Failed to load chart data</div>
          <Button variant="outline-primary" onClick={loadChartData}>
            Retry
          </Button>
        </Card.Body>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <Card.Header className="d-flex justify-content-between align-items-center">
        <div className="d-flex align-items-center">
          <h6 className="mb-0 me-2">{symbol}</h6>
          {chartData.length > 0 && (
            <Badge bg={chartData[chartData.length - 1].price > chartData[chartData.length - 2]?.price ? 'success' : 'danger'}>
              ${chartData[chartData.length - 1].price.toFixed(2)}
            </Badge>
          )}
        </div>
        
        {/* Mobile-optimized controls */}
        {isMobile ? (
          <Dropdown>
            <Dropdown.Toggle variant="outline-secondary" size="sm">
              <Settings size={14} />
            </Dropdown.Toggle>
            <Dropdown.Menu>
              <Dropdown.Header>Timeframe</Dropdown.Header>
              {timeframes.map(tf => (
                <Dropdown.Item
                  key={tf.value}
                  active={chartConfig.timeframe === tf.value}
                  onClick={() => updateChartConfig({ timeframe: tf.value })}
                >
                  {tf.mobile}
                </Dropdown.Item>
              ))}
              <Dropdown.Divider />
              <Dropdown.Header>Indicators</Dropdown.Header>
              {indicatorOptions.map(indicator => (
                <Dropdown.Item
                  key={indicator.key}
                  onClick={() => toggleIndicator(indicator.key)}
                >
                  {chartConfig.indicators[indicator.key].enabled && '✓ '}
                  {indicator.shortLabel}
                </Dropdown.Item>
              ))}
            </Dropdown.Menu>
          </Dropdown>
        ) : (
          <div className="d-flex align-items-center gap-2">
            {/* Timeframe selector */}
            <ButtonGroup size="sm">
              {timeframes.map(tf => (
                <Button
                  key={tf.value}
                  variant={chartConfig.timeframe === tf.value ? 'primary' : 'outline-secondary'}
                  onClick={() => updateChartConfig({ timeframe: tf.value })}
                >
                  {tf.label}
                </Button>
              ))}
            </ButtonGroup>
            
            {/* Chart type selector */}
            <ButtonGroup size="sm">
              {chartTypes.filter(ct => !isMobile || ct.mobile).map(ct => (
                <Button
                  key={ct.value}
                  variant={chartConfig.type === ct.value ? 'primary' : 'outline-secondary'}
                  onClick={() => updateChartConfig({ type: ct.value })}
                >
                  <ct.icon size={14} />
                </Button>
              ))}
            </ButtonGroup>
            
            {/* Indicators dropdown */}
            <Dropdown>
              <Dropdown.Toggle variant="outline-secondary" size="sm">
                Indicators
              </Dropdown.Toggle>
              <Dropdown.Menu>
                {indicatorOptions.map(indicator => (
                  <Dropdown.Item
                    key={indicator.key}
                    onClick={() => toggleIndicator(indicator.key)}
                  >
                    {chartConfig.indicators[indicator.key].enabled ? (
                      <Eye size={14} className="me-2" />
                    ) : (
                      <EyeOff size={14} className="me-2" />
                    )}
                    {indicator.label}
                  </Dropdown.Item>
                ))}
              </Dropdown.Menu>
            </Dropdown>
          </div>
        )}
      </Card.Header>
      
      <Card.Body className="p-2">
        {/* Main price chart */}
        <div 
          ref={chartRef}
          style={{ touchAction: 'manipulation' }}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          <ResponsiveContainer width="100%" height={isMobile ? 300 : height}>
            {renderChart()}
          </ResponsiveContainer>
        </div>
        
        {/* Volume chart */}
        {renderVolumeChart()}
        
        {/* RSI chart */}
        {renderRSIChart()}
        
        {/* Zoom controls */}
        {zoomState.isZoomed && (
          <div className="d-flex justify-content-center mt-2">
            <ButtonGroup size="sm">
              <Button variant="outline-secondary" onClick={handleDoubleTap}>
                <RotateCcw size={14} />
                {!isMobile && ' Reset Zoom'}
              </Button>
            </ButtonGroup>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default Charts;