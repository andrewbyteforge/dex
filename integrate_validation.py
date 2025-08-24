"""
Integration script to add enhanced validation to existing APIs.

Shows how to integrate the new validation middleware and endpoint
validation into your existing DEX Sniper Pro backend.

File: integrate_validation.py
"""

import sys
from pathlib import Path

def main():
    """Show integration steps for validation enhancements."""
    print("DEX Sniper Pro - Validation Integration Guide")
    print("=" * 50)
    
    print("Step 1: Save the validation files")
    print("-" * 30)
    print("Create these files with the artifact content:")
    print("  - backend/app/middleware/request_validation.py")
    print("  - backend/app/api/validation_enhancements.py")
    
    print("\nStep 2: Update your main.py to add middleware")
    print("-" * 30)
    print("Add this to your backend/main.py file:")
    print("""
# Add these imports at the top:
from app.middleware.request_validation import RequestValidationMiddleware

# Add middleware to your FastAPI app (after CORS):
app.add_middleware(
    RequestValidationMiddleware,
    max_request_size=10 * 1024 * 1024,  # 10MB
    request_timeout=30.0,
    enable_security_filtering=True
)
""")
    
    print("\nStep 3: Example API endpoint with validation")
    print("-" * 30)
    print("Here's how to use validation in your API endpoints:")
    print("""
# In backend/app/api/trades.py:
from fastapi import APIRouter, Depends
from ..api.validation_enhancements import ValidatedTradingRequest, validate_api_endpoint_params

@router.post("/execute")
async def execute_trade(request: ValidatedTradingRequest):
    # Request is automatically validated by Pydantic
    # Additional validation can be done with:
    # validated_params = validate_api_endpoint_params(**request.dict())
    
    return {"message": "Trade validated and ready for execution"}

# For query parameters:
@router.get("/quote")
async def get_quote(
    input_token: str,
    output_token: str, 
    amount: str,
    chain: str = "ethereum"
):
    # Validate query parameters
    validated = validate_api_endpoint_params(
        input_token=input_token,
        output_token=output_token,
        amount=amount,
        chain=chain
    )
    
    return {"quote": "validated", "params": validated}
""")
    
    print("\nStep 4: Test validation")
    print("-" * 30)
    print("Test that validation is working:")
    print("1. Start your server: uvicorn main:app --reload")
    print("2. Try these test requests:")
    print("   - Valid: POST /api/v1/trades/execute with proper JSON")
    print("   - Invalid: POST with malformed wallet address")
    print("   - Invalid: POST with XSS payload in a field")
    print("   - Large: POST with >10MB body (should be rejected)")
    
    print("\nStep 5: Monitor validation logs")
    print("-" * 30)
    print("Check your logs for validation events:")
    print("  - Request size violations")
    print("  - Security pattern detections")
    print("  - Invalid parameter formats")
    
    print("\n" + "=" * 50)
    print("Integration complete! Your API now has:")
    print("✓ Request size limits (DoS protection)")
    print("✓ Request timeout handling") 
    print("✓ Security pattern detection (XSS, SQL injection, etc.)")
    print("✓ Comprehensive parameter validation")
    print("✓ Blockchain address validation")
    print("✓ Trading amount validation with precision")
    print("✓ Chain and DEX compatibility checks")

if __name__ == "__main__":
    main()