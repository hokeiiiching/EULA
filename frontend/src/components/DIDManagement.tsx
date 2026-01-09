import { useState } from 'react';
import type { WalletState, DIDVerification } from '../types';
import './DIDManagement.css';

interface DIDManagementProps {
    onClose: () => void;
    wallet: WalletState;
    did: DIDVerification | null;
    createDID: (businessName: string, registrationNumber: string, country: string) => Promise<void>;
    removeDID: () => Promise<void>;
    isLoading: boolean;
    error: string | null;
}

export function DIDManagement({
    onClose,
    wallet,
    did,
    createDID,
    removeDID,
    isLoading,
    error
}: DIDManagementProps) {
    // const { did, createDID, removeDID, isLoading, error } = useWallet(); // Removed isolated hook
    const [businessName, setBusinessName] = useState('');
    const [registrationNumber, setRegistrationNumber] = useState('');
    const [country, setCountry] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!businessName || !registrationNumber || !country) return;

        console.log('[DIDManagement] Creating DID...');
        setIsSubmitting(true);
        try {
            await createDID(businessName, registrationNumber, country);
            console.log('[DIDManagement] DID created successfully');
            onClose(); // Close modal on success
        } catch (err) {
            console.error('[DIDManagement] Failed to create DID:', err);
            // Error is already set in hook, but let's log it explicitly
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm('Are you sure you want to delete your DID? This action cannot be undone.')) {
            return;
        }

        setIsSubmitting(true);
        try {
            await removeDID();
        } catch (err) {
            console.error('Failed to delete DID:', err);
        } finally {
            setIsSubmitting(false);
        }
    };

    if (did && did.status === 'verified') {
        return (
            <div className="did-management card card-elevated">
                <div className="did-header">
                    <h3>Digital Identity (DID)</h3>
                    <button className="close-btn" onClick={onClose}>×</button>
                </div>

                <div className="did-content">
                    <div className="did-status verified">
                        <span className="icon">✓</span> Verified Business Identity
                    </div>

                    <div className="did-details">
                        <div className="detail-row">
                            <span className="label">Business Name</span>
                            <span className="value">{did.businessName}</span>
                        </div>
                        <div className="detail-row">
                            <span className="label">Registration #</span>
                            <span className="value">{did.registrationNumber}</span>
                        </div>
                        <div className="detail-row">
                            <span className="label">Country</span>
                            <span className="value">{did.country}</span>
                        </div>
                        <div className="detail-row">
                            <span className="label">DID</span>
                            <span className="value mono">{did.walletAddress}</span>
                        </div>
                    </div>

                    <div className="did-actions">
                        <button
                            className="btn btn-danger"
                            onClick={handleDelete}
                            disabled={isSubmitting || isLoading}
                        >
                            {isSubmitting ? 'Revoking...' : 'Revoke Identity'}
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="did-management card card-elevated">
            <div className="did-header">
                <h3>Create Digital Identity</h3>
                <button className="close-btn" onClick={onClose}>×</button>
            </div>

            <div className="did-content">
                <p className="did-description">
                    Create a Decentralized Identifier (DID) on the XRP Ledger to verify your business identity for invoice factoring.
                </p>

                <form onSubmit={handleCreate}>
                    <div className="form-group">
                        <label htmlFor="businessName">Business Name</label>
                        <input
                            id="businessName"
                            type="text"
                            value={businessName}
                            onChange={(e) => setBusinessName(e.target.value)}
                            placeholder="e.g. Acme Corp"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="registrationNumber">Registration Number</label>
                        <input
                            id="registrationNumber"
                            type="text"
                            value={registrationNumber}
                            onChange={(e) => setRegistrationNumber(e.target.value)}
                            placeholder="e.g. 123456789"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="country">Country Code (ISO 2)</label>
                        <input
                            id="country"
                            type="text"
                            value={country}
                            onChange={(e) => setCountry(e.target.value.toUpperCase())}
                            placeholder="e.g. US"
                            maxLength={2}
                            required
                        />
                    </div>

                    {error && <div className="error-message">{error}</div>}

                    <div className="form-actions">
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={isSubmitting || isLoading}
                        >
                            {isSubmitting ? 'Creating Identity...' : 'Create DID'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
