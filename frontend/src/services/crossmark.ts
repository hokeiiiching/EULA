/**
 * Crossmark Wallet Service
 * 
 * Uses Crossmark for SIGNING, then submits directly to XRPL.
 * Crossmark handles autofill of Sequence, Fee, LastLedgerSequence.
 */

import sdk from '@crossmarkio/sdk';
import { Client } from 'xrpl';

// ============================================================================
// Types
// ============================================================================

export interface CrossmarkAddress {
    address: string;
    network: string;
}

export interface CrossmarkTransactionResult {
    success: boolean;
    hash?: string;
    error?: string;
}

export interface NFTokenMintTransaction {
    TransactionType: 'NFTokenMint';
    Account: string;
    URI: string;
    Flags: number;
    TransferFee: number;
    NFTokenTaxon: number;
}

// ============================================================================
// Constants
// ============================================================================

const LOG_PREFIX = '[Crossmark]';
const XRPL_TESTNET_WS = 'wss://s.altnet.rippletest.net:51233';

// ============================================================================
// RLUSD Configuration (Ripple USD Stablecoin)
// ============================================================================

// RLUSD issuer address on XRPL Testnet
export const RLUSD_ISSUER_TESTNET = 'rQhWct2fv4Vc4KRjRgMrxa8xPN9Zx9iLKV';

// RLUSD currency code (standard format, not hex)
export const RLUSD_CURRENCY = 'USD';

// Helper to create RLUSD amount object for XRPL transactions
export function createRLUSDAmount(value: string, issuer: string = RLUSD_ISSUER_TESTNET): IssuedCurrencyAmount {
    return {
        currency: RLUSD_CURRENCY,
        issuer: issuer,
        value: value,
    };
}

export interface IssuedCurrencyAmount {
    currency: string;
    issuer: string;
    value: string;
}

// ============================================================================
// Logging
// ============================================================================

function logInfo(message: string, data?: unknown): void {
    console.log(`${LOG_PREFIX} ${message}`, data ?? '');
}

function logError(message: string, error?: unknown): void {
    console.error(`${LOG_PREFIX} ERROR: ${message}`, error ?? '');
}

// ============================================================================
// Public Functions
// ============================================================================

/**
 * Check if Crossmark extension is installed.
 */
export function isCrossmarkAvailable(): boolean {
    const installed = sdk.sync.isInstalled();
    logInfo('Crossmark installed:', installed);
    return installed ?? false;
}

/**
 * Connect to Crossmark wallet and get the user's address.
 */
export async function connectCrossmark(): Promise<CrossmarkAddress> {
    logInfo('Connecting to Crossmark...');

    try {
        const response = await sdk.async.signInAndWait();
        logInfo('SignIn response:', response);

        const address = response?.response?.data?.address;

        if (!address) {
            logError('No address in response:', response);
            throw new Error('No wallet address returned. Did you approve the connection?');
        }

        logInfo('Connected with address:', address);

        return { address, network: 'testnet' };
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Connection failed:', error);
        throw new Error(`Crossmark connection failed: ${message}`);
    }
}

/**
 * Sign with Crossmark, then submit directly to XRPL.
 * Let Crossmark autofill Sequence, Fee, LastLedgerSequence.
 */
