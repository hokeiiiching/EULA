/**
 * VerificationStatus component displays verification results.
 * 
 * Shows validation check results, anomalies, and extracted data.
 */

// import React from 'react';
import type { VerificationResult } from '../types';
import './VerificationStatus.css';

interface VerificationStatusProps {
    result: VerificationResult;
    onMint: () => void;
    onReset: () => void;
}

export function VerificationStatus({
    result,
    onMint,
    onReset,
}: VerificationStatusProps) {
    const statusConfig = {
        passed: { label: 'Forensic Audit Passed', icon: '✓', className: 'status-passed' },
        failed: { label: 'Audit Failed', icon: '✗', className: 'status-failed' },
        requires_review: { label: 'Manual Review Required', icon: '!', className: 'status-review' },
        pending: { label: 'Pending', icon: '○', className: 'status-pending' },
        processing: { label: 'Processing...', icon: '⟳', className: 'status-processing' },
    };

    const config = statusConfig[result.status];
    const canMint = result.status === 'passed' || result.status === 'requires_review';

    return (
        <div className="verification-status">
            <div className={`status-header ${config.className}`}>
                <span className="status-icon">{config.icon}</span>
                <h3>{config.label}</h3>
            </div>

            {/* Extracted Data */}
            <div className="extracted-data card">
                <h4>Extracted Document Data</h4>
                <div className="data-grid">
                    <div className="data-item">
                        <span className="data-label">Invoice #</span>
                        <span className="data-value">{result.extractedData.invoiceNumber || '—'}</span>
                    </div>
                    <div className="data-item">
                        <span className="data-label">Total Amount</span>
                        <span className="data-value highlight">
                            {result.extractedData.currency} {result.extractedData.totalAmount || '0.00'}
                        </span>
                    </div>
                    <div className="data-item">
                        <span className="data-label">Due Date</span>
                        <span className="data-value">{result.extractedData.dueDate || '—'}</span>
                    </div>
                    <div className="data-item">
                        <span className="data-label">Payee</span>
                        <span className="data-value">{result.extractedData.payeeName || '—'}</span>
                    </div>
                    <div className="data-item">
                        <span className="data-label">Payer</span>
                        <span className="data-value">{result.extractedData.payerName || '—'}</span>
                    </div>
                    <div className="data-item">
                        <span className="data-label">PO #</span>
                        <span className="data-value">{result.extractedData.poNumber || '—'}</span>
                    </div>
                </div>
            </div>

            {/* Validation Checks */}
            <div className="validation-checks card">
                <h4>Validation Checks</h4>
                <div className="checks-list">
                    {result.checks.map((check, index) => (
                        <div
                            key={index}
                            className={`check-item ${check.passed ? 'check-passed' : 'check-failed'}`}
                        >
                            <span className="check-icon">{check.passed ? '✓' : '✗'}</span>
                            <div className="check-content">
                                <span className="check-name">{formatRuleName(check.ruleName)}</span>
                                <span className="check-message">{check.message}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Anomalies */}
            {result.anomalies.length > 0 && (
                <div className="anomalies card">
                    <h4>Anomalies Detected</h4>
                    <div className="anomalies-list">
                        {result.anomalies.map((anomaly, index) => (
                            <div
                                key={index}
                                className={`anomaly-item anomaly-${anomaly.severity}`}
                            >
                                <span className="anomaly-icon">
                                    {anomaly.severity === 'error' ? '⚠' : '!'}
                                </span>
                                <div className="anomaly-content">
                                    <span className="anomaly-code">{anomaly.code}</span>
                                    <span className="anomaly-message">{anomaly.message}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Review Flags */}
            {result.reviewFlags.length > 0 && (
                <div className="review-flags card">
                    <h4>Manual Review Required</h4>
                    <p>The following fields have low OCR confidence:</p>
                    <ul>
                        {result.reviewFlags.map((flag, index) => (
                            <li key={index}>{flag}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Document Hashes */}
            <div className="hashes card">
                <h4>Document Hashes</h4>
                <div className="hash-list">
                    <div className="hash-item">
                        <span className="hash-label">Invoice</span>
                        <code className="hash-value">{truncateHash(result.invoiceHash)}</code>
                    </div>
                    <div className="hash-item">
                        <span className="hash-label">PO</span>
                        <code className="hash-value">{truncateHash(result.poHash)}</code>
                    </div>
                    <div className="hash-item">
                        <span className="hash-label">POD</span>
                        <code className="hash-value">{truncateHash(result.podHash)}</code>
                    </div>
                    <div className="hash-item">
                        <span className="hash-label">Bundle</span>
                        <code className="hash-value">{truncateHash(result.bundleHash)}</code>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="actions">
                {canMint && (
                    <button className="btn btn-primary" onClick={onMint}>
                        Mint Invoice NFT
                    </button>
                )}
                <button className="btn btn-secondary" onClick={onReset}>
                    Start Over
                </button>
            </div>
        </div>
    );
}

function formatRuleName(name: string): string {
    return name
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function truncateHash(hash: string | undefined): string {
    if (!hash) return '—';
    if (hash.length <= 20) return hash;
    return `${hash.slice(0, 16)}...${hash.slice(-4)}`;
}

export default VerificationStatus;
