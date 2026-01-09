/**
 * WalletConnect component for XRPL wallet integration.
 * 
 * Displays wallet connection status and provides connect/disconnect actions.
 */


import type { WalletState, DIDVerification } from '../types';
import { formatAddress } from '../services/xrpl';
import './WalletConnect.css';

interface WalletConnectProps {
    wallet: WalletState;
    did: DIDVerification | null;
    isLoading: boolean;
    error: string | null;
    onConnect: (provider: 'crossmark' | 'demo') => void;
    onDisconnect: () => void;
    onManageDID?: () => void;
    onRefreshDID?: () => void;
}

export function WalletConnect({
    wallet,
    did,
    isLoading,
    error,
    onConnect,
    onDisconnect,
    onManageDID,
    onRefreshDID,
}: WalletConnectProps) {
    if (wallet.isConnected && wallet.address) {
        return (
            <div className="wallet-connected">
                <div className="wallet-info">
                    <div className="wallet-identity">
                        <span className="network-badge">{wallet.network}</span>
                        <span className="address" title={wallet.address}>{formatAddress(wallet.address)}</span>
                    </div>

                    {did && (
                        <div className={`did-status-badge ${did.status}`}>
                            {did.status === 'verified' ? (
                                <span className="status-verified">
                                    <span className="icon">✓</span> {did.businessName}
                                </span>
                            ) : (
                                <span className="status-missing">
                                    <span className="icon">!</span> No DID
                                </span>
                            )}
                        </div>
                    )}
                </div>

                <div className="wallet-controls">
                    <div className="action-group">
                        <button
                            className="btn-icon"
                            onClick={onRefreshDID}
                            title="Refresh DID Status"
                        >
                            ⟳
                        </button>

                        <button
                            className={`btn-action ${did?.status === 'verified' ? 'btn-view' : 'btn-create'}`}
                            onClick={onManageDID}
                        >
                            {did?.status === 'verified' ? 'Manage ID' : 'Create ID'}
                        </button>

                        {did?.status === 'verified' && (
                            <a
                                href={`https://testnet.xrpl.org/accounts/${wallet.address}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn-icon"
                                title="View on Explorer"
                            >
                                ↗
                            </a>
                        )}
                    </div>

                    <div className="separator"></div>

                    <button
                        className="btn-disconnect"
                        onClick={onDisconnect}
                        disabled={isLoading}
                        title="Disconnect Wallet"
                    >
                        Disconnect
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="wallet-connect">
            <h3>Connect Your Wallet</h3>
            <p>Connect an XRPL wallet to tokenize your invoices</p>

            {error && (
                <div className="wallet-error">
                    {error}
                </div>
            )}

            <div className="wallet-options">
                <button
                    className="wallet-option"
                    onClick={() => onConnect('crossmark')}
                    disabled={isLoading}
                >
                    <img
                        src="https://crossmark.io/favicon.ico"
                        alt="Crossmark"
                        className="wallet-icon-img"
                        style={{ width: '24px', height: '24px' }}
                    />
                    <span className="wallet-name">Crossmark</span>
                    <span className="wallet-desc">Browser extension wallet</span>
                </button>
            </div>

            {isLoading && (
                <div className="wallet-loading">
                    <span className="animate-spin">⟳</span>
                    Connecting...
                </div>
            )}
        </div>
    );
}

export default WalletConnect;
