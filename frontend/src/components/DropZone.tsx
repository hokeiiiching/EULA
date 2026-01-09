/**
 * 3-Way Match DropZone component for document uploads.
 * 
 * Three distinct drop zones for Invoice, PO, and POD documents.
 */

import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import type { DocumentBundle } from '../types';
import './DropZone.css';

interface DropZoneProps {
    documents: DocumentBundle;
    onDrop: (type: keyof DocumentBundle, file: File) => void;
    onClear: (type: keyof DocumentBundle) => void;
    disabled?: boolean;
}

interface SingleDropZoneProps {
    label: string;
    description: string;
    type: keyof DocumentBundle;
    file: File | null;
    status: 'empty' | 'uploaded' | 'processing' | 'error';
    onDrop: (file: File) => void;
    onClear: () => void;
    disabled?: boolean;
    icon: string;
}

function SingleDropZone({
    label,
    description,
    file,
    status,
    onDrop,
    onClear,
    disabled,
    icon,
}: SingleDropZoneProps) {
    const handleDrop = useCallback((acceptedFiles: File[]) => {
        if (acceptedFiles.length > 0) {
            onDrop(acceptedFiles[0]);
        }
    }, [onDrop]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop: handleDrop,
        accept: {
            'application/pdf': ['.pdf'],
            'image/png': ['.png'],
            'image/jpeg': ['.jpg', '.jpeg'],
        },
        maxFiles: 1,
        disabled: disabled || status === 'processing',
    });

    return (
        <div className={`dropzone-single ${status} ${isDragActive ? 'drag-active' : ''}`}>
            <div {...getRootProps()} className="dropzone-area">
                <input {...getInputProps()} />

                <div className="dropzone-icon">{icon}</div>
                <div className="dropzone-label">{label}</div>

                {status === 'empty' && (
                    <div className="dropzone-prompt">
                        {isDragActive ? 'Drop here...' : description}
                    </div>
                )}

                {status === 'uploaded' && file && (
                    <div className="dropzone-file">
                        <span className="file-name">{file.name}</span>
                        <span className="file-size">
                            {(file.size / 1024).toFixed(1)} KB
                        </span>
                    </div>
                )}

                {status === 'processing' && (
                    <div className="dropzone-processing">
                        <span className="animate-spin">⟳</span>
                        Processing...
                    </div>
                )}

                {status === 'error' && (
                    <div className="dropzone-error">
                        Upload failed
                    </div>
                )}
            </div>

            {status === 'uploaded' && (
                <button
                    className="dropzone-clear"
                    onClick={(e) => {
                        e.stopPropagation();
                        onClear();
                    }}
                    disabled={disabled}
                >
                    ×
                </button>
            )}
        </div>
    );
}

export function DropZone({
    documents,
    onDrop,
    onClear,
    disabled = false,
}: DropZoneProps) {
    return (
        <div className="dropzone-container">
            <h3>Upload Documents</h3>
            <p>Upload all three documents for 3-way match verification</p>

            <div className="dropzone-grid">
                <SingleDropZone
                    label="Invoice"
                    description="Drop invoice PDF or image"
                    type="invoice"
                    icon="📄"
                    file={documents.invoice.file}
                    status={documents.invoice.status}
                    onDrop={(file) => onDrop('invoice', file)}
                    onClear={() => onClear('invoice')}
                    disabled={disabled}
                />

                <SingleDropZone
                    label="Purchase Order"
                    description="Drop PO PDF or image"
                    type="purchaseOrder"
                    icon="📋"
                    file={documents.purchaseOrder.file}
                    status={documents.purchaseOrder.status}
                    onDrop={(file) => onDrop('purchaseOrder', file)}
                    onClear={() => onClear('purchaseOrder')}
                    disabled={disabled}
                />

                <SingleDropZone
                    label="Proof of Delivery"
                    description="Drop POD PDF or image"
                    type="proofOfDelivery"
                    icon="📦"
                    file={documents.proofOfDelivery.file}
                    status={documents.proofOfDelivery.status}
                    onDrop={(file) => onDrop('proofOfDelivery', file)}
                    onClear={() => onClear('proofOfDelivery')}
                    disabled={disabled}
                />
            </div>

            <div className="dropzone-formats">
                Accepted formats: PDF, PNG, JPG
            </div>
        </div>
    );
}

export default DropZone;
