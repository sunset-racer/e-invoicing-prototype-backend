import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Annotated

from pydantic import (
    BaseModel, 
    Field, 
    field_validator, 
    model_validator, 
    ConfigDict
)

# --- ENUMS (Standardizing our constants) ---
class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class InvoiceStatus(str, Enum):
    RECEIVED = "RECEIVED" # Draft state
    SUCCESS = "SUCCESS"   # Cleared/Signed
    FAILED = "FAILED"     # Rejected by Tax Authority

# --- SUB-MODELS ---
class InvoiceItem(BaseModel):
    description: str = Field(..., min_length=3, max_length=200, description="Item details")
    quantity: int = Field(..., gt=0, description="Positive integer count")
    unit_price: Decimal = Field(..., gt=0, decimal_places=2, description="Price per unit")

# --- MAIN SCHEMA ---
class InvoiceSchema(BaseModel):
    """
    Represents the strict structure of an E-Invoice.
    Automates validation and financial calculations (Subtotal + Tax).
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    id: Optional[str] = Field(None, alias="_id")
    
    sender_id: str = Field(..., description="VAT or Tax ID of the Sender")
    receiver_id: str = Field(..., description="VAT or Tax ID of the Receiver")
    
    items: List[InvoiceItem] = Field(..., min_length=1, description="Line items")
    
    # --- FINANCIAL FIELDS ---
    currency: Currency = Currency.USD
    
    # We default tax rate to 15% (Common VAT standard), but it can be overridden
    tax_rate: Decimal = Field(default=Decimal("0.15"), ge=0, le=1, description="Tax Rate (e.g., 0.15 for 15%)")
    
    # Computed Fields (Calculated automatically below)
    subtotal: Decimal = Field(default=Decimal("0.00"), description="Sum of items before tax")
    tax_amount: Decimal = Field(default=Decimal("0.00"), description="Calculated Tax Amount")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Final Total (Subtotal + Tax)")
    
    status: InvoiceStatus = Field(default=InvoiceStatus.RECEIVED)
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # --- VALIDATORS ---

    @field_validator("sender_id", "receiver_id")
    @classmethod
    def validate_tax_ids(cls, v: str) -> str:
        # Regex: 5-20 chars, uppercase letters, numbers, and hyphens only
        pattern = r"^[A-Z0-9\-]{5,20}$"
        if not re.fullmatch(pattern, v):
            raise ValueError(f"Invalid Tax ID format: '{v}'. Use uppercase alphanumerics (e.g., US-TAX-101).")
        return v

    @model_validator(mode="after")
    def calculate_financials(self):
        """
        The 'Source of Truth' Calculation Engine.
        We compute Subtotal, Tax, and Total here to ensure data integrity.
        """
        # 1. Calculate Subtotal
        raw_subtotal = sum(
            (item.quantity * item.unit_price for item in self.items),
            Decimal("0.00")
        )
        # Round to 2 decimal places
        self.subtotal = raw_subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # 2. Calculate Tax
        raw_tax = self.subtotal * self.tax_rate
        self.tax_amount = raw_tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # 3. Calculate Final Total
        self.total_amount = self.subtotal + self.tax_amount
        
        return self