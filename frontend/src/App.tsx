/**
 * EULA Main Application Component
 * 
 * Orchestrates the invoice tokenization workflow:
 * 1. Wallet connection
 * 2. Document upload (3-way match)
 * 3. Verification
 * 4. NFT minting
 */

import { useState } from 'react';
import { useWallet } from './hooks/useWallet';
import { useVerification } from './hooks/useVerification';
import { WalletConnect } from './components/WalletConnect';
import { DropZone } from './components/DropZone';
import { VerificationStatus } from './components/VerificationStatus';
import { MintingPanel } from './components/MintingPanel';
import { Marketplace } from './components/Marketplace';
import { DIDManagement } from './components/DIDManagement';
import './App.css';

function App() {
    const {
        wallet,
        did,
        isLoading: walletLoading,
        error: walletError,
        connect,
        disconnect,
        refreshDID,
        createDID,
        removeDID
    } = useWallet();

    const {
        documents,
        result,
        isProcessing,
        error: verificationError,
        setDocument,
        clearDocument,
        verify,
        reset,
        isComplete,
    } = useVerification();

    const [showMinting, setShowMinting] = useState(false);
    const [showMarketplace, setShowMarketplace] = useState(false);
    const [showDIDManagement, setShowDIDManagement] = useState(false);

    const handleVerify = async () => {
        if (wallet.address) {
            await verify(wallet.address, false);
        }
    };

    const handleMint = () => {
        setShowMinting(true);
    };

    const handleCloseMinting = () => {
        setShowMinting(false);
    };

    return (
        <div className="app">
            <header className="app-header">
                <div className="container">
                    <div className="header-content">
                        <div className="logo">
                            <span className="logo-icon">◆</span>
                            <span className="logo-text">EULA</span>
                        </div>

                        <div className="header-actions">
                            <button
                                className="marketplace-btn"
                                onClick={() => setShowMarketplace(true)}
                            >
                                🏪 Marketplace
                            </button>
                            {wallet.isConnected && (
                                <WalletConnect
                                    wallet={wallet}
                                    did={did}
                                    isLoading={walletLoading}
                                    error={walletError}
                                    onConnect={connect}
                                    onDisconnect={disconnect}
                                    onManageDID={() => setShowDIDManagement(true)}
                                    onRefreshDID={refreshDID}
                                />
                            )}
                        </div>
                    </div>
                </div>
            </header>

            <main className="app-main">
                <div className="container">
                    {/* Hero section when not connected */}
                    {!wallet.isConnected && (
                        <section className="hero">
                            <h1>
                                Tokenize Your Invoices
                                <span className="gradient-text"> on XRPL</span>
                            </h1>
                            <p className="hero-subtitle">
                                Automated 3-way match verification. Instant RLUSD liquidity.
                                Zero paperwork.
                            </p>

                            <div className="hero-features">
                                <div className="feature">
                                    <span className="feature-icon">🔍</span>
                                    <span className="feature-text">AI-Powered OCR</span>
                                </div>
                                <div className="feature">
                                    <span className="feature-icon">✓</span>
                                    <span className="feature-text">Forensic Verification</span>
                                </div>
                                <div className="feature">
                                    <span className="feature-icon">⚡</span>
                                    <span className="feature-text">&lt;5s Settlement</span>
                                </div>
                            </div>

                            <div className="card card-elevated wallet-card">
                                <WalletConnect
                                    wallet={wallet}
                                    did={did}
                                    isLoading={walletLoading}
                                    error={walletError}
                                    onConnect={connect}
                                    onDisconnect={disconnect}
                                    onManageDID={() => setShowDIDManagement(true)}
                                    onRefreshDID={refreshDID}
                                />
                            </div>


                        </section>
                    )}

                    {/* Main workflow when connected */}
                    {wallet.isConnected && (
                        <section className="workflow">
                            {/* Show verification result or upload form */}
                            {result ? (
                                <div className="card card-elevated">
                                    <VerificationStatus
                                        result={result}
                                        onMint={handleMint}
                                        onReset={reset}
                                    />
                                </div>
                            ) : (
                                <>
                                    <div className="workflow-header">
                                        <h2>Upload Your Documents</h2>
                                        <p>
                                            Submit Invoice, Purchase Order, and Proof of Delivery
                                            for 3-way match verification
                                        </p>
                                    </div>

                                    <div className="card card-elevated">
                                        <DropZone
                                            documents={documents}
                                            onDrop={setDocument}
                                            onClear={clearDocument}
                                            disabled={isProcessing}
                                        />
                                    </div>

                                    {verificationError && (
                                        <div className="error-banner">
                                            {verificationError}
                                        </div>
                                    )}

                                    <div className="workflow-actions">
                                        <button
                                            className="btn btn-primary btn-lg"
                                            onClick={handleVerify}
                                            disabled={!isComplete || isProcessing}
                                        >
                                            {isProcessing ? (
                                                <>
                                                    <span className="animate-spin">⟳</span>
                                                    Verifying Documents...
                                                </>
                                            ) : (
                                                'Verify Documents'
                                            )}
                                        </button>
                                    </div>
                                </>
                            )}
                        </section>
                    )}
                </div>
            </main>

            <footer className="app-footer">
                <div className="container">
                    <p>
                        EULA © 2026 • Powered by{' '}
                        <a href="https://xrpl.org" target="_blank" rel="noopener noreferrer">
                            XRP Ledger
                        </a>
                    </p>
                </div>
            </footer>

            {/* Minting Modal */}
            {showMinting && result && wallet.address && (
                <div className="minting-modal-overlay" onClick={handleCloseMinting}>
                    <div className="minting-modal" onClick={(e) => e.stopPropagation()}>
                        <MintingPanel
                            verificationResult={result}
                            walletAddress={wallet.address}
                            onClose={handleCloseMinting}
                        />
                    </div>
                </div>
            )}

            {/* Marketplace Modal */}
            {showMarketplace && (
                <Marketplace
                    buyerAddress={wallet.address || null}
                    onClose={() => setShowMarketplace(false)}
                    onConnectWallet={() => {
                        setShowMarketplace(false);
                        // Wallet connect will show on main page
                    }}
                />
            )}

            {/* DID Management Modal */}
            {showDIDManagement && (
                <div className="minting-modal-overlay" onClick={() => setShowDIDManagement(false)}>
                    <div className="minting-modal" onClick={(e) => e.stopPropagation()}>
                        <DIDManagement
                            onClose={() => setShowDIDManagement(false)}
                            wallet={wallet}
                            did={did}
                            createDID={createDID} // Ensure this is the one from useWallet
                            removeDID={removeDID}
                            isLoading={walletLoading}
                            error={walletError}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;
