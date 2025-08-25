/**
 * DEX Sniper Pro - Enhanced Quote Display Component
 * 
 * Advanced multi-DEX quote comparison with detailed analysis,
 * visual indicators, and comprehensive error handling.
 * 
 * File: frontend/src/components/QuoteDisplay.jsx
 */

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Card, 
  Table, 
  Badge, 
  Button, 
  Spinner, 
  Alert, 
  Row, 
  Col,
  ProgressBar,
  Tooltip,
  OverlayTrigger
} from 'react-bootstrap';
import PropTypes from 'prop-types';

/**
 * Enhanced quote display component with multi-DEX comparison
 * 
 * @param {Object} props Component properties
 * @param {Array} props.quotes Array of quote objects from backend
 * @param {Object} props.selectedQuote Currently selected quote
 * @param {Function} props.onQuoteSelect Callback when user selects a quote
 * @param {boolean} props.isLoading Loading state
 * @param {string} props.error Error message if any
 * @param {Function} props.onRefresh Callback to refresh quotes
 * @param {string} props.fromToken Source token symbol
 * @param {string} props.toToken Destination token symbol
 * @param {string} props.fromAmount Input amount
 * @param {number} props.chainId Current chain ID
 * @returns {JSX.Element} Quote display component
 */
const QuoteDisplay = ({
  quotes = [],
  selectedQuote,
  onQuoteSelect,
  isLoading = false,
  error = null,
  onRefresh,
  fromToken,
  toToken,
  fromAmount,
  chainId
}) => {
  const [lastUpdated, setLastUpdated] = useState(null);
  const [sortBy, setSortBy] = useState('output_amount');
  const [sortDirection, setSortDirection] = useState('desc');

  /**
   * Update timestamp when quotes change
   */
  useEffect(() => {
    if (quotes.length > 0) {
      setLastUpdated(new Date());
    }
  }, [quotes]);

  /**
   * Sort quotes by specified field
   */
  const sortedQuotes = useCallback(() => {
    if (!quotes || quotes.length === 0) return [];

    return [...quotes].sort((a, b) => {
      let aValue = a[sortBy];
      let bValue = b[sortBy];

      // Handle numeric fields
      if (typeof aValue === 'string' && !isNaN(parseFloat(aValue))) {
        aValue = parseFloat(aValue);
        bValue = parseFloat(bValue);
      }

      if (sortDirection === 'desc') {
        return bValue > aValue ? 1 : -1;
      } else {
        return aValue > bValue ? 1 : -1;
      }
    });
  }, [quotes, sortBy, sortDirection]);

  /**
   * Handle sort header click
   */
  const handleSort = (field) => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setSortDirection('desc');
    }
  };

  /**
   * Calculate savings compared to worst quote
   */
  const calculateSavings = (quote) => {
    if (!quotes || quotes.length < 2) return null;

    const outputAmounts = quotes.map(q => parseFloat(q.output_amount));
    const minOutput = Math.min(...outputAmounts);
    const currentOutput = parseFloat(quote.output_amount);
    
    if (currentOutput <= minOutput) return null;

    const savingsAmount = currentOutput - minOutput;
    const savingsPercent = ((savingsAmount / minOutput) * 100).toFixed(2);
    
    return {
      amount: savingsAmount.toFixed(6),
      percent: savingsPercent
    };
  };

  /**
   * Get price impact color class
   */
  const getPriceImpactColor = (impact) => {
    const impactNum = parseFloat(impact);
    if (impactNum < 1) return 'text-success';
    if (impactNum < 3) return 'text-warning';
    return 'text-danger';
  };

  /**
   * Get gas cost badge variant
   */
  const getGasBadgeVariant = (gasUsd) => {
    const gasNum = parseFloat(gasUsd);
    if (gasNum < 5) return 'success';
    if (gasNum < 20) return 'warning';
    return 'danger';
  };

  /**
   * Format route display
   */
  const formatRoute = (route) => {
    if (!route || !Array.isArray(route)) return 'Direct';
    if (route.length <= 2) return 'Direct';
    
    return route.map(token => token.symbol || token.slice(0, 6)).join(' → ');
  };

  /**
   * Render sort arrow
   */
  const renderSortArrow = (field) => {
    if (sortBy !== field) return null;
    return sortDirection === 'desc' ? ' ↓' : ' ↑';
  };

  /**
   * Render loading state
   */
  if (isLoading) {
    return (
      <Card className="mb-3">
        <Card.Header>
          <div className="d-flex align-items-center">
            <Spinner size="sm" className="me-2" />
            <span>Getting quotes from multiple DEXs...</span>
          </div>
        </Card.Header>
        <Card.Body>
          <div className="text-center py-4">
            <ProgressBar animated now={100} className="mb-3" />
            <small className="text-muted">
              Comparing prices across Uniswap, PancakeSwap, QuickSwap, and more...
            </small>
          </div>
        </Card.Body>
      </Card>
    );
  }

  /**
   * Render error state
   */
  if (error) {
    return (
      <Card className="mb-3">
        <Card.Header className="bg-danger text-white">
          <i className="bi bi-exclamation-triangle me-2"></i>
          Quote Error
        </Card.Header>
        <Card.Body>
          <Alert variant="danger" className="mb-3">
            {error}
          </Alert>
          {onRefresh && (
            <Button variant="outline-primary" onClick={onRefresh}>
              <i className="bi bi-arrow-clockwise me-2"></i>
              Try Again
            </Button>
          )}
        </Card.Body>
      </Card>
    );
  }

  /**
   * Render empty state
   */
  if (!quotes || quotes.length === 0) {
    return (
      <Card className="mb-3">
        <Card.Body className="text-center py-4">
          <i className="bi bi-search mb-3" style={{ fontSize: '2rem', color: '#6c757d' }}></i>
          <p className="text-muted mb-0">
            Enter token amounts and click "Get Quotes" to compare DEX prices
          </p>
        </Card.Body>
      </Card>
    );
  }

  const sortedQuoteList = sortedQuotes();

  return (
    <Card className="mb-3">
      <Card.Header>
        <Row className="align-items-center">
          <Col>
            <div className="d-flex align-items-center">
              <i className="bi bi-graph-up me-2"></i>
              <strong>DEX Quote Comparison</strong>
              <Badge bg="secondary" className="ms-2">
                {quotes.length} quotes
              </Badge>
            </div>
          </Col>
          <Col xs="auto">
            {lastUpdated && (
              <small className="text-muted">
                Updated {lastUpdated.toLocaleTimeString()}
              </small>
            )}
            {onRefresh && (
              <Button 
                variant="outline-secondary" 
                size="sm" 
                onClick={onRefresh}
                className="ms-2"
              >
                <i className="bi bi-arrow-clockwise"></i>
              </Button>
            )}
          </Col>
        </Row>
      </Card.Header>

      <Card.Body className="p-0">
        <Table responsive hover className="mb-0">
          <thead className="table-light">
            <tr>
              <th></th>
              <th 
                style={{ cursor: 'pointer' }} 
                onClick={() => handleSort('dex')}
              >
                DEX{renderSortArrow('dex')}
              </th>
              <th 
                style={{ cursor: 'pointer' }} 
                onClick={() => handleSort('output_amount')}
                className="text-end"
              >
                You Get{renderSortArrow('output_amount')}
              </th>
              <th 
                style={{ cursor: 'pointer' }} 
                onClick={() => handleSort('price_impact')}
                className="text-end"
              >
                Price Impact{renderSortArrow('price_impact')}
              </th>
              <th 
                style={{ cursor: 'pointer' }} 
                onClick={() => handleSort('gas_usd')}
                className="text-end"
              >
                Gas Cost{renderSortArrow('gas_usd')}
              </th>
              <th className="text-center">Route</th>
              <th className="text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedQuoteList.map((quote, index) => {
              const isSelected = selectedQuote?.quote_id === quote.quote_id;
              const isBest = index === 0 && sortBy === 'output_amount' && sortDirection === 'desc';
              const savings = calculateSavings(quote);

              return (
                <tr 
                  key={quote.quote_id || index}
                  className={isSelected ? 'table-primary' : ''}
                  style={{ cursor: 'pointer' }}
                  onClick={() => onQuoteSelect && onQuoteSelect(quote)}
                >
                  <td className="text-center" style={{ width: '40px' }}>
                    {isBest && (
                      <OverlayTrigger
                        placement="right"
                        overlay={<Tooltip>Best available price</Tooltip>}
                      >
                        <Badge bg="success" className="p-1">
                          <i className="bi bi-trophy"></i>
                        </Badge>
                      </OverlayTrigger>
                    )}
                    {isSelected && !isBest && (
                      <Badge bg="primary" className="p-1">
                        <i className="bi bi-check"></i>
                      </Badge>
                    )}
                  </td>

                  <td>
                    <div className="fw-bold">{quote.dex}</div>
                    <small className="text-muted">
                      {quote.version || 'v2'}
                    </small>
                  </td>

                  <td className="text-end">
                    <div className="fw-bold">
                      {parseFloat(quote.output_amount).toFixed(6)} {toToken}
                    </div>
                    {savings && (
                      <small className="text-success">
                        +{savings.amount} ({savings.percent}%)
                      </small>
                    )}
                  </td>

                  <td className="text-end">
                    <span className={getPriceImpactColor(quote.price_impact)}>
                      {parseFloat(quote.price_impact).toFixed(2)}%
                    </span>
                  </td>

                  <td className="text-end">
                    {quote.gas_usd ? (
                      <Badge bg={getGasBadgeVariant(quote.gas_usd)}>
                        ${parseFloat(quote.gas_usd).toFixed(2)}
                      </Badge>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>

                  <td className="text-center">
                    <small className="text-muted">
                      {formatRoute(quote.route)}
                    </small>
                  </td>

                  <td className="text-center">
                    <Button
                      variant={isSelected ? "primary" : "outline-primary"}
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onQuoteSelect && onQuoteSelect(quote);
                      }}
                    >
                      {isSelected ? 'Selected' : 'Select'}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card.Body>

      {/* Summary Footer */}
      <Card.Footer className="bg-light">
        <Row className="align-items-center">
          <Col>
            <small className="text-muted">
              Trading {fromAmount} {fromToken} → {toToken}
              {chainId && ` on Chain ${chainId}`}
            </small>
          </Col>
          <Col xs="auto">
            <small className="text-muted">
              Best rate: {sortedQuoteList.length > 0 && sortedQuoteList[0]?.dex}
            </small>
          </Col>
        </Row>
      </Card.Footer>
    </Card>
  );
};

QuoteDisplay.propTypes = {
  quotes: PropTypes.arrayOf(PropTypes.shape({
    quote_id: PropTypes.string,
    dex: PropTypes.string.isRequired,
    output_amount: PropTypes.string.isRequired,
    price_impact: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    gas_usd: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    route: PropTypes.array,
    version: PropTypes.string
  })),
  selectedQuote: PropTypes.object,
  onQuoteSelect: PropTypes.func,
  isLoading: PropTypes.bool,
  error: PropTypes.string,
  onRefresh: PropTypes.func,
  fromToken: PropTypes.string,
  toToken: PropTypes.string,
  fromAmount: PropTypes.string,
  chainId: PropTypes.number
};

export default QuoteDisplay;