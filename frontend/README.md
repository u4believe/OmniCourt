# OmniCourt frontend

Next.js frontend for OmniCourt — a chain-agnostic dispute adjudication registry
on GenLayer. See the [project README](../README.md) for the contract itself.

## Setup

1. Install dependencies:

**Using bun:**
```bash
bun install
```

**Using npm:**
```bash
npm install
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Configure environment variables:
   - `NEXT_PUBLIC_CONTRACT_ADDRESS` - the deployed OmniCourt registry address
   - `NEXT_PUBLIC_GENLAYER_RPC_URL` - GenLayer RPC URL (defaults to `https://studio-next.genlayer.com/api`)
   - `NEXT_PUBLIC_GENLAYER_CHAIN_ID` - RPC chain ID (defaults to `61997`)
   - `NEXT_PUBLIC_GENLAYER_CHAIN_NAME` - Network label shown to users

   Change the RPC URL and chain ID together. The same resolved network is used
   by MetaMask, `genlayer-js`, and Transaction Kit.

## Development

**Using bun:**
```bash
bun dev
```

**Using npm:**
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Build

**Using bun:**
```bash
bun run build
bun start
```

**Using npm:**
```bash
npm run build
npm start
```

## Tech Stack

- **Next.js 16** - React framework with App Router
- **TypeScript** - Type safety
- **Tailwind CSS v4** - Styling with custom glass-morphism theme
- **genlayer-js** - GenLayer blockchain SDK
- **TanStack Query (React Query)** - Data fetching and caching
- **Radix UI** - Accessible component primitives
- **shadcn/ui** - Pre-built UI components

## Wallet Management

The app connects to MetaMask, adds or switches to the configured GenLayer
network, supports account switching, and remembers only the user's explicit
disconnect preference. Private keys are never stored by the application.

## Features

- **File a dispute**: Pick one of the three relationship types (agent-agent,
  agent-person, person-person) and describe the claim and the remedy sought.
  Parties are named by free-form reference, so neither side needs a GenLayer
  wallet.
- **Submit evidence**: Attach any public URL to either side. Validators fetch it
  themselves, which is what makes the registry network-agnostic.
- **Adjudicate**: Send a dispute for judgment. Each validator independently
  re-fetches every evidence URL and reaches its own verdict.
- **Read verdicts**: Per dispute — status, both evidence trails, the recommended
  action, the allocation split, and the validators' reasoning.
- **Integration panel**: The exact `get_verdict` call another application makes,
  rendered against the live contract address.
- **Glass-morphism UI**: Premium dark theme with OKLCH colors, backdrop blur effects, and smooth animations
- **Data Refresh**: TanStack Query refreshes contract data after completed transactions and when the window regains focus
