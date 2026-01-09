/**
 * Custom React hook for wallet connection state.
 */

import { useState, useCallback } from 'react';
import type { WalletState, DIDVerification } from '../types';
import { connectWallet, disconnectWallet } from '../services/xrpl';
import { checkDID } from '../services/api';

interface UseWalletReturn {
    wallet: WalletState;
    did: DIDVerification | null;
    isLoading: boolean;
    error: string | null;
    connect: (provider: 'crossmark' | 'demo') => Promise<void>;
    disconnect: () => Promise<void>;
    createDID: (businessName: string, registrationNumber: string, country: string) => Promise<void>;
    removeDID: () => Promise<void>;
    refreshDID: () => Promise<void>;
}

export function useWallet(): UseWalletReturn {
    const [wallet, setWallet] = useState<WalletState>({
        isConnected: false,
        address: null,
        network: null,
    });
    const [did, setDid] = useState<DIDVerification | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const connect = useCallback(async (
        provider: 'crossmark' | 'demo'
    ) => {
        setIsLoading(true);
        setError(null);

        try {
            const walletState = await connectWallet(provider);
            setWallet(walletState);

            // Check DID status after connecting
            if (walletState.address) {
                try {
                    const didResult = await checkDID(walletState.address);
                    setDid(didResult);
                } catch (didError) {
                    // DID check failed, but wallet is still connected
                    console.warn('DID check failed:', didError);
                    setDid(null);
                }
            }
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to connect wallet';
            setError(message);
            setWallet({ isConnected: false, address: null, network: null });
        } finally {
            setIsLoading(false);
        }
    }, []);

    const disconnect = useCallback(async () => {
        setIsLoading(true);
        try {
            const walletState = await disconnectWallet();
            setWallet(walletState);
            setDid(null);
        } finally {
            setIsLoading(false);
        }
    }, []);

    const createDID = useCallback(async (
        businessName: string,
        registrationNumber: string,
        country: string
    ) => {
        if (!wallet.address) return;
        setIsLoading(true);
        setError(null);
        console.log('[useWallet] createDID started for:', businessName);
        try {
            const { setDID } = await import('../services/xrpl');
            console.log('[useWallet] Calling setDID...');
            if (!wallet.address) throw new Error('Wallet not connected');
            const txHash = await setDID(wallet.address, businessName, registrationNumber, country);
            console.log('[useWallet] setDID successful, txHash:', txHash);

            // Poll for update or just optimistically update?
            // For now, let's wait a bit and then re-check
            console.log('[useWallet] Waiting 4s for ledger close...');
            await new Promise(resolve => setTimeout(resolve, 4000)); // Wait for ledger close

            console.log('[useWallet] Re-checking DID status...');
            const didResult = await checkDID(wallet.address);
            console.log('[useWallet] DID check result:', didResult);
            setDid(didResult);
        } catch (err) {
            console.error('[useWallet] createDID failed:', err);
            const message = err instanceof Error ? err.message : 'Failed to create DID';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [wallet.address]);

    const removeDID = useCallback(async () => {
        if (!wallet.address) return;
        setIsLoading(true);
        setError(null);
        try {
            const { deleteDID } = await import('../services/xrpl');
            if (!wallet.address) throw new Error('Wallet not connected');
            await deleteDID(wallet.address);

            await new Promise(resolve => setTimeout(resolve, 4000)); // Wait for ledger close

            const didResult = await checkDID(wallet.address);
            setDid(didResult);
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to delete DID';
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [wallet.address]);

    const refreshDID = useCallback(async () => {
        if (wallet.address) {
            setIsLoading(true);
            try {
                console.log('[useWallet] Manual refresh triggered');
                const didResult = await checkDID(wallet.address);
                setDid(didResult);
            } catch (err) {
                console.error('[useWallet] Manual refresh failed:', err);
            } finally {
                setIsLoading(false);
            }
        }
    }, [wallet.address]);

    return {
        wallet,
        did,
        isLoading,
        error,
        connect,
        disconnect,
        createDID,
        removeDID,
        refreshDID,
    };
}