export async function signAndSubmitNFTMint(
    transaction: NFTokenMintTransaction
): Promise<CrossmarkTransactionResult> {
    logInfo('='.repeat(50));
    logInfo('NFT MINT: Sign with Crossmark, Submit to XRPL');
    logInfo('='.repeat(50));

    let xrplClient: Client | null = null;

    try {
        // ================================================================
        // Step 1: BARE MINIMUM transaction for testing
        // Per XRPL docs, NFTokenMint requires: TransactionType, Account, NFTokenTaxon
        // Testing WITHOUT URI first to isolate the issue
        // ================================================================
        const nftMintTx: Record<string, unknown> = {
            TransactionType: 'NFTokenMint',
            Account: transaction.Account,
            NFTokenTaxon: 0,
            // NO URI - testing bare minimum
        };

        logInfo('Step 1: BARE MINIMUM Transaction (no URI):', nftMintTx);

        // ================================================================
        // Step 2: Sign with Crossmark
        // ================================================================
        logInfo('Step 2: Signing with Crossmark...');

        const signResp = await sdk.async.signAndWait(nftMintTx);
        logInfo('Sign response:', signResp);

        const txBlob = signResp?.response?.data?.txBlob;

        if (!txBlob) {
            logError('No txBlob:', signResp);
            return { success: false, error: 'Failed to sign. Did you approve?' };
        }

        logInfo('Got txBlob, length:', txBlob.length);

        // ================================================================
        // Step 3: Submit to XRPL directly
        // ================================================================
        logInfo('Step 3: Connecting to XRPL...');
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        logInfo('Step 4: Submitting to XRPL...');

        const submitResult = await xrplClient.request({
            command: 'submit',
            tx_blob: txBlob,
        });

        logInfo('Submit result:', submitResult);

        const engineResult = submitResult.result.engine_result;
        const hash = submitResult.result.tx_json?.hash;

        if (engineResult === 'tesSUCCESS' || engineResult === 'terQUEUED') {
            logInfo('SUCCESS! Hash:', hash);
            return { success: true, hash };
        } else {
            const errorMsg = `${engineResult}: ${submitResult.result.engine_result_message}`;
            logError('Failed:', errorMsg);
            return { success: false, error: errorMsg };
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Error:', error);
        return { success: false, error: message };
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Build the XRPL explorer URL for a transaction.
 */
export function getExplorerUrl(hash: string, network: 'testnet' | 'mainnet' = 'testnet'): string {
    return network === 'mainnet'
        ? `https://livenet.xrpl.org/transactions/${hash}`
        : `https://testnet.xrpl.org/transactions/${hash}`;
}

// ============================================================================
// DEX Offer Functions
// ============================================================================

export interface CreateSellOfferParams {
    account: string;       // Wallet address
    nftokenId: string;     // The NFT Token ID to sell
    amount: string;        // Price in RLUSD (e.g., "100.00")
}

/**
 * Create a sell offer on the DEX for an NFT.
 * This lists the NFT for sale so buyers can purchase it.
 * 
 * Per XRPL docs:
 * - TransactionType: 'NFTokenCreateOffer'
 * - Account: Your wallet
 * - NFTokenID: The NFT to sell
 * - Amount: Price in drops
 * - Flags: 1 = tfSellNFToken (sell offer)
 */
export async function createSellOffer(
    params: CreateSellOfferParams
): Promise<CrossmarkTransactionResult> {
    logInfo('='.repeat(50));
    logInfo('CREATE SELL OFFER: List NFT on DEX');
    logInfo('='.repeat(50));
    logInfo('NFTokenID:', params.nftokenId);
    logInfo('Price (drops):', params.amount);

    let xrplClient: Client | null = null;

    try {
        // Build the NFTokenCreateOffer transaction with RLUSD amount
        const rlusdAmount = createRLUSDAmount(params.amount);

        const offerTx: Record<string, unknown> = {
            TransactionType: 'NFTokenCreateOffer',
            Account: params.account,
            NFTokenID: params.nftokenId,
            Amount: rlusdAmount,  // Price in RLUSD
            Flags: 1,             // 1 = tfSellNFToken (sell offer)
        };

        logInfo('Step 1: Sell Offer Transaction:', offerTx);

        // Sign with Crossmark
        logInfo('Step 2: Signing with Crossmark...');
        const signResp = await sdk.async.signAndWait(offerTx);
        logInfo('Sign response:', signResp);

        const txBlob = signResp?.response?.data?.txBlob;

        if (!txBlob) {
            logError('No txBlob:', signResp);
            return { success: false, error: 'Failed to sign. Did you approve?' };
        }

        logInfo('Got txBlob, length:', txBlob.length);

        // Submit to XRPL
        logInfo('Step 3: Connecting to XRPL...');
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        logInfo('Step 4: Submitting to XRPL...');
        const submitResult = await xrplClient.request({
            command: 'submit',
            tx_blob: txBlob,
        });

        logInfo('Submit result:', submitResult);

        const engineResult = submitResult.result.engine_result;
        const hash = submitResult.result.tx_json?.hash;

        if (engineResult === 'tesSUCCESS' || engineResult === 'terQUEUED') {
            logInfo('SUCCESS! Sell offer created. Hash:', hash);
            return { success: true, hash };
        } else {
            const errorMsg = `${engineResult}: ${submitResult.result.engine_result_message}`;
            logError('Failed:', errorMsg);
            return { success: false, error: errorMsg };
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Error:', error);
        return { success: false, error: message };
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Get all NFTs owned by an account.
 */
export async function getAccountNFTs(account: string): Promise<any[]> {
    let xrplClient: Client | null = null;

    try {
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        const response = await xrplClient.request({
            command: 'account_nfts',
            account: account,
        });

        return response.result.account_nfts || [];
    } catch (error) {
        logError('Failed to get NFTs:', error);
        return [];
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

// ============================================================================
// Marketplace Functions
// ============================================================================

export interface NFTSellOffer {
    index: string;           // Offer ID (used to accept)
    amount: string | IssuedCurrencyAmount;  // Price (XRP drops string or RLUSD object)
    owner: string;           // Seller address
    destination?: string;    // Specific buyer (if any)
    nftokenId: string;       // The NFT being sold
    isRLUSD?: boolean;       // True if amount is in RLUSD
}

/**
 * Check if an amount is in RLUSD format.
 */
export function isRLUSDAmount(amount: unknown): amount is IssuedCurrencyAmount {
    return typeof amount === 'object' && amount !== null && 'currency' in amount && 'issuer' in amount;
}

/**
 * Format offer amount for display.
 * Returns formatted string like "100.00 RLUSD" or "10.5 XRP"
 */
export function formatOfferAmount(amount: string | IssuedCurrencyAmount): string {
    if (isRLUSDAmount(amount)) {
        const value = parseFloat(amount.value);
        return `${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} RLUSD`;
    }
    // XRP drops
    const xrp = parseInt(amount, 10) / 1_000_000;
    return `${xrp.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} XRP`;
}

/**
 * Get numeric value from offer amount (for sorting/comparison).
 */
export function getOfferAmountValue(amount: string | IssuedCurrencyAmount): number {
    if (isRLUSDAmount(amount)) {
        return parseFloat(amount.value);
    }
    return parseInt(amount, 10) / 1_000_000;
}

/**
 * Get sell offers for a specific NFT.
 */
export async function getNFTSellOffers(nftokenId: string): Promise<NFTSellOffer[]> {
    let xrplClient: Client | null = null;

    try {
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        const response = await xrplClient.request({
            command: 'nft_sell_offers',
            nft_id: nftokenId,
        });

        const offers = response.result.offers || [];
        return offers.map((offer: any) => ({
            index: offer.nft_offer_index,
            amount: offer.amount,
            owner: offer.owner,
            destination: offer.destination,
            nftokenId: nftokenId,
            isRLUSD: isRLUSDAmount(offer.amount),
        }));
    } catch (error: any) {
        // No offers found is not an error
        if (error?.data?.error === 'objectNotFound') {
            return [];
        }
        logError('Failed to get sell offers:', error);
        return [];
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Get all NFT sell offers from a seller's account.
 * This queries all NFTs owned by the seller and their offers.
 */
export async function getAllSellOffers(sellerAccount: string): Promise<NFTSellOffer[]> {
    const nfts = await getAccountNFTs(sellerAccount);
    const allOffers: NFTSellOffer[] = [];

    for (const nft of nfts) {
        const offers = await getNFTSellOffers(nft.NFTokenID);
        allOffers.push(...offers);
    }

    return allOffers;
}

export interface AcceptOfferParams {
    account: string;       // Buyer's wallet address
    sellOfferId: string;   // The offer ID to accept (from NFTSellOffer.index)
}

/**
 * Accept a sell offer to buy an NFT.
 * The buyer pays the offer amount and receives the NFT.
 */
export async function acceptSellOffer(
    params: AcceptOfferParams
): Promise<CrossmarkTransactionResult> {
    logInfo('='.repeat(50));
    logInfo('ACCEPT SELL OFFER: Buy NFT');
    logInfo('='.repeat(50));
    logInfo('Buyer:', params.account);
    logInfo('Offer ID:', params.sellOfferId);

    let xrplClient: Client | null = null;

    try {
        // Build NFTokenAcceptOffer transaction
        const acceptTx: Record<string, unknown> = {
            TransactionType: 'NFTokenAcceptOffer',
            Account: params.account,
            NFTokenSellOffer: params.sellOfferId,
        };

        logInfo('Step 1: Accept Offer Transaction:', acceptTx);

        // Sign with Crossmark
        logInfo('Step 2: Signing with Crossmark...');
        const signResp = await sdk.async.signAndWait(acceptTx);
        logInfo('Sign response:', signResp);

        const txBlob = signResp?.response?.data?.txBlob;

        if (!txBlob) {
            logError('No txBlob:', signResp);
            return { success: false, error: 'Failed to sign. Did you approve?' };
        }

        logInfo('Got txBlob, length:', txBlob.length);

        // Submit to XRPL
        logInfo('Step 3: Connecting to XRPL...');
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        logInfo('Step 4: Submitting to XRPL...');
        const submitResult = await xrplClient.request({
            command: 'submit',
            tx_blob: txBlob,
        });

        logInfo('Submit result:', submitResult);

        const engineResult = submitResult.result.engine_result;
        const hash = submitResult.result.tx_json?.hash;

        if (engineResult === 'tesSUCCESS' || engineResult === 'terQUEUED') {
            logInfo('SUCCESS! NFT purchased. Hash:', hash);
            return { success: true, hash };
        } else {
            const errorMsg = `${engineResult}: ${submitResult.result.engine_result_message}`;
            logError('Failed:', errorMsg);
            return { success: false, error: errorMsg };
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Error:', error);
        return { success: false, error: message };
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Convert drops to XRP.
 */
export function dropsToXrp(drops: string): number {
    return parseInt(drops, 10) / 1000000;
}

/**
 * Set DID for the account.
 */
export async function signAndSubmitDIDSet(
    account: string,
    dataHex: string
): Promise<CrossmarkTransactionResult> {
    logInfo('='.repeat(50));
    logInfo('DID SET: Sign with Crossmark, Submit to XRPL');
    logInfo('='.repeat(50));

    let xrplClient: Client | null = null;

    try {
        const tx: Record<string, unknown> = {
            TransactionType: 'DIDSet',
            Account: account,
            Data: dataHex,
        };

        logInfo('Step 1: DIDSet Transaction:', tx);

        // Sign with Crossmark
        logInfo('Step 2: Signing with Crossmark... (Please check for popup)');

        // Create a timeout promise
        const timeoutMs = 60000; // 60 seconds
        const timeoutPromise = new Promise<any>((_, reject) => {
            setTimeout(() => reject(new Error('Crossmark signing timed out. Please try again and ensure the popup is approved.')), timeoutMs);
        });

        // Race between signing and timeout
        const signResp = await Promise.race([
            sdk.async.signAndWait(tx),
            timeoutPromise
        ]);

        logInfo('Sign response:', signResp);

        const txBlob = signResp?.response?.data?.txBlob;

        if (!txBlob) {
            logError('No txBlob:', signResp);
            return { success: false, error: 'Failed to sign. Did you approve?' };
        }

        // Submit to XRPL and wait for validation
        logInfo('Step 3: Connecting to XRPL...');
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        logInfo('Step 4: Submitting and waiting for validation...');
        const result = await xrplClient.submitAndWait(txBlob);

        logInfo('Final Transaction Result:', result);

        const meta = result.result.meta;
        const transactionResult = typeof meta === 'string' ? meta : meta?.TransactionResult;
        const hash = result.result.hash;

        if (transactionResult === 'tesSUCCESS') {
            logInfo('SUCCESS! DID set. Hash:', hash);
            return { success: true, hash };
        } else {
            const errorMsg = `Transaction failed on ledger: ${transactionResult}`;
            logError('Failed:', errorMsg);
            return { success: false, error: errorMsg };
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Error:', error);
        return { success: false, error: message };
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Delete DID for the account.
 */
export async function signAndSubmitDIDDelete(
    account: string
): Promise<CrossmarkTransactionResult> {
    logInfo('='.repeat(50));
    logInfo('DID DELETE: Sign with Crossmark, Submit to XRPL');
    logInfo('='.repeat(50));

    let xrplClient: Client | null = null;

    try {
        const tx: Record<string, unknown> = {
            TransactionType: 'DIDDelete',
            Account: account,
        };

        logInfo('Step 1: DIDDelete Transaction:', tx);

        // Sign with Crossmark
        logInfo('Step 2: Signing with Crossmark...');
        const signResp = await sdk.async.signAndWait(tx);
        logInfo('Sign response:', signResp);

        const txBlob = signResp?.response?.data?.txBlob;

        if (!txBlob) {
            logError('No txBlob:', signResp);
            return { success: false, error: 'Failed to sign. Did you approve?' };
        }

        // Submit to XRPL and wait for validation
        logInfo('Step 3: Connecting to XRPL...');
        xrplClient = new Client(XRPL_TESTNET_WS);
        await xrplClient.connect();

        logInfo('Step 4: Submitting and waiting for validation...');
        const result = await xrplClient.submitAndWait(txBlob);

        logInfo('Final Transaction Result:', result);

        const meta = result.result.meta;
        const transactionResult = typeof meta === 'string' ? meta : meta?.TransactionResult;
        const hash = result.result.hash;

        if (transactionResult === 'tesSUCCESS') {
            logInfo('SUCCESS! DID deleted. Hash:', hash);
            return { success: true, hash };
        } else {
            const errorMsg = `Transaction failed on ledger: ${transactionResult}`;
            logError('Failed:', errorMsg);
            return { success: false, error: errorMsg };
        }

    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        logError('Error:', error);
        return { success: false, error: message };
    } finally {
        if (xrplClient?.isConnected()) {
            await xrplClient.disconnect();
        }
    }
}

/**
 * Format address for display.
 */
export function formatAddress(address: string): string {
    if (address.length <= 12) return address;
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
}
