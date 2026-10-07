
export enum PatronCategory {
    ADULT = 'adult',
    YOUTH = 'youth',
    STAFF = 'staff',
    RESEARCHER = 'researcher',
    RESTRICTED = 'restricted'
}

export enum CheckoutStatus {
    ACTIVE = 'active',
    RETURNED = 'returned',
    OVERDUE = 'overdue',
    LOST = 'lost'
}

export enum HoldStatus {
    PENDING = 'pending',
    READY = 'ready',
    FULFILLED = 'fulfilled',
    CANCELLED = 'cancelled',
    EXPIRED = 'expired'
}

export enum FineReason {
    OVERDUE = 'overdue',
    DAMAGE = 'damage',
    LOST = 'lost',
    PROCESSING = 'processing'
}

export interface Patron {
    id: string;
    barcode: string;
    name: string;
    email: string;
    phone: string;
    category: PatronCategory;
    checkout_limit: number;
    hold_limit: number;
    blocked: boolean;
    block_reason: string | null;
}

export interface Checkout {
    id: string;
    instance_id: string;
    patron_id: string;
    checked_out_at: string;
    due_date: string;
    returned_at: string | null;
    status: CheckoutStatus;
    book_title?: string; // Optional, added by frontend or backend summary
}

export interface Hold {
    id: string;
    book_id: string;
    patron_id: string;
    position: number;
    status: HoldStatus;
    created_at: string;
    notified_at: string | null;
    expires_at: string | null;
    book_title?: string;
    estimated_wait?: string;
}

export interface Fine {
    id: string;
    patron_id: string;
    checkout_id: string;
    reason: FineReason;
    amount: number;
    description: string;
    paid: boolean;
    paid_at: string | null;
    waived: boolean;
    waived_reason: string | null;
    created_at: string;
}

export interface PatronResponse {
    patron: Patron;
    current_checkouts: number;
    active_holds: number;
    fines_owed: number;
}

export interface PatronSummaryResponse {
    patron: Patron;
    checkouts: Checkout[];
    holds: Hold[];
    fines: Fine[];
    total_fines_owed: number;
}

export interface RenewalResponse {
    checkout: Checkout;
    new_due_date: string;
    renewals_remaining: number;
}
