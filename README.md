# EULA
**Invoice Factoring Platform on XRP Ledger**

EULA enables SMEs to tokenize verified invoices as NFTs and sell them to invoice factorers for immediate liquidity. Built on XRPL with Crossmark wallet integration.

---

## Features

### For SMEs (Invoice Sellers)
- **3-Way Match Verification**: Upload Invoice, PO, and POD for automated forensic validation
- **AI-Powered OCR**: docTR extracts structured data with spatial context
- **NFT Minting**: Tokenize verified invoices on XRPL
- **RLUSD Pricing**: List invoice NFTs for sale in RLUSD stablecoin (Testnet)
- **DEX Listing**: Create sell offers directly on the on-chain order book

### For Invoice Factorers (Buyers)
- **Marketplace**: Search and browse invoice NFTs by Token ID
- **Instant Purchase**: Buy invoice NFTs using RLUSD or XRP
- **On-Chain Proof**: Blockchain verifies ownership transfer
- **Notice of Assignment**: Legal compliance reminder for debt collection rights

### Core Technology
- **RLUSD Stablecoin**: Pricing and settlement in Ripple USD
- **Crossmark Wallet**: Browser extension for secure transaction signing
- **XRPL Testnet**: Leveraging native NFT and DEX primitives
- **Duplicate Prevention**: SHA-256 analysis across documents
- **DID (Decentralized Identifier)**: On-chain business verification

---

## Architecture

react-frontend + crossmark-sdk -> fastapi-backend + doctr-ocr -> xrpl-testnet

---

## Quick Start

