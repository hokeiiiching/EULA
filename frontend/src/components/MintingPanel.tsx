/**
 * MintingPanel Component
 * 
 * NFT minting interface that guides users through the tokenization process.
 * Uses Crossmark wallet for transaction signing on XRPL.
 */

import { useState, useEffect, useCallback } from 'react';
import type { VerificationResult } from '../types';
import {
    isCrossmarkAvailable,
    signAndSubmitNFTMint,
    createSellOffer,
    getExplorerUrl,
    getAccountNFTs,
    type NFTokenMintTransaction,
} from '../services/crossmark';
import './MintingPanel.css';

// ============================================================================
// Types
// ============================================================================

interface MintingPanelProps {
    verificationResult: VerificationResult;
    walletAddress: string;
    onClose: () => void;
}

type MintStep = 'idle' | 'preparing' | 'signing' | 'submitted' | 'confirmed' | 'error';

interface MintState {
    step: MintStep;
    message: string;
    txHash?: string;
    nftTokenId?: string;
    explorerUrl?: string;
}

// ============================================================================
// Constants
// ============================================================================

const INITIAL_STATE: MintState = {
    step: 'idle',
    message: '',
};

const STEP_MESSAGES: Record<MintStep, string> = {
    idle: 'Ready to mint',
    preparing: 'Preparing transaction...',
    signing: 'Please approve the transaction in Crossmark...',
    submitted: 'Transaction submitted to XRPL...',
    confirmed: 'NFT successfully minted!',
    error: 'Minting failed',
};

// ============================================================================
// Component
// ============================================================================

