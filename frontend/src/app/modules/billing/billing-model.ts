export interface ChargeI {
  id: number;
  reservation: number;
  charge_type: number | null;
  charge_type_name?: string;
  charge_type_code?: string;
  service?: number | null;
  service_name?: string;
  package?: number | null;
  package_name?: string;
  description: string;
  quantity: number;
  unit_price: string | number;
  total_amount: string | number;
  charge_date?: string;
  is_active: boolean;
  is_automatic: boolean;
  automation_key?: string | null;
}

export interface ChargeCreatePayloadI {
  reservation: number;
  charge_type?: number | null;
  service?: number | null;
  package?: number | null;
  description?: string;
  quantity: number;
  unit_price?: number;
  is_active?: boolean;
}

export interface InvoiceChargeI {
  id: number;
  invoice: number;
  charge: number;
  charge_description?: string;
  charge_total_amount?: string | number;
  created_at?: string;
}

export interface InvoiceI {
  id: number;
  reservation: number;
  status: number;
  status_name?: string;
  status_code?: string;
  invoice_number: string;
  issue_date?: string;
  subtotal: string | number;
  tax_amount: string | number;
  total_amount: string | number;
  notes?: string | null;
  is_active: boolean;
  invoice_charges?: InvoiceChargeI[];
  created_at?: string;
  updated_at?: string;
}

export interface InvoiceCreatePayloadI {
  reservation: number;
  status: number;
  invoice_number: string;
  subtotal?: number;
  tax_amount?: number;
  notes?: string | null;
  is_active?: boolean;
}

export interface PaymentI {
  id: number;
  invoice: number;
  invoice_number?: string;
  payment_method: number | null;
  payment_method_name?: string;
  payment_method_code?: string;
  amount: string | number;
  payment_date?: string;
  reference?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface PaymentCreatePayloadI {
  invoice: number;
  payment_method: number | null;
  amount: number;
  reference?: string | null;
  notes?: string | null;
  is_active?: boolean;
}