### Prerequisites
1. **Python 3.11+**
2. **Node.js 18+**
3. **Crossmark Wallet**: Install the [browser extension](https://crossmark.io)
4. **XRPL Testnet Account**: Create one at the [XRPL Faucet](https://xrpl.org/xrp-testnet-faucet.html)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. Install dependencies (including docTR for OCR):
   ```bash
   pip install -e ".[dev]"
   ```
   *Note: This may take a few minutes as it downloads OCR models.*

4. Start the API server:
   ```bash
   uvicorn src.eula.main:app --reload --port 8000
   ```

### Frontend Setup

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open your browser to: http://localhost:5173

---

## User Flows

### 1. Seller Flow (SME)
1. **Connect Wallet**: Open EULA and connect your Crossmark wallet.
2. **Verify Identity**: Create a DID if you haven't already (one-time on-chain setup).
3. **Upload Documents**: Drag & drop your Invoice, Purchase Order (PO), and Proof of Delivery (POD).
4. **Verify**: Click "Verify Documents". The AI checks for consistency (3-way match).
5. **Mint NFT**: Once verified, mint the invoice as an NFT.
6. **List for Sale**: Set your price in RLUSD and sign the sell offer.

### 2. Buyer Flow (Factorer)
1. **Browse**: Go to the Marketplace section.
2. **Search**: Enter the NFT Token ID provided by the seller.
3. **Review**: Check the invoice amount and price in RLUSD.
4. **Buy**: Click "Buy Now" and sign the transaction to purchase.
5. **Collection**: Follow the "Notice of Assignment" instructions to notify the debtor.

---

## Project Structure

- **backend/**: FastAPI application
  - **src/eula/services/**: Core logic for OCR, forensic validation, and XRPL interaction
  - **src/eula/domain/**: Business models and validation rules
  - **src/eula/api/**: REST endpoints
- **frontend/**: React application
  - **src/components/**: UI components (MintingPanel, Marketplace, etc.)
  - **src/services/**: Crossmark SDK and XRPL integration

---

## XRPL Integration Details

We use native XRPL features to build this platform:

| Feature | XRPL Primitive | Usage |
|---------|----------------|-------|
| **Tokenization** | `NFTokenMint` | Representing invoices as unique digital assets |
| **Trading** | `NFTokenCreateOffer` | Listing invoices for sale on the DEX |
| **Settlement** | `NFTokenAcceptOffer` | Atomic swap of RLUSD/XRP for the NFT |
| **Identity** | `DIDSet` | On-chain registry of verified business entities |
| **Pricing** | `IssuedCurrency` | Using RLUSD issuer for stable pricing |

---

## XRPL Transactions Used

- **Network**: XRPL Testnet
- **Stablecoin**: RLUSD (Testnet Issuer: `rQhWct2fv4Vc4KRjRgMrxa8xPN9Zx9iLKV`)
- **Validation**: 3-Way Match (Invoice/PO/POD) + Duplicate Amount Check

---

## License

MIT License — See LICENSE for details.

---

## Current Limitations (MVP)

- **Testnet only** — Not connected to mainnet
- **No URI metadata** — NFTs minted without metadata URI (caused malformed errors)
- **Manual Token ID sharing** — Sellers must share Token ID with buyers
- **Duplicate Detection (Partial)** — Invoice hash is computed but not persisted for cross-session checks

### Duplicate Detection Roadmap

The current implementation computes a SHA-256 hash of invoice documents to prevent double financing. However, full duplicate detection requires an off-chain index since XRPL NFT metadata cannot be efficiently queried.

**Production Implementation:**
1. **Database Table**: Store `{invoice_hash, nft_token_id, issuer_address, created_at}` when minting
2. **Pre-Mint Check**: Query the hash index before allowing `NFTokenMint`
3. **Index Options**:
   - PostgreSQL with unique constraint on `invoice_hash`
   - Redis for high-speed lookups
   - IPFS-based registry with CIDs for decentralized verification
4. **Rejection Flow**: Return `409 Conflict` if hash already exists with link to existing NFT

---

## Future Improvements

### Phase 2 — Legal & Compliance
- [x] **Notice of Assignment (Demo)** — UI reminder for buyers to notify debtors
  - *MVP Status*: In-app notification displays legal requirements after purchase
  - *Production Roadmap*: 
    1. Add debtor email field during invoice upload
    2. Integrate SendGrid/AWS SES for automated emails
    3. Auto-generate PDF assignment letters with `@react-pdf/renderer`
    4. Send on `NFTokenAcceptOffer` success
- [ ] Transferability clause document upload
- [ ] Ricardian contracts in NFT metadata (embed legal terms in NFT URI)

### Phase 3 — Enhanced Features  
- [ ] Email notifications for offers
- [ ] Invoice analytics dashboard
- [ ] Multi-invoice batch minting
- [ ] Transferability clause document upload

### Phase 3 — Enterprise
- [ ] ERP/SAP integration for auto-verification
- [ ] Ricardian contracts in NFT metadata
- [ ] Multi-chain support (Ethereum, Polygon)
- [ ] Institutional investor onboarding

---

## Testing

### Generate Sample Documents
```bash
cd backend/tests/sample_docs
python generate_test_pdfs.py
```

### Test the Flow
1. Start backend: `cd backend && uvicorn src.eula.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173
4. Connect Crossmark (testnet)
5. Upload sample PDFs
6. Verify → Mint → List → Buy from marketplace

---

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.

---

## SME Guide: Digital Identity (DID)

**For Business Owners (Non-Technical)**

### What is a DID?
Think of a **DID (Decentralized Identifier)** as a **digital passport** for your business that lives on the blockchain. Just like you have a UEN (Unique Entity Number) or Tax ID in the physical world, a DID proves who you are in the digital Web3 world.

### Why do I need it?
Invoice factorers (the people lending you money) need to know you are a legitimate business, not a scammer. Your DID is permanently linked to your wallet address, giving lenders confidence that:
1.  You are a real, registered business.
2.  Your invoices are authentic.
3.  Your reputation follows you on-chain.

### Frequently Asked Questions

**Q: Do I need to "Login" with my DID every time?**
**A: No.** You only create your DID **once**.
*   **One-Time Setup**: You fill out your business details and sign the transaction *one time*.
*   **Forever Valid**: Once created, it stays on the blockchain forever.
*   **Daily Use**: When you come back to EULA, just connect your wallet. The system automatically sees your DID and shows the "Verified" badge.

**Q: What if I make a mistake?**
**A:** You can **Delete/Revoke** your DID at any time and create a new one. However, keeping a long-standing DID builds more trust with lenders over time.

---

## Acknowledgments

- [XRP Ledger](https://xrpl.org) — NFT and DEX infrastructure
- [Crossmark](https://crossmark.io) — Browser wallet SDK
- [docTR](https://github.com/mindee/doctr) — OCR engine
- [FastAPI](https://fastapi.tiangolo.com) — Backend framework
- [React](https://react.dev) — Frontend framework
