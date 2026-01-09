/**
 * XRPL Service
 * 
 * Provides XRPL ledger interactions and wallet connection utilities.
 */

import { Client } from 'xrpl';
import type { WalletState } from '../types';
import {
    connectCrossmark,
    isCrossmarkAvailable,
    signAndSubmitDIDSet,
    signAndSubmitDIDDelete
} from './crossmark';

// ============================================================================
// Constants
// ============================================================================

const XRPL_TESTNET_WS = 'wss://s.altnet.rippletest.net:51233';

function stringToHex(str: string): string {
    return Array.from(new TextEncoder().encode(str))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('')
        .toUpperCase();
}

// ============================================================================
// XRPL Client
// ============================================================================

let xrplClient: Client | null = null;

/**
 * Get or create XRPL WebSocket client connection.
 */
export async function getXrplClient(): Promise<Client> {
    if (xrplClient && xrplClient.isConnected()) {
        return xrplClient;
    }

    console.log('[XRPL] Connecting to testnet...');
    xrplClient = new Client(XRPL_TESTNET_WS);
    await xrplClient.connect();
    console.log('[XRPL] Connected');
    return xrplClient;
}

/**
 * Disconnect XRPL client.
 */
export async function disconnectXrpl(): Promise<void> {
    if (xrplClient && xrplClient.isConnected()) {
        console.log('[XRPL] Disconnecting...');
        await xrplClient.disconnect();
        xrplClient = null;
    }
}

// ============================================================================
// Account Queries
// ============================================================================

/**
 * Get all NFTs owned by an account.
 */
export async function getAccountNFTs(address: string): Promise<any[]> {
    const client = await getXrplClient();

    const response = await client.request({
        command: 'account_nfts',
        account: address,
    });

    return response.result.account_nfts || [];
}

/**
 * Check if address has a valid DID on ledger.
 */
export async function checkAddressDID(address: string): Promise<boolean> {
    const client = await getXrplClient();

    try {
        const response = await client.request({
            command: 'account_objects',
            account: address,
            type: 'did',
        });

        const didObjects = response.result.account_objects || [];
        return didObjects.length > 0;
    } catch {
        return false;
    }
}

/**
 * Set DID for the connected wallet.
 */
export async function setDID(
    userAddress: string,
    businessName: string,
    registrationNumber: string,
    country: string
): Promise<string> {
    console.log('[xrpl] setDID called with:', { userAddress, businessName, registrationNumber, country });
    // const client = await getXrplClient();

    // Format data as expected by backend: business_name|registration_number|country
    const dataString = `${businessName}|${registrationNumber}|${country}`;
    const dataHex = stringToHex(dataString);
    console.log('[xrpl] Formatted data hex:', dataHex);

    // Use Crossmark to sign and submit
    if (!isCrossmarkAvailable()) {
        throw new Error('Crossmark wallet extension is not installed');
    }

    // specific method that waits for validation
    // First, verify connection and get address
    // const { address } = await connectCrossmark(); // REMOVED: Redundant login
    console.log('[xrpl] Submitting DID transaction for address:', userAddress);

    const result = await signAndSubmitDIDSet(userAddress, dataHex);
    console.log('[xrpl] Transaction result:', result);

    if (!result.success) {
        throw new Error(result.error || 'Failed to create DID');
    }

    return result.hash || '';
}

/**
 * Delete DID for the connected wallet.
 */
export async function deleteDID(userAddress: string): Promise<string> {
    // const { address } = await connectCrossmark(); // REMOVED: Redundant login

    const result = await signAndSubmitDIDDelete(userAddress);

    if (!result.success) {
        throw new Error(result.error || 'Failed to delete DID');
    }

    return result.hash || '';
}

// ============================================================================
// Wallet Connection
// ============================================================================

/**
 * Connect wallet using the specified provider.
 */
export async function connectWallet(
    provider: 'crossmark' | 'demo'
): Promise<WalletState> {
    console.log(`[XRPL] Connecting wallet via ${provider}...`);

    if (provider === 'demo') {
        console.log('[XRPL] Using demo wallet');
        return {
            isConnected: true,
            address: 'rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe',
            network: 'testnet',
        };
    }

    if (provider === 'crossmark') {
        if (!isCrossmarkAvailable()) {
            throw new Error('Crossmark wallet extension is not installed');
        }

        const result = await connectCrossmark();
        console.log('[XRPL] Crossmark connected:', result.address);

        return {
            isConnected: true,
            address: result.address,
            network: 'testnet' as const,
        };
    }

    throw new Error(`Unknown wallet provider: ${provider}`);
}

/**
 * Disconnect wallet.
 */
export async function disconnectWallet(): Promise<WalletState> {
    await disconnectXrpl();
    console.log('[XRPL] Wallet disconnected');

    return {
        isConnected: false,
        address: null,
        network: null,
    };
}

// ============================================================================
// Utilities
// ============================================================================

/**
 * Format wallet address for display (truncated).
 */
export function formatAddress(address: string): string {
    if (address.length <= 12) return address;
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