export function MintingPanel({
    verificationResult,
    walletAddress,
    onClose,
}: MintingPanelProps) {
    // State
    const [state, setState] = useState<MintState>(INITIAL_STATE);
    const [discountPercent, setDiscountPercent] = useState(5);
    const [isProcessing, setIsProcessing] = useState(false);
    const [crossmarkAvailable, setCrossmarkAvailable] = useState(false);
    const [offerCreated, setOfferCreated] = useState(false);
    const [isCreatingOffer, setIsCreatingOffer] = useState(false);

    // Derived values
    const faceValue = parseFloat(verificationResult.extractedData.totalAmount || '0');
    const salePrice = faceValue * (1 - discountPercent / 100);


    // Check Crossmark availability on mount
    useEffect(() => {
        const checkAvailability = async () => {
            // Wait for extension to inject
            await new Promise(resolve => setTimeout(resolve, 300));
            const available = isCrossmarkAvailable();
            setCrossmarkAvailable(available);
            console.log('[MintingPanel] Crossmark available:', available);
        };
        checkAvailability();
    }, []);

    /**
     * Update the minting state with proper logging.
     */
    const updateState = useCallback((step: MintStep, extras?: Partial<MintState>) => {
        const message = extras?.message || STEP_MESSAGES[step];
        console.log(`[MintingPanel] State change: ${step} - ${message}`);
        setState({ step, message, ...extras });
    }, []);

    /**
     * Prepare the NFT mint transaction by calling the backend API.
     */
    const prepareMintTransaction = async (): Promise<NFTokenMintTransaction> => {
        console.log('[MintingPanel] Preparing mint transaction...');
        console.log('[MintingPanel] Request params:', {
            verification_id: verificationResult.verificationId,
            wallet_address: walletAddress,
            discount_percent: discountPercent,
        });

        const response = await fetch('/api/v1/mint/prepare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                verification_id: verificationResult.verificationId,
                wallet_address: walletAddress,
                discount_percent: discountPercent,
            }),
        });

        console.log('[MintingPanel] Backend response status:', response.status);

        if (!response.ok) {
            let errorDetail = `HTTP ${response.status}`;
            try {
                const errorBody = await response.json();
                console.error('[MintingPanel] Backend error:', errorBody);
                errorDetail = errorBody.detail || errorBody.message || JSON.stringify(errorBody);
            } catch {
                // Ignore JSON parse errors
            }
            throw new Error(`Backend error: ${errorDetail}`);
        }

        const payload = await response.json();
        console.log('[MintingPanel] Transaction payload:', payload);

        // Build the transaction object
        return {
            TransactionType: 'NFTokenMint',
            Account: walletAddress,
            URI: payload.uri_hex,
            Flags: payload.flags,
            TransferFee: payload.transfer_fee,
            NFTokenTaxon: payload.nftoken_taxon,
        };
    };

    /**
     * Handle the mint button click.
     * Orchestrates the full minting flow.
     */
    const handleMint = async () => {
        if (isProcessing) return;

        console.log('═'.repeat(60));
        console.log('[MintingPanel] MINTING STARTED');
        console.log('═'.repeat(60));

        setIsProcessing(true);

        try {
            // Step 1: Prepare transaction
            updateState('preparing');
            const transaction = await prepareMintTransaction();
            console.log('[MintingPanel] Transaction prepared:', transaction);

            // Step 2: Sign with Crossmark
            updateState('signing');
            const result = await signAndSubmitNFTMint(transaction);

            if (!result.success) {
                throw new Error(result.error || 'Transaction failed');
            }

            // Step 3: Get the minted NFT Token ID
            updateState('submitted', { message: 'Fetching NFT Token ID...' });

            // Wait a moment for ledger to update, then fetch NFTs
            await new Promise(resolve => setTimeout(resolve, 2000));
            const nfts = await getAccountNFTs(walletAddress);
            const latestNft = nfts.length > 0 ? nfts[nfts.length - 1] : null;
            const nftTokenId = latestNft?.NFTokenID;

            console.log('[MintingPanel] Fetched NFTs:', nfts);
            console.log('[MintingPanel] Latest NFT Token ID:', nftTokenId);

            // Step 4: Success
            const explorerUrl = result.hash ? getExplorerUrl(result.hash) : undefined;
            updateState('confirmed', {
                txHash: result.hash,
                nftTokenId,
                explorerUrl,
            });

            console.log('═'.repeat(60));
            console.log('[MintingPanel] MINTING SUCCESS');
            console.log('[MintingPanel] Transaction hash:', result.hash);
            console.log('[MintingPanel] NFT Token ID:', nftTokenId);
            console.log('═'.repeat(60));

        } catch (error) {
            console.error('═'.repeat(60));
            console.error('[MintingPanel] MINTING FAILED');
            console.error('[MintingPanel] Error:', error);
            console.error('═'.repeat(60));

            const message = error instanceof Error ? error.message : 'Unknown error occurred';
            updateState('error', { message });
        } finally {
            setIsProcessing(false);
        }
    };

    /**
     * Handle creating a sell offer on DEX.
     */
    const handleCreateOffer = async () => {
        if (!state.nftTokenId) {
            console.error('[MintingPanel] No NFT Token ID available');
            return;
        }

        setIsCreatingOffer(true);
        console.log('[MintingPanel] Creating sell offer for NFT:', state.nftTokenId);

        try {
            // Use sale price directly for RLUSD (no drops conversion)
            const priceString = salePrice.toFixed(2);

            const result = await createSellOffer({
                account: walletAddress,
                nftokenId: state.nftTokenId,
                amount: priceString,
            });

            if (result.success) {
                setOfferCreated(true);
                console.log('[MintingPanel] Sell offer created! Hash:', result.hash);
                alert(`✅ Sell offer created!\n\nYour invoice NFT is now listed for sale at ${salePrice.toFixed(2)} RLUSD.\n\nTransaction: ${result.hash}`);
            } else {
                throw new Error(result.error || 'Failed to create offer');
            }
        } catch (error) {
            console.error('[MintingPanel] Failed to create offer:', error);
            const message = error instanceof Error ? error.message : 'Unknown error';
            alert(`❌ Failed to create sell offer: ${message}`);
        } finally {
            setIsCreatingOffer(false);
        }
    };

    // ========================================================================
    // Render
    // ========================================================================

    const showPricing = state.step === 'idle' && !isProcessing;
    const showProgress = isProcessing || state.step === 'confirmed' || state.step === 'error';
    const canMint = crossmarkAvailable && !isProcessing && state.step === 'idle';

    return (
        <div className="minting-panel">
            {/* Header */}
            <div className="minting-header">
                <h2>🎨 Mint Invoice NFT</h2>
                <button className="close-btn" onClick={onClose} aria-label="Close">
                    ×
                </button>
            </div>

            {/* Crossmark Warning */}
            {!crossmarkAvailable && state.step === 'idle' && (
                <div className="crossmark-warning card">
                    <p>⚠️ <strong>Crossmark wallet not detected!</strong></p>
                    <p>Please install the Crossmark browser extension:</p>
                    <a
                        href="https://crossmark.io"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-sm"
                    >
                        Install Crossmark →
                    </a>
                </div>
            )}

            {/* Invoice Summary */}
            <div className="invoice-summary card">
                <h4>Invoice Details</h4>
                <div className="summary-grid">
                    <SummaryItem
                        label="Invoice #"
                        value={verificationResult.extractedData.invoiceNumber}
                    />
                    <SummaryItem
                        label="Payee"
                        value={verificationResult.extractedData.payeeName}
                    />
                    <SummaryItem
                        label="Due Date"
                        value={verificationResult.extractedData.dueDate}
                    />
                    <SummaryItem
                        label="Face Value"
                        value={`${faceValue.toLocaleString('en-US', { minimumFractionDigits: 2 })} RLUSD`}
                        highlight
                    />
                </div>
            </div>

            {/* Pricing Section */}
            {showPricing && (
                <div className="pricing card">
                    <h4>Set Sale Price</h4>
                    <DiscountSlider
                        value={discountPercent}
                        onChange={setDiscountPercent}
                    />
                    <PricePreview
                        faceValue={faceValue}
                        discountPercent={discountPercent}
                        salePrice={salePrice}
                    />
                </div>
            )}

            {/* Progress Steps */}
            {showProgress && (
                <ProgressSteps currentStep={state.step} />
            )}

            {/* Status Message */}
            <StatusMessage step={state.step} message={state.message} />

            {/* Success Result */}
            {state.step === 'confirmed' && state.txHash && (
                <SuccessResult
                    txHash={state.txHash}
                    explorerUrl={state.explorerUrl}
                    salePrice={salePrice}
                />
            )}

            {/* Actions */}
            <div className="minting-actions">
                {canMint && (
                    <button className="btn btn-primary btn-lg" onClick={handleMint}>
                        🚀 Mint NFT on XRPL
                    </button>
                )}
                {state.step === 'confirmed' && !offerCreated && state.nftTokenId && (
                    <button
                        className="btn btn-primary"
                        onClick={handleCreateOffer}
                        disabled={isCreatingOffer}
                    >
                        {isCreatingOffer ? '⏳ Creating Offer...' : '💰 List on DEX for Sale'}
                    </button>
                )}
                {state.step === 'confirmed' && offerCreated && (
                    <div className="offer-success">
                        ✅ Listed for sale at {salePrice.toFixed(2)} RLUSD
                    </div>
                )}
                {state.step === 'confirmed' && (
                    <button className="btn btn-secondary" onClick={onClose}>
                        Done
                    </button>
                )}
                {state.step === 'error' && (
                    <button className="btn btn-primary" onClick={handleMint}>
                        Retry
                    </button>
                )}
            </div>
        </div>
    );
}

