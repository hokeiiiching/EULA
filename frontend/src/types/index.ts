/**
 * TypeScript type definitions for EULA frontend.
 */

// Verification status from API
export type VerificationStatus =
    | 'pending'
    | 'processing'
    | 'passed'
    | 'failed'
    | 'requires_review';

// DID status
export type DIDStatus =
    | 'verified'
    | 'not_found'
    | 'expired'
    | 'revoked'
    | 'invalid';

// Document types for 3-way match
export type DocumentType = 'invoice' | 'po' | 'pod';

// Wallet connection state
export interface WalletState {
    isConnected: boolean;
    address: string | null;
    network: 'testnet' | 'mainnet' | null;
}

// DID verification result
export interface DIDVerification {
    walletAddress: string;
    status: DIDStatus;
    businessName?: string;
    registrationNumber?: string;
    country?: string;
    message: string;
}

// Single validation check result
export interface ValidationCheck {
    ruleName: string;
    passed: boolean;
    message: string;
    details: Record<string, unknown>;
}

// Detected anomaly
export interface Anomaly {
    code: string;
    message: string;
    severity: 'warning' | 'error';
    fieldPath: string;
}

// Extracted document data
export interface ExtractedData {
    invoiceNumber?: string;
    totalAmount?: string;
    currency: string;
    invoiceDate?: string;
    dueDate?: string;
    payeeName?: string;
    payerName?: string;
    poNumber?: string;
    podReference?: string;
}

// Complete verification response
export interface VerificationResult {
    verificationId: string;
    status: VerificationStatus;
    checks: ValidationCheck[];
    anomalies: Anomaly[];
    reviewFlags: string[];
    extractedData: ExtractedData;
    invoiceHash?: string;
    poHash?: string;
    podHash?: string;
    bundleHash?: string;
    createdAt: string;
}

// Document upload state
export interface DocumentUpload {
    file: File | null;
    preview?: string;
    status: 'empty' | 'uploaded' | 'processing' | 'error';
    error?: string;
}

// 3-way match document set
export interface DocumentBundle {
    invoice: DocumentUpload;
    purchaseOrder: DocumentUpload;
    proofOfDelivery: DocumentUpload;
}

// API error response
export interface ApiError {
    error: string;
    detail?: string;
    code?: string;
}

// Mint transaction payload
export interface MintTransaction {
    transactionType: string;
    account: string;
    uriHex: string;
    flags: number;
    transferFee: number;
    nftokenTaxon: number;
    memos: Record<string, unknown>[];
    faceValue: string;
    salePrice: string;
    currency: string;
}
