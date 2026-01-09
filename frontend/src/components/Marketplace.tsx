/**
 * Marketplace Component
 * 
 * Allows invoice factorers to search and buy NFT invoices by Token ID.
 */

import { useState } from 'react';
import {
    getNFTSellOffers,
    acceptSellOffer,
    getExplorerUrl,
    formatOfferAmount,
    formatAddress,
    type NFTSellOffer,
} from '../services/crossmark';
import './Marketplace.css';

// ============================================================================
// Types
// ============================================================================

interface MarketplaceProps {
    buyerAddress: string | null;
    onClose: () => void;
    onConnectWallet?: () => void;
}

interface SearchResult {
    nftokenId: string;
    offers: NFTSellOffer[];
}

// ============================================================================
// Component
// ============================================================================

export function Marketplace({ buyerAddress, onClose, onConnectWallet }: MarketplaceProps) {
    const [searchInput, setSearchInput] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
    const [searchError, setSearchError] = useState<string | null>(null);
    const [buyingOfferId, setBuyingOfferId] = useState<string | null>(null);
    const [purchaseSuccess, setPurchaseSuccess] = useState<{
        hash: string;
    } | null>(null);

    // Handle search for NFT
    const handleSearch = async () => {
        const tokenId = searchInput.trim();

        if (!tokenId) {
            setSearchError('Please enter an NFT Token ID');
            return;
        }

        // Basic validation - NFT Token IDs are 64 hex characters
        if (tokenId.length !== 64 || !/^[0-9A-Fa-f]+$/.test(tokenId)) {
            setSearchError('Invalid NFT Token ID. Should be 64 hexadecimal characters.');
            return;
        }

        setIsSearching(true);
        setSearchError(null);
        setSearchResult(null);

        try {
            console.log('[Marketplace] Searching for NFT:', tokenId);
            const offers = await getNFTSellOffers(tokenId);

            console.log('[Marketplace] Found offers:', offers);

            setSearchResult({
                nftokenId: tokenId,
                offers,
            });

            if (offers.length === 0) {
                setSearchError('No sell offers found for this NFT. It may not be listed for sale.');
            }
        } catch (err) {
            console.error('[Marketplace] Search error:', err);
            setSearchError('Failed to search. Please check the Token ID and try again.');
        } finally {
            setIsSearching(false);
        }
    };

    // Handle buying an NFT
    const handleBuy = async (offer: NFTSellOffer) => {
        if (!buyerAddress) {
            if (onConnectWallet) {
                onConnectWallet();
            }
            return;
        }

        if (buyingOfferId) return;

        setBuyingOfferId(offer.index);
        console.log('[Marketplace] Buying NFT:', offer);

        try {
            const result = await acceptSellOffer({
                account: buyerAddress,
                sellOfferId: offer.index,
            });

            if (result.success && result.hash) {
                setPurchaseSuccess({ hash: result.hash });
                // Remove this offer from results
                if (searchResult) {
                    setSearchResult({
                        ...searchResult,
                        offers: searchResult.offers.filter(o => o.index !== offer.index),
                    });
                }
            } else {
                throw new Error(result.error || 'Purchase failed');
            }
        } catch (err) {
            console.error('[Marketplace] Purchase error:', err);
            alert(`❌ Purchase failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setBuyingOfferId(null);
        }
    };

    // Handle Enter key in search
    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    // ========================================================================
    // Render
    // ========================================================================

    return (
        <div className="marketplace">
            {/* Header */}
            <div className="marketplace-header">
                <div className="header-content">
                    <h1>🏪 Invoice Marketplace</h1>
                    <p>Search and purchase tokenized invoices</p>
                </div>
                <button className="close-btn" onClick={onClose}>×</button>
            </div>

            {/* Wallet Status */}
            <div className="wallet-status">
                {buyerAddress ? (
                    <>
                        <span className="status-dot connected"></span>
                        <span className="label">Connected:</span>
                        <span className="address">{formatAddress(buyerAddress)}</span>
                    </>
                ) : (
                    <>
                        <span className="status-dot disconnected"></span>
                        <span className="label">Not connected</span>
                        {onConnectWallet && (
                            <button className="btn btn-sm" onClick={onConnectWallet}>
                                Connect Wallet
                            </button>
                        )}
                    </>
                )}
            </div>

            {/* Search Section */}
            <div className="search-section">
                <h3>🔍 Search by NFT Token ID</h3>
                <p className="search-hint">
                    Paste the NFT Token ID from the seller to find and purchase the invoice
                </p>
                <div className="search-input-group">
                    <input
                        type="text"
                        className="search-input"
                        placeholder="Enter NFT Token ID (64 hex characters)"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        onKeyPress={handleKeyPress}
                        disabled={isSearching}
                    />
                    <button
                        className="btn btn-primary search-btn"
                        onClick={handleSearch}
                        disabled={isSearching || !searchInput.trim()}
                    >
                        {isSearching ? '⏳ Searching...' : 'Search'}
                    </button>
                </div>

                {/* Search Error */}
                {searchError && (
                    <div className="search-message error">
                        ⚠️ {searchError}
                    </div>
                )}
            </div>

            {/* Purchase Success */}
            {purchaseSuccess && (
                <div className="purchase-success">
                    <h3>🎉 Purchase Successful!</h3>
                    <p>You now own this invoice NFT.</p>
                    <a
                        href={getExplorerUrl(purchaseSuccess.hash)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="explorer-link"
                    >
                        View Transaction →
                    </a>

                    {/* Notice of Assignment - Legal Reminder */}
                    <div className="notice-of-assignment">
                        <h4>⚠️ Legal Action Required: Notice of Assignment</h4>
                        <p>
                            To legally collect payment on this invoice, you <strong>must notify the debtor</strong>
                            that the invoice has been assigned to you.
                        </p>
                        <div className="notice-details">
                            <p><strong>Send a formal letter to the debtor's Accounts Payable stating:</strong></p>
                            <ul>
                                <li>The invoice has been sold/assigned to you</li>
                                <li>Future payments must be made to your account</li>
                                <li>Include the original invoice number and amount</li>
                            </ul>
                            <p className="legal-note">
                                📜 This is required under UCC Article 9 (US) and common law (Singapore)
                                for valid debt discharge. Without proper notice, the debtor may legally
                                pay the original seller and still discharge their debt.
                            </p>
                        </div>
                    </div>

                    <button
                        className="btn btn-secondary"
                        onClick={() => setPurchaseSuccess(null)}
                    >
                        Continue
                    </button>
                </div>
            )}

            {/* Search Results */}
            {searchResult && searchResult.offers.length > 0 && (
                <div className="search-results">
                    <h3>📋 Available Offers</h3>
                    <div className="nft-info">
                        <span className="label">Token ID:</span>
                        <code>{searchResult.nftokenId.slice(0, 16)}...{searchResult.nftokenId.slice(-8)}</code>
                        <a
                            href={`https://testnet.xrpl.org/nft/${searchResult.nftokenId}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="explorer-link small"
                        >
                            View on Explorer
                        </a>
                    </div>

                    <div className="offers-list">
                        {searchResult.offers.map((offer) => (
                            <div key={offer.index} className="offer-card">
                                <div className="offer-details">
                                    <div className="detail">
                                        <span className="label">Seller</span>
                                        <span className="value">{formatAddress(offer.owner)}</span>
                                    </div>
                                    <div className="detail">
                                        <span className="label">Price</span>
                                        <span className="value highlight">
                                            {formatOfferAmount(offer.amount)}
                                        </span>
                                    </div>
                                </div>
                                <button
                                    className="btn btn-primary buy-btn"
                                    onClick={() => handleBuy(offer)}
                                    disabled={buyingOfferId !== null}
                                >
                                    {buyingOfferId === offer.index ? '⏳ Processing...' : '💰 Buy Now'}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Empty State for No Offers */}
            {searchResult && searchResult.offers.length === 0 && !searchError && (
                <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <h3>NFT Found, But Not For Sale</h3>
                    <p>This NFT exists but has no active sell offers.</p>
                </div>
            )}

            {/* Instructions when no search yet */}
            {!searchResult && !searchError && (
                <div className="instructions">
                    <h3>How it works</h3>
                    <ol>
                        <li>Get the <strong>NFT Token ID</strong> from the invoice seller</li>
                        <li>Paste it in the search box above</li>
                        <li>Review the offer details and price</li>
                        <li>Click <strong>"Buy Now"</strong> to purchase with your connected wallet</li>
                    </ol>
                </div>
            )}
        </div>
    );
}

export default Marketplace;
