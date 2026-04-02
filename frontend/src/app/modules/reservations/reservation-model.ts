export type ReservationViewMode = 'table' | 'grid' | 'calendar';

export type ReservationStatusFilter =
  | 'ALL'
  | 'CONFIRMADA'
  | 'PENDIENTE'
  | 'EN_CURSO'
  | 'POR_SALIR_HOY'
  | 'CANCELADA';

export type ReservationVisualStatus =
  | 'CONFIRMADA'
  | 'PENDIENTE'
  | 'EN_CURSO'
  | 'POR_SALIR_HOY'
  | 'CANCELADA'
  | 'FINALIZADA'
  | 'OTRA';

export interface ReservationI {
  id: number;
  client: number;
  client_full_name?: string;
  client_document_number?: string;
  status: number;
  status_name?: string;
  status_code?: string;
  origin: number;
  origin_name?: string;
  origin_code?: string;
  expected_check_in: string;
  expected_check_out: string;
  real_check_in?: string | null;
  real_check_out?: string | null;
  promo_code?: string | null;
  total_discount?: string | number;
  notes?: string | null;
  total_rooms?: number;
  total_guests?: number;
  total_nights?: number;
  created_by?: string | null;
  created_at?: string;
}

export interface ReservationWritePayloadI {
  client: number;
  origin: number;
  expected_check_in: string;
  expected_check_out: string;
  real_check_in?: string | null;
  real_check_out?: string | null;
  promo_code?: string | null;
  total_discount?: string | number;
  notes?: string | null;
}

export interface ReservationRoomI {
  id: number;
  reservation: number;
  room: number;
  room_number?: string;
  night_rate: string | number;
  adults: number;
  children: number;
  meal_plan?: number | null;
  meal_plan_name?: string;
  meal_plan_code?: string;
  subtotal?: string | number;
  created_at?: string;
}

export interface ReservationRoomPayloadI {
  reservation: number;
  room: number;
  night_rate: string | number;
  adults: number;
  children: number;
  meal_plan?: number | null;
}

export interface ReservationGuestI {
  id: number;
  reservation: number;
  document_type?: number | null;
  document_type_name?: string;
  document_type_code?: string;
  document_number?: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  birth_date?: string | null;
  nationality?: string | null;
  blood_type?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  created_at?: string;
}

export interface ReservationGuestPayloadI {
  reservation: number;
  document_type: number;
  document_number: string;
  first_name: string;
  last_name: string;
  birth_date?: string | null;
  nationality?: string | null;
  blood_type?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
}

export interface ReservationDepositI {
  id: number;
  reservation: number;
  deposit_date: string;
  amount: string | number;
  payment_method?: number | null;
  payment_method_name?: string;
  payment_method_code?: string;
  reference?: string | null;
  status?: number | null;
  status_name?: string;
  status_code?: string;
  notes?: string | null;
  created_at?: string;
}

export interface ReservationDetailI extends ReservationI {
  client_email?: string;
  client_phone?: string;
  rooms_detail: ReservationRoomI[];
  guests: ReservationGuestI[];
  deposits: ReservationDepositI[];
}

export interface ReservationStatusStyleI {
  label: string;
  chipBg: string;
  chipColor: string;
  dotColor: string;
  borderColor: string;
  actionBg: string;
  actionColor: string;
}