// ============================================================================
// Sub-components
// ============================================================================

interface SummaryItemProps {
    label: string;
    value: string | undefined;
    highlight?: boolean;
}

function SummaryItem({ label, value, highlight }: SummaryItemProps) {
    return (
        <div className={`summary-item ${highlight ? 'highlight' : ''}`}>
            <span className="label">{label}</span>
            <span className="value">{value || '—'}</span>
        </div>
    );
}

interface DiscountSliderProps {
    value: number;
    onChange: (value: number) => void;
}

function DiscountSlider({ value, onChange }: DiscountSliderProps) {
    return (
        <div className="discount-control">
            <label>Discount Rate</label>
            <div className="discount-input">
                <input
                    type="range"
                    min="0"
                    max="20"
                    value={value}
                    onChange={(e) => onChange(parseInt(e.target.value, 10))}
                />
                <span className="discount-value">{value}%</span>
            </div>
        </div>
    );
}

interface PricePreviewProps {
    faceValue: number;
    discountPercent: number;
    salePrice: number;
}

function PricePreview({ faceValue, discountPercent, salePrice }: PricePreviewProps) {
    const discountAmount = faceValue * (discountPercent / 100);

    return (
        <div className="price-preview">
            <div className="price-item">
                <span>Face Value</span>
                <span>{faceValue.toFixed(2)} RLUSD</span>
            </div>
            <div className="price-item discount">
                <span>Discount ({discountPercent}%)</span>
                <span>-{discountAmount.toFixed(2)} RLUSD</span>
            </div>
            <div className="price-item sale-price">
                <span>Sale Price</span>
                <span className="highlight">{salePrice.toFixed(2)} RLUSD</span>
            </div>
        </div>
    );
}

