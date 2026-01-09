
import { Client, Wallet, convertStringToHex } from 'xrpl';

const XRPL_TESTNET_WS = 'wss://s.altnet.rippletest.net:51233';

// Mocking the function I added to frontend (browser-native)
// In Node.js, TextEncoder is global in recent versions.
function stringToHex(str: string): string {
    return Array.from(new TextEncoder().encode(str))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('')
        .toUpperCase();
}

async function main() {
    const client = new Client(XRPL_TESTNET_WS);
    await client.connect();
    console.log('Connected to Testnet');

    try {
        // 1. Create and Fund Wallet
        console.log('Funding wallet...');
        const { wallet, balance } = await client.fundWallet();
        console.log(`Wallet created: ${wallet.address} (Balance: ${balance})`);

        // 2. Prepare Data
        const businessName = "Acme Manual Test";
        const registrationNumber = "999999";
        const country = "US";
        const dataString = `${businessName}|${registrationNumber}|${country}`;

        // Use our manual helper to verify it works
        const dataHex = stringToHex(dataString);
        console.log(`Data String: ${dataString}`);
        console.log(`Data Hex: ${dataHex}`);

        // 3. Construct Transaction
        const tx = {
            TransactionType: 'DIDSet',
            Account: wallet.address,
            Data: dataHex,
        };

        // 4. Submit and Wait
        console.log('Submitting DIDSet transaction...');
        const result = await client.submitAndWait(tx, { wallet });

        console.log(`Result: ${result.result.meta.TransactionResult}`);
        console.log(`Hash: ${result.result.hash}`);

        if (result.result.meta.TransactionResult === 'tesSUCCESS') {
            console.log('Transaction SUCCESS on ledger.');
        } else {
            console.error('Transaction FAILED on ledger.');
            return;
        }

        // 5. Verify Object Exists (Backend Logic)
        console.log('Querying account_objects...');
        const response = await client.request({
            command: 'account_objects',
            account: wallet.address,
            type: 'did'
        });

        console.log('Account Objects Response:', JSON.stringify(response.result, null, 2));

        const didObjects = response.result.account_objects || [];
        if (didObjects.length > 0) {
            console.log('SUCCESS: DID Object found on ledger!');
            console.log('Object:', didObjects[0]);
        } else {
            console.error('FAILURE: DID Object NOT found despite success result.');
        }

    } catch (err) {
        console.error('Error:', err);
    } finally {
        await client.disconnect();
    }
}

main();
