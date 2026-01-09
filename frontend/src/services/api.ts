/**
 * API client for EULA backend.
 */

import type { VerificationResult, DIDVerification, MintTransaction, ApiError } from '../types';

const API_BASE = (import.meta as any).env.VITE_API_URL || '';

/**
 * Verify documents via 3-way match.
 */
export async function verifyDocuments(
    walletAddress: string,
    invoice: File,
    purchaseOrder: File,
    proofOfDelivery: File,
    skipDidCheck: boolean = false
): Promise<VerificationResult> {
    const formData = new FormData();
    formData.append('wallet_address', walletAddress);
    formData.append('invoice', invoice);
    formData.append('purchase_order', purchaseOrder);
    formData.append('proof_of_delivery', proofOfDelivery);
    formData.append('skip_did_check', skipDidCheck.toString());

    const response = await fetch(`${API_BASE}/api/v1/verification/verify`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.detail || error.error);
    }

    const data = await response.json();

    // Convert snake_case to camelCase
    return {
        verificationId: data.verification_id,
        status: data.status,
        checks: data.checks.map((c: any) => ({
            ruleName: c.rule_name,
            passed: c.passed,
            message: c.message,
            details: c.details,
        })),
        anomalies: data.anomalies.map((a: any) => ({
            code: a.code,
            message: a.message,
            severity: a.severity,
            fieldPath: a.field_path,
        })),
        reviewFlags: data.review_flags,
        extractedData: {
            invoiceNumber: data.extracted_data.invoice_number,
            totalAmount: data.extracted_data.total_amount,
            currency: data.extracted_data.currency,
            invoiceDate: data.extracted_data.invoice_date,
            dueDate: data.extracted_data.due_date,
            payeeName: data.extracted_data.payee_name,
            payerName: data.extracted_data.payer_name,
            poNumber: data.extracted_data.po_number,
            podReference: data.extracted_data.pod_reference,
        },
        invoiceHash: data.invoice_hash,
        poHash: data.po_hash,
        podHash: data.pod_hash,
        bundleHash: data.bundle_hash,
        createdAt: data.created_at,
    };
}

/**
 * Check DID verification status for a wallet.
 */
export async function checkDID(
    walletAddress: string,
    refresh: boolean = false
): Promise<DIDVerification> {
    const url = new URL(`${API_BASE}/api/v1/verification/did/${walletAddress}`);
    if (refresh) {
        url.searchParams.append('refresh', 'true');
    }

    const response = await fetch(url.toString());

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.detail || error.error);
    }

    const data = await response.json();

    return {
        walletAddress: data.wallet_address,
        status: data.status,
        businessName: data.business_name,
        registrationNumber: data.registration_number,
        country: data.country,
        message: data.message,
    };
}

/**
 * Prepare NFT mint transaction.
 */
export async function prepareMint(
    verificationId: string,
    discountPercent: number = 4
): Promise<MintTransaction> {
    const response = await fetch(`${API_BASE}/api/v1/mint/prepare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            verification_id: verificationId,
            discount_percent: discountPercent,
        }),
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.detail || error.error);
    }

    const data = await response.json();

    return {
        transactionType: data.transaction_type,
        account: data.account,
        uriHex: data.uri_hex,
        flags: data.flags,
        transferFee: data.transfer_fee,
        nftokenTaxon: data.nftoken_taxon,
        memos: data.memos,
        faceValue: data.face_value,
        salePrice: data.sale_price,
        currency: data.currency,
    };
}

/**
 * Health check.
 */
export async function checkHealth(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
}
