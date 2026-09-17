"use client";

import { Navbar } from "@/components/Navbar";
import { DisputeRegistry } from "@/components/DisputeRegistry";
import { IntegrationPanel } from "@/components/IntegrationPanel";

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />

      <main className="flex-grow pt-20 pb-12 px-4 md:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-10 animate-fade-in">
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-4">
              OmniCourt
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-3xl mx-auto">
              A chain-agnostic dispute adjudication registry. One deployed
              contract any application can call into to have a disputed
              transaction judged by decentralized AI validators — between two
              agents, an agent and a person, or two people.
            </p>
          </div>

          <section className="mb-10 animate-fade-in" style={{ animationDelay: "80ms" }}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Step
                index="1"
                title="Open a dispute"
                body="Name the two parties however they exist — a wallet on any chain, an agent id, an email. No GenLayer account required for either side."
              />
              <Step
                index="2"
                title="Submit evidence"
                body="Any public URL a machine can read — a chain API response, a raw data endpoint, a direct image link. Nothing is bridged and no foreign chain state is read."
              />
              <Step
                index="3"
                title="Get a verdict"
                body="Each validator independently re-fetches the evidence and judges it. Consensus produces a verdict your app reads back and enforces."
              />
            </div>
          </section>

          <section className="mb-10 animate-slide-up">
            <h2 className="text-2xl font-bold mb-4">Dispute registry</h2>
            <DisputeRegistry />
          </section>

          <section className="animate-fade-in" style={{ animationDelay: "160ms" }}>
            <IntegrationPanel />
          </section>

          <section
            className="mt-10 brand-card p-6 md:p-8 animate-fade-in"
            style={{ animationDelay: "200ms" }}
          >
            <h2 className="text-2xl font-bold mb-3">Why decentralized judgment</h2>
            <p className="text-sm text-muted-foreground">
              Every question OmniCourt answers — did the agent&apos;s output match
              its mandate? did the buyer actually receive the item? did the second
              agent deliver the result it billed for? — is a subjective,
              evidence-weighing judgment, not a deterministic computation. A single
              centralized arbiter is both a single point of failure and a single
              point of bias. Optimistic Democracy across independent validators is
              what makes the verdict contestable and non-unilateral, which is the
              only reason a &ldquo;court&rdquo; is credible at all.
            </p>
            <p className="text-sm text-muted-foreground mt-3">
              OmniCourt deliberately stops at the verdict. Enforcement is
              chain-specific and belongs to the calling application — this is the
              judgment layer, not the enforcement layer.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}

function Step({
  index,
  title,
  body,
}: {
  index: string;
  title: string;
  body: string;
}) {
  return (
    <div className="brand-card p-5 space-y-2">
      <div className="text-accent font-bold text-lg">
        {index}. {title}
      </div>
      <p className="text-sm text-muted-foreground">{body}</p>
    </div>
  );
}