interface ProgressStepsProps {
    currentStep: MintStep;
}

function ProgressSteps({ currentStep }: ProgressStepsProps) {
    const steps: Array<{ key: MintStep; label: string }> = [
        { key: 'preparing', label: 'Prepare Transaction' },
        { key: 'signing', label: 'Sign with Crossmark' },
        { key: 'submitted', label: 'Submit to XRPL' },
        { key: 'confirmed', label: 'Confirmed' },
    ];

    const getStepStatus = (stepKey: MintStep): 'pending' | 'active' | 'complete' => {
        const stepOrder = ['preparing', 'signing', 'submitted', 'confirmed'];
        const currentIndex = stepOrder.indexOf(currentStep);
        const stepIndex = stepOrder.indexOf(stepKey);

        if (currentStep === 'error') {
            return stepIndex <= currentIndex ? 'active' : 'pending';
        }
        if (stepIndex < currentIndex) return 'complete';
        if (stepIndex === currentIndex) return 'active';
        return 'pending';
    };

    return (
        <div className="minting-progress card">
            {steps.map(({ key, label }) => {
                const status = getStepStatus(key);
                return (
                    <div key={key} className={`progress-step ${status}`}>
                        <span className="step-icon">
                            {status === 'complete' ? '✓' : status === 'active' ? '⟳' : '○'}
                        </span>
                        <span className="step-text">{label}</span>
                    </div>
                );
            })}
        </div>
    );
}

interface StatusMessageProps {
    step: MintStep;
    message: string;
}

function StatusMessage({ step, message }: StatusMessageProps) {
    if (!message) return null;

    const icon = step === 'error' ? '❌' : step === 'confirmed' ? '🎉' : '';

    return (
        <div className={`status-message ${step}`}>
            {icon} {message}
        </div>
    );
}

interface SuccessResultProps {
    txHash: string;
    explorerUrl?: string;
    salePrice: number;
}

function SuccessResult({ txHash, explorerUrl, salePrice }: SuccessResultProps) {
    const truncatedHash = `${txHash.slice(0, 16)}...${txHash.slice(-8)}`;

    return (
        <div className="mint-result card">
            <h4>NFT Minted Successfully!</h4>
            <div className="result-details">
                <div className="result-item">
                    <span className="label">Transaction Hash</span>
                    <code className="value">{truncatedHash}</code>
                </div>
                <div className="result-item">
                    <span className="label">Sale Price</span>
                    <span className="value highlight">
                        {salePrice.toFixed(2)} RLUSD
                    </span>
                </div>
            </div>
            {explorerUrl && (
                <a
                    href={explorerUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="explorer-link"
                >
                    View on XRPL Explorer →
                </a>
            )}
        </div>
    );
}

export default MintingPanel;
