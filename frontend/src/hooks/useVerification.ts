/**
 * Custom React hook for document verification workflow.
 */

import { useState, useCallback } from 'react';
import type { DocumentBundle, VerificationResult, DocumentUpload } from '../types';
import { verifyDocuments as apiVerifyDocuments } from '../services/api';

const initialDocument: DocumentUpload = {
    file: null,
    status: 'empty',
};

const initialBundle: DocumentBundle = {
    invoice: { ...initialDocument },
    purchaseOrder: { ...initialDocument },
    proofOfDelivery: { ...initialDocument },
};

interface UseVerificationReturn {
    documents: DocumentBundle;
    result: VerificationResult | null;
    isProcessing: boolean;
    error: string | null;
    setDocument: (type: keyof DocumentBundle, file: File) => void;
    clearDocument: (type: keyof DocumentBundle) => void;
    verify: (walletAddress: string, skipDidCheck?: boolean) => Promise<void>;
    reset: () => void;
    isComplete: boolean;
}

export function useVerification(): UseVerificationReturn {
    const [documents, setDocuments] = useState<DocumentBundle>(initialBundle);
    const [result, setResult] = useState<VerificationResult | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const setDocument = useCallback((type: keyof DocumentBundle, file: File) => {
        setDocuments(prev => ({
            ...prev,
            [type]: {
                file,
                preview: URL.createObjectURL(file),
                status: 'uploaded' as const,
            },
        }));
        // Clear any previous result when documents change
        setResult(null);
        setError(null);
    }, []);

    const clearDocument = useCallback((type: keyof DocumentBundle) => {
        setDocuments(prev => {
            // Clean up preview URL
            if (prev[type].preview) {
                URL.revokeObjectURL(prev[type].preview!);
            }
            return {
                ...prev,
                [type]: { ...initialDocument },
            };
        });
    }, []);

    const verify = useCallback(async (
        walletAddress: string,
        skipDidCheck: boolean = false
    ) => {
        // Validate all documents are uploaded
        if (!documents.invoice.file ||
            !documents.purchaseOrder.file ||
            !documents.proofOfDelivery.file) {
            setError('Please upload all three documents');
            return;
        }

        setIsProcessing(true);
        setError(null);

        try {
            const verificationResult = await apiVerifyDocuments(
                walletAddress,
                documents.invoice.file,
                documents.purchaseOrder.file,
                documents.proofOfDelivery.file,
                skipDidCheck
            );
            setResult(verificationResult);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Verification failed';
            setError(message);
        } finally {
            setIsProcessing(false);
        }
    }, [documents]);

    const reset = useCallback(() => {
        // Clean up all preview URLs
        Object.values(documents).forEach(doc => {
            if (doc.preview) {
                URL.revokeObjectURL(doc.preview);
            }
        });
        setDocuments(initialBundle);
        setResult(null);
        setError(null);
    }, [documents]);

    const isComplete = Boolean(
        documents.invoice.file &&
        documents.purchaseOrder.file &&
        documents.proofOfDelivery.file
    );

    return {
        documents,
        result,
        isProcessing,
        error,
        setDocument,
        clearDocument,
        verify,
        reset,
        isComplete,
    };
}
